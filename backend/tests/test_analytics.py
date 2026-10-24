"""6. Statistika formulalari, davr chegaralari, nol qiymatlar va filtrlangan CSV'ning panel bilan mosligi."""

import csv
import io
import zoneinfo
from datetime import date, datetime, time, timedelta

import pytest

from apps.analytics.services import Analytics, Filters, parse_filters
from apps.bookings.models import BookingEvent, Enrollment, TrialBooking
from apps.conversations.models import Conversation, HumanHandoff, Message
from apps.courses.models import TrialSlot
from apps.leads.models import LeadStatusChange

pytestmark = pytest.mark.django_db
TZ = zoneinfo.ZoneInfo("Asia/Tashkent")
D_FROM, D_TO = date(2026, 9, 1), date(2026, 9, 10)


def at(d: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm), tzinfo=TZ)


def make_slot(kit, when, group=None, capacity=10):
    return TrialSlot.objects.create(organization=kit.org, group=group or kit.group, starts_at=when, ends_at=when + timedelta(minutes=90), capacity=capacity)


def book(kit, lead, slot, confirmed_at, status="confirmed", cancelled_at=None):
    b = TrialBooking.objects.create(organization=kit.org, lead=lead, slot=slot, status=status, confirmed_at=confirmed_at, cancelled_at=cancelled_at)
    BookingEvent.objects.create(organization=kit.org, booking=b, event_type="confirmed", occurred_at=confirmed_at)
    if status == "attended":
        BookingEvent.objects.create(organization=kit.org, booking=b, event_type="attended", occurred_at=slot.starts_at + timedelta(hours=1))
    return b


def analytics(kit, **kw):
    f = Filters(date_from=kw.pop("date_from", D_FROM), date_to=kw.pop("date_to", D_TO), **kw)
    return Analytics(kit.org, f)


def kpi(data, key):
    return next(k for k in data if k["key"] == key)


def test_period_boundaries_use_org_timezone(kit):
    inside_start = kit.lead(created_at=at(D_FROM, 0, 5))  # 00:05 Toshkent = oldingi kun 19:05 UTC
    inside_end = kit.lead(created_at=at(D_TO, 23, 55))
    before = kit.lead(created_at=at(D_FROM, 0, 0) - timedelta(minutes=1))
    after = kit.lead(created_at=at(D_TO + timedelta(days=1), 0, 0))
    a = analytics(kit)
    ids = set(a.leads().filter(created_at__gte=a.start, created_at__lt=a.end).values_list("id", flat=True))
    assert ids == {inside_start.id, inside_end.id}
    assert before.id not in ids and after.id not in ids
    k = kpi(a.kpis(), "new_leads")
    assert k["value"] == 2
    assert k["previous"] == 1  # 'before' oldingi teng davrga tushadi
    assert k["change"] == 100.0
    assert a.prev_from == date(2026, 8, 22) and a.prev_to == date(2026, 8, 31)
    spark = {p["bucket"]: p["value"] for p in k["sparkline"]}
    assert spark["2026-09-01"] == 1 and spark["2026-09-10"] == 1 and len(spark) == 10


def test_zero_values_and_no_previous_data(kit):
    a = analytics(kit)
    data = a.kpis()
    conv = kpi(data, "conversion_rate")
    assert conv["value"] is None and conv["denominator"] == 0
    leads = kpi(data, "new_leads")
    assert leads["value"] == 0 and leads["change"] is None and leads["no_previous_data"] is True
    assert kpi(data, "ai_first_response_median")["value"] is None
    kit.lead(created_at=at(D_FROM, 12))
    leads = kpi(analytics(kit).kpis(), "new_leads")
    assert leads["value"] == 1 and leads["previous"] == 0 and leads["change"] is None and leads["no_previous_data"] is True


def test_conversion_cohort_definition(kit):
    slot = make_slot(kit, at(D_TO, 10))
    l1 = kit.lead(created_at=at(D_FROM, 10))
    l2 = kit.lead(created_at=at(D_FROM, 11))
    l3 = kit.lead(created_at=at(D_FROM, 12))
    kit.lead(created_at=at(D_FROM, 13))
    old = kit.lead(created_at=at(D_FROM - timedelta(days=3), 10))  # kohortaga kirmaydi
    book(kit, l1, slot, at(D_FROM, 15))
    book(kit, l2, slot, at(D_FROM, 16), status="cancelled", cancelled_at=at(D_FROM + timedelta(days=1), 9))  # bekor bo'lsa ham hisoblanadi
    book(kit, l3, make_slot(kit, at(D_TO + timedelta(days=5), 10)), at(D_TO + timedelta(days=1), 9))  # davr oxiridan keyin — hisoblanmaydi
    book(kit, old, slot, at(D_FROM + timedelta(days=2), 10))
    conv = kpi(analytics(kit).kpis(), "conversion_rate")
    assert conv["numerator"] == 2 and conv["denominator"] == 4
    assert conv["value"] == 50.0
    assert "davr oxirigacha" in conv["definition"]


def test_new_bookings_counted_on_first_confirmation_and_cancellations_separate(kit):
    slot = make_slot(kit, at(D_TO, 10))
    lead = kit.lead(created_at=at(D_FROM, 9))
    b = book(kit, lead, slot, at(D_FROM, 10), status="cancelled", cancelled_at=at(D_FROM + timedelta(days=2), 10))
    a = analytics(kit)
    assert kpi(a.kpis(), "confirmed_bookings")["value"] == 1
    series = {row["bucket"]: row for row in a.timeseries()}
    assert series["2026-09-01"]["confirmed_bookings"] == 1
    assert series["2026-09-03"]["cancelled_bookings"] == 1
    statuses = {r["status"]: r["count"] for r in a.booking_statuses()}
    assert statuses["cancelled"] == 1 and statuses["confirmed"] == 0
    assert b.confirmed_at == at(D_FROM, 10)


def test_first_response_ai_and_operator_not_mixed(kit):
    lead = kit.lead(source="webchat", created_at=at(D_FROM, 10))
    conv = Conversation.objects.create(organization=kit.org, lead=lead, channel="webchat", external_chat_id="frt1", created_at=at(D_FROM, 10))
    t0 = at(D_FROM, 10)
    Message.objects.create(organization=kit.org, conversation=conv, sender="customer", text="salom", created_at=t0)
    Message.objects.create(organization=kit.org, conversation=conv, sender="ai", text="javob", created_at=t0 + timedelta(seconds=4))
    t1 = t0 + timedelta(minutes=5)
    Message.objects.create(organization=kit.org, conversation=conv, sender="customer", text="admin", created_at=t1)
    HumanHandoff.objects.create(organization=kit.org, conversation=conv, requested_via="customer", created_at=t1 + timedelta(seconds=1))
    Message.objects.create(organization=kit.org, conversation=conv, sender="operator", text="salom", created_at=t1 + timedelta(seconds=300))

    lead2 = kit.lead(source="telegram", created_at=at(D_FROM, 11))
    conv2 = Conversation.objects.create(organization=kit.org, lead=lead2, channel="telegram", external_chat_id="frt2", created_at=at(D_FROM, 11))
    Message.objects.create(organization=kit.org, conversation=conv2, sender="customer", text="?", created_at=at(D_FROM, 11))
    Message.objects.create(organization=kit.org, conversation=conv2, sender="ai", text="!", created_at=at(D_FROM, 11) + timedelta(seconds=10))
    data = analytics(kit).kpis()
    assert kpi(data, "ai_first_response_median")["value"] == 7.0  # median(4, 10)
    assert kpi(data, "operator_first_response_median")["value"] == 300.0
    assert kpi(data, "operator_first_response_median")["samples"] == 1


def test_funnel_unique_leads_and_rebooking_not_double_counted(kit):
    lead = kit.lead(created_at=at(D_FROM, 9))
    LeadStatusChange.objects.create(lead=lead, from_status="new", to_status="qualified", created_at=at(D_FROM, 9, 5))
    s1, s2 = make_slot(kit, at(D_FROM + timedelta(days=2), 10)), make_slot(kit, at(D_FROM + timedelta(days=4), 10))
    book(kit, lead, s1, at(D_FROM, 10), status="cancelled", cancelled_at=at(D_FROM, 18))
    book(kit, lead, s2, at(D_FROM, 19), status="attended")
    Enrollment.objects.create(organization=kit.org, lead=lead, course=kit.course, status="confirmed", confirmed_at=at(D_FROM + timedelta(days=6), 10))
    kit.lead(created_at=at(D_FROM, 12))
    funnel = {row["stage"]: row["count"] for row in analytics(kit).funnel()}
    assert funnel == {"lead": 2, "qualified": 1, "trial_booked": 1, "trial_attended": 1, "enrolled": 1}
    counts = list(funnel.values())
    assert counts == sorted(counts, reverse=True)


def test_filters_apply_consistently_and_csv_matches(kit, client_for):
    slot_a = make_slot(kit, at(D_FROM + timedelta(days=3), 10), group=kit.group)
    slot_b = make_slot(kit, at(D_FROM + timedelta(days=3), 18), group=kit.group2)
    la = kit.lead(created_at=at(D_FROM, 10), branch=kit.branch, interested_course=kit.course, source="telegram")
    lb = kit.lead(created_at=at(D_FROM, 11), branch=kit.branch2, interested_course=kit.course2, source="webchat")
    book(kit, la, slot_a, at(D_FROM, 12))
    book(kit, lb, slot_b, at(D_FROM, 13))
    client = client_for(kit.manager)
    params = f"date_from={D_FROM}&date_to={D_TO}&branch_id={kit.branch.id}"
    overview = client.get(f"/api/analytics/overview/?{params}").json()
    assert kpi(overview["kpis"], "new_leads")["value"] == 1
    assert kpi(overview["kpis"], "confirmed_bookings")["value"] == 1
    assert sum(r["confirmed_bookings"] for r in overview["timeseries"]) == 1
    response = client.get(f"/api/analytics/export.csv?{params}")
    assert response.status_code == 200 and response["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    kpi_rows = {r[1]: r[3] for r in rows if r and r[0] == "kpi"}
    for item in overview["kpis"]:
        expected = "—" if item["value"] is None else str(item["value"])
        assert kpi_rows[item["key"]] == expected, item["key"]
    ts_rows = [r for r in rows if r and r[0] == "timeseries"]
    assert [(r[1], int(r[4]), int(r[5])) for r in ts_rows] == [(t["bucket"], t["new_leads"], t["confirmed_bookings"]) for t in overview["timeseries"]]
    # Manba filtri
    src = client.get(f"/api/analytics/overview/?date_from={D_FROM}&date_to={D_TO}&source=webchat").json()
    assert kpi(src["kpis"], "new_leads")["value"] == 1 and kpi(src["kpis"], "confirmed_bookings")["value"] == 1
    # Kurs filtri
    crs = client.get(f"/api/analytics/overview/?date_from={D_FROM}&date_to={D_TO}&course_id={kit.course2.id}").json()
    assert [c["course_id"] for c in crs["courses"]] == [kit.course2.id]
    # Drill-down jadvali grafik nuqtasiga mos
    det = client.get(f"/api/analytics/details/?date_from={D_FROM}&date_to={D_TO}&metric=new_leads&bucket=2026-09-01").json()
    assert det["kind"] == "leads" and det["count"] == 2


def test_week_granularity_buckets(kit):
    kit.lead(created_at=at(date(2026, 9, 7), 10))  # dushanba
    kit.lead(created_at=at(date(2026, 9, 13), 10))  # yakshanba — o'sha hafta
    a = analytics(kit, date_from=date(2026, 9, 1), date_to=date(2026, 9, 20), granularity="week")
    rows = {r["bucket"]: r["new_leads"] for r in a.timeseries()}
    assert rows["2026-09-07"] == 2
    assert list(rows)[0] == "2026-08-31"


def test_invalid_filters(kit):
    from apps.core.exceptions import BusinessError

    with pytest.raises(BusinessError):
        parse_filters(kit.org, {"date_from": "2026-09-10", "date_to": "2026-09-01"})
    with pytest.raises(BusinessError):
        parse_filters(kit.org, {"date_from": "bad"})
    with pytest.raises(BusinessError):
        parse_filters(kit.org, {"date_from": "2025-01-01", "date_to": "2026-09-01"})
