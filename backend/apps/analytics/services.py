"""Statistika: barcha qiymatlar haqiqiy DB yozuvlaridan, tashkilot vaqt zonasida hisoblanadi.

Ta'riflar METRICS.md'da batafsil yozilgan. Qisqacha:
  * Davr [date_from 00:00, date_to+1 00:00) — tashkilot zonasida; oldingi davr — teng uzunlikdagi
    bevosita oldingi oraliq.
  * Yangi mijoz — davrda yaratilgan noyob lead (test leadlar hisobga olinmaydi).
  * Yangi bron — davrda BIRINCHI marta tasdiqlangan bron (TrialBooking.confirmed_at, o'zgarmaydi).
  * Konversiya — davrda yaratilgan leadlar ichida davr oxirigacha kamida bitta tasdiqlangan bron
    olgan noyob leadlar / davrda yaratilgan noyob leadlar.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Min, OuterRef, Q, Subquery
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from apps.bookings.models import BookingEvent, Enrollment, TrialBooking
from apps.conversations.models import Conversation, HumanHandoff, Message
from apps.core.audit import AuditEvent
from apps.core.exceptions import BusinessError
from apps.core.utils import org_tz
from apps.courses.models import Course
from apps.leads.models import Lead, LeadStatusChange

MAX_RANGE_DAYS = 366
STAGES = [
    ("lead", "Murojaat"),
    ("qualified", "Ehtiyoj aniqlandi"),
    ("trial_booked", "Sinovga yozildi"),
    ("trial_attended", "Sinovga keldi"),
    ("enrolled", "O'qishga yozildi"),
]
STATUS_STAGE_INDEX = {"new": 0, "qualified": 1, "trial_booked": 2, "trial_attended": 3, "enrolled": 4}
KPI_KEYS = [
    "new_leads",
    "new_conversations",
    "confirmed_bookings",
    "attended",
    "enrolled",
    "conversion_rate",
    "ai_first_response_median",
    "operator_first_response_median",
]
KPI_LABELS = {
    "new_leads": "Yangi mijozlar",
    "new_conversations": "Yangi suhbatlar",
    "confirmed_bookings": "Tasdiqlangan sinov bronlari",
    "attended": "Sinov darsiga kelganlar",
    "enrolled": "O'qishga yozilganlar",
    "conversion_rate": "Mijozdan bronga konversiya",
    "ai_first_response_median": "AI birinchi javob (median)",
    "operator_first_response_median": "Operator birinchi javob (median)",
}


@dataclass
class Filters:
    date_from: date
    date_to: date
    branch_id: int | None = None
    course_id: int | None = None
    source: str | None = None
    granularity: str = "day"
    allowed_branch_ids: list[int] | None = None

    def as_dict(self) -> dict:
        return {
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "branch_id": self.branch_id,
            "course_id": self.course_id,
            "source": self.source,
            "granularity": self.granularity,
        }


def _int_or_none(value):
    if value in (None, "", "all", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise BusinessError("invalid_filter", "Filtr qiymati noto'g'ri.", status_code=400) from None


def parse_filters(organization, params, membership=None) -> Filters:
    tz = org_tz(organization)
    today = timezone.localtime(timezone.now(), tz).date()
    try:
        date_to = date.fromisoformat(params.get("date_to")) if params.get("date_to") else today
        date_from = date.fromisoformat(params.get("date_from")) if params.get("date_from") else date_to - timedelta(days=29)
    except ValueError:
        raise BusinessError("invalid_date", "Sana formati YYYY-MM-DD bo'lishi kerak.", status_code=400) from None
    if date_from > date_to:
        raise BusinessError("invalid_range", "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.", status_code=400)
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise BusinessError("range_too_long", f"Davr {MAX_RANGE_DAYS} kundan oshmasligi kerak.", status_code=400)
    granularity = params.get("granularity") or ("week" if (date_to - date_from).days > 62 else "day")
    if granularity not in ("day", "week"):
        raise BusinessError("invalid_granularity", "granularity: day yoki week.", status_code=400)
    source = params.get("source") or None
    if source and source not in Lead.Source.values:
        raise BusinessError("invalid_source", "Noma'lum manba.", status_code=400)
    filters = Filters(
        date_from=date_from,
        date_to=date_to,
        branch_id=_int_or_none(params.get("branch_id")),
        course_id=_int_or_none(params.get("course_id")),
        source=source,
        granularity=granularity,
    )
    if membership is not None and membership.role != "owner":
        allowed = list(membership.branches.values_list("id", flat=True))
        if allowed:
            if filters.branch_id and filters.branch_id not in allowed:
                raise BusinessError("forbidden_branch", "Bu filial statistikasi sizga ochiq emas.", status_code=403)
            filters.allowed_branch_ids = allowed
    if filters.branch_id and not organization.branches.filter(pk=filters.branch_id).exists():
        raise BusinessError("not_found", "Filial topilmadi.", status_code=404)
    if filters.course_id and not Course.objects.filter(organization=organization, pk=filters.course_id).exists():
        raise BusinessError("not_found", "Kurs topilmadi.", status_code=404)
    return filters


class Analytics:
    def __init__(self, organization, filters: Filters):
        self.org = organization
        self.f = filters
        self.tz = org_tz(organization)
        self.start, self.end = self.bounds(filters.date_from, filters.date_to)
        length = (filters.date_to - filters.date_from).days + 1
        self.prev_from = filters.date_from - timedelta(days=length)
        self.prev_to = filters.date_from - timedelta(days=1)
        self.prev_start, self.prev_end = self.bounds(self.prev_from, self.prev_to)

    def bounds(self, d_from: date, d_to: date) -> tuple[datetime, datetime]:
        return datetime.combine(d_from, time.min, tzinfo=self.tz), datetime.combine(d_to + timedelta(days=1), time.min, tzinfo=self.tz)

    # ------------------------------------------------------------------ base querysets
    def leads(self):
        qs = Lead.objects.filter(organization=self.org, is_test=False)
        if self.f.branch_id:
            qs = qs.filter(branch_id=self.f.branch_id)
        elif self.f.allowed_branch_ids:
            qs = qs.filter(Q(branch_id__in=self.f.allowed_branch_ids) | Q(branch__isnull=True))
        if self.f.course_id:
            qs = qs.filter(interested_course_id=self.f.course_id)
        if self.f.source:
            qs = qs.filter(source=self.f.source)
        return qs

    def conversations(self):
        qs = Conversation.objects.filter(organization=self.org).exclude(channel=Conversation.Channel.TEST).filter(lead__is_test=False)
        if self.f.branch_id:
            qs = qs.filter(lead__branch_id=self.f.branch_id)
        elif self.f.allowed_branch_ids:
            qs = qs.filter(Q(lead__branch_id__in=self.f.allowed_branch_ids) | Q(lead__branch__isnull=True))
        if self.f.course_id:
            qs = qs.filter(lead__interested_course_id=self.f.course_id)
        if self.f.source:
            qs = qs.filter(lead__source=self.f.source)
        return qs

    def bookings(self):
        qs = TrialBooking.objects.filter(organization=self.org, lead__is_test=False)
        if self.f.branch_id:
            qs = qs.filter(slot__group__branch_id=self.f.branch_id)
        elif self.f.allowed_branch_ids:
            qs = qs.filter(slot__group__branch_id__in=self.f.allowed_branch_ids)
        if self.f.course_id:
            qs = qs.filter(slot__group__course_id=self.f.course_id)
        if self.f.source:
            qs = qs.filter(lead__source=self.f.source)
        return qs

    def enrollments(self):
        qs = Enrollment.objects.filter(organization=self.org, status=Enrollment.Status.CONFIRMED, lead__is_test=False)
        if self.f.branch_id:
            qs = qs.filter(Q(group__branch_id=self.f.branch_id) | Q(group__isnull=True, lead__branch_id=self.f.branch_id))
        elif self.f.allowed_branch_ids:
            qs = qs.filter(Q(group__branch_id__in=self.f.allowed_branch_ids) | Q(group__isnull=True, lead__branch_id__in=self.f.allowed_branch_ids))
        if self.f.course_id:
            qs = qs.filter(course_id=self.f.course_id)
        if self.f.source:
            qs = qs.filter(lead__source=self.f.source)
        return qs

    # ------------------------------------------------------------------ buckets
    def bucket_keys(self, d_from: date | None = None, d_to: date | None = None) -> list[date]:
        d_from, d_to = d_from or self.f.date_from, d_to or self.f.date_to
        if self.f.granularity == "week":
            first = d_from - timedelta(days=d_from.weekday())
            keys, cur = [], first
            while cur <= d_to:
                keys.append(cur)
                cur += timedelta(days=7)
            return keys
        return [d_from + timedelta(days=i) for i in range((d_to - d_from).days + 1)]

    def bucket_of(self, dt: datetime) -> date:
        d = timezone.localtime(dt, self.tz).date()
        if self.f.granularity == "week":
            return d - timedelta(days=d.weekday())
        return d

    def _trunc(self, field: str):
        return TruncWeek(field, tzinfo=self.tz) if self.f.granularity == "week" else TruncDate(field, tzinfo=self.tz)

    def count_series(self, qs, field: str, start: datetime, end: datetime, keys: list[date]) -> list[int]:
        rows = (
            qs.filter(**{f"{field}__gte": start, f"{field}__lt": end})
            .order_by()
            .annotate(b=self._trunc(field))
            .values("b")
            .annotate(c=Count("id", distinct=True))
        )
        counts = {}
        for r in rows:
            b = r["b"]
            if isinstance(b, datetime):
                b = b.date()
            counts[b] = counts.get(b, 0) + r["c"]
        return [counts.get(k, 0) for k in keys]

    # ------------------------------------------------------------------ KPI computations
    def _count(self, qs, field, start, end) -> int:
        return qs.filter(**{f"{field}__gte": start, f"{field}__lt": end}).count()

    def _attended_qs(self):
        return self.bookings().filter(status=TrialBooking.Status.ATTENDED)

    def conversion(self, start, end) -> tuple[float | None, int, int]:
        cohort = self.leads().filter(created_at__gte=start, created_at__lt=end)
        denominator = cohort.count()
        if denominator == 0:
            return None, 0, 0
        numerator = cohort.filter(trial_bookings__confirmed_at__lt=end).distinct().count()
        return round(numerator * 100.0 / denominator, 1), numerator, denominator

    def _first_response_pairs(self, start, end) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float]]]:
        convs = self.conversations().filter(created_at__gte=start, created_at__lt=end)
        first_customer = (
            Message.objects.filter(conversation=OuterRef("pk"), sender=Message.Sender.CUSTOMER).order_by("created_at", "id").values("created_at")[:1]
        )
        annotated = convs.annotate(first_customer=Subquery(first_customer)).filter(first_customer__isnull=False)
        first_ai = (
            Message.objects.filter(conversation=OuterRef("pk"), sender=Message.Sender.AI, created_at__gte=OuterRef("first_customer"))
            .order_by("created_at", "id")
            .values("created_at")[:1]
        )
        ai_pairs = []
        for c in annotated.annotate(first_ai=Subquery(first_ai)).values("first_customer", "first_ai"):
            if c["first_ai"]:
                ai_pairs.append((c["first_customer"], (c["first_ai"] - c["first_customer"]).total_seconds()))

        handoffs = HumanHandoff.objects.filter(conversation__in=self.conversations(), created_at__gte=start, created_at__lt=end).exclude(
            requested_via=HumanHandoff.Via.OPERATOR
        )
        trigger = (
            Message.objects.filter(conversation=OuterRef("conversation"), sender=Message.Sender.CUSTOMER, created_at__lte=OuterRef("created_at"))
            .order_by("-created_at", "-id")
            .values("created_at")[:1]
        )
        op_pairs = []
        for h in handoffs.annotate(trigger_at=Subquery(trigger)).values("conversation_id", "created_at", "trigger_at"):
            t0 = h["trigger_at"] or h["created_at"]
            first_op = (
                Message.objects.filter(conversation_id=h["conversation_id"], sender=Message.Sender.OPERATOR, created_at__gte=t0)
                .order_by("created_at", "id")
                .values_list("created_at", flat=True)
                .first()
            )
            if first_op:
                op_pairs.append((t0, (first_op - t0).total_seconds()))
        return ai_pairs, op_pairs

    @staticmethod
    def _median(values: list[float]) -> float | None:
        return round(statistics.median(values), 1) if values else None

    def _kpi_values(self, start, end) -> dict:
        conv, num, den = self.conversion(start, end)
        ai_pairs, op_pairs = self._first_response_pairs(start, end)
        return {
            "new_leads": self._count(self.leads(), "created_at", start, end),
            "new_conversations": self._count(self.conversations(), "created_at", start, end),
            "confirmed_bookings": self._count(self.bookings(), "confirmed_at", start, end),
            "attended": self._count(self._attended_qs(), "slot__starts_at", start, end),
            "enrolled": self._count(self.enrollments(), "confirmed_at", start, end),
            "conversion_rate": conv,
            "conversion_numerator": num,
            "conversion_denominator": den,
            "ai_first_response_median": self._median([v for _, v in ai_pairs]),
            "operator_first_response_median": self._median([v for _, v in op_pairs]),
            "ai_first_response_samples": len(ai_pairs),
            "operator_first_response_samples": len(op_pairs),
        }

    def _sparklines(self, keys: list[date]) -> dict:
        start, end = self.start, self.end
        series = {
            "new_leads": self.count_series(self.leads(), "created_at", start, end, keys),
            "new_conversations": self.count_series(self.conversations(), "created_at", start, end, keys),
            "confirmed_bookings": self.count_series(self.bookings(), "confirmed_at", start, end, keys),
            "attended": self.count_series(self._attended_qs(), "slot__starts_at", start, end, keys),
            "enrolled": self.count_series(self.enrollments(), "confirmed_at", start, end, keys),
        }
        # Konversiya: har bir bucket kohortasi, davr oxirigacha bron olganlar ulushi
        cohort = (
            self.leads()
            .filter(created_at__gte=start, created_at__lt=end)
            .annotate(first_booking=Min("trial_bookings__confirmed_at", filter=Q(trial_bookings__confirmed_at__lt=end)))
            .values("created_at", "first_booking")
        )
        den = dict.fromkeys(keys, 0)
        num = dict.fromkeys(keys, 0)
        for row in cohort:
            b = self.bucket_of(row["created_at"])
            if b in den:
                den[b] += 1
                if row["first_booking"]:
                    num[b] += 1
        series["conversion_rate"] = [round(num[k] * 100.0 / den[k], 1) if den[k] else None for k in keys]
        ai_pairs, op_pairs = self._first_response_pairs(start, end)
        for key, pairs in (("ai_first_response_median", ai_pairs), ("operator_first_response_median", op_pairs)):
            buckets: dict[date, list[float]] = {k: [] for k in keys}
            for t0, v in pairs:
                b = self.bucket_of(t0)
                if b in buckets:
                    buckets[b].append(v)
            series[key] = [self._median(buckets[k]) for k in keys]
        return series

    def kpis(self) -> list[dict]:
        current = self._kpi_values(self.start, self.end)
        previous = self._kpi_values(self.prev_start, self.prev_end)
        keys = self.bucket_keys()
        sparks = self._sparklines(keys)
        result = []
        for key in KPI_KEYS:
            cur, prev = current[key], previous[key]
            unit = "percent" if key == "conversion_rate" else ("seconds" if key.endswith("_median") else "count")
            change, change_unit, no_prev = None, "percent", False
            if key == "conversion_rate":
                change_unit = "pp"
                if prev is None or cur is None:
                    no_prev = prev is None
                else:
                    change = round(cur - prev, 1)
            else:
                if prev in (None, 0):
                    no_prev = True
                elif cur is not None:
                    change = round((cur - prev) * 100.0 / prev, 1)
            item = {
                "key": key,
                "label": KPI_LABELS[key],
                "value": cur,
                "previous": prev,
                "change": change,
                "change_unit": change_unit,
                "no_previous_data": no_prev,
                "unit": unit,
                "lower_is_better": key.endswith("_median"),
                "sparkline": [{"bucket": k.isoformat(), "value": v} for k, v in zip(keys, sparks[key], strict=True)],
            }
            if key == "conversion_rate":
                item["numerator"] = current["conversion_numerator"]
                item["denominator"] = current["conversion_denominator"]
                item["definition"] = (
                    "Davrda yaratilgan noyob mijozlar ichida davr oxirigacha kamida bitta tasdiqlangan sinov broni "
                    "olganlar ulushi (bron olganlar / davrda yaratilgan mijozlar)."
                )
            if key.endswith("_median"):
                item["samples"] = current[key.replace("_median", "_samples")]
            result.append(item)
        return result

    # ------------------------------------------------------------------ charts
    def timeseries(self) -> list[dict]:
        keys = self.bucket_keys()
        leads = self.count_series(self.leads(), "created_at", self.start, self.end, keys)
        bookings = self.count_series(self.bookings(), "confirmed_at", self.start, self.end, keys)
        cancelled = self.count_series(self.bookings().filter(cancelled_at__isnull=False), "cancelled_at", self.start, self.end, keys)
        out = []
        for i, k in enumerate(keys):
            bucket_end = k + timedelta(days=6 if self.f.granularity == "week" else 0)
            out.append(
                {
                    "bucket": k.isoformat(),
                    "bucket_end": min(bucket_end, self.f.date_to).isoformat(),
                    "bucket_start": max(k, self.f.date_from).isoformat(),
                    "new_leads": leads[i],
                    "confirmed_bookings": bookings[i],
                    "cancelled_bookings": cancelled[i],
                }
            )
        return out

    def channels(self) -> list[dict]:
        rows = (
            self.conversations()
            .filter(created_at__gte=self.start, created_at__lt=self.end)
            .order_by()
            .values("channel")
            .annotate(count=Count("id"))
            .order_by("channel")
        )
        counts = {r["channel"]: r["count"] for r in rows}
        labels = dict(Conversation.Channel.choices)
        return [{"channel": ch, "label": labels[ch], "count": counts.get(ch, 0)} for ch in ("telegram", "webchat")]

    def sources(self) -> list[dict]:
        rows = self.leads().filter(created_at__gte=self.start, created_at__lt=self.end).order_by().values("source").annotate(count=Count("id"))
        counts = {r["source"]: r["count"] for r in rows}
        return [{"source": s, "label": label, "count": counts.get(s, 0)} for s, label in Lead.Source.choices]

    def courses(self) -> list[dict]:
        interest = dict(
            self.leads()
            .filter(created_at__gte=self.start, created_at__lt=self.end, interested_course__isnull=False)
            .order_by()
            .values_list("interested_course_id")
            .annotate(c=Count("id"))
        )
        booked = dict(
            self.bookings()
            .filter(confirmed_at__gte=self.start, confirmed_at__lt=self.end)
            .order_by()
            .values_list("slot__group__course_id")
            .annotate(c=Count("id"))
        )
        qs = Course.objects.filter(organization=self.org).order_by("name")
        if self.f.course_id:
            qs = qs.filter(pk=self.f.course_id)
        return [
            {"course_id": c.id, "name": c.name, "interest": interest.get(c.id, 0), "bookings": booked.get(c.id, 0)}
            for c in qs
            if c.is_active or interest.get(c.id) or booked.get(c.id)
        ]

    def _cohort_stage_map(self) -> dict[int, int]:
        """Kohortadagi har bir lead erishgan eng yuqori bosqich (hodisalar tarixidan, davr oxirigacha)."""

        cohort_ids = list(self.leads().filter(created_at__gte=self.start, created_at__lt=self.end).values_list("id", flat=True))
        stage = dict.fromkeys(cohort_ids, 0)
        if not cohort_ids:
            return stage
        for lead_id, to_status in LeadStatusChange.objects.filter(lead_id__in=cohort_ids, created_at__lt=self.end).values_list("lead_id", "to_status"):
            idx = STATUS_STAGE_INDEX.get(to_status)
            if idx is not None and idx > stage[lead_id]:
                stage[lead_id] = idx
        for lead_id in TrialBooking.objects.filter(lead_id__in=cohort_ids, confirmed_at__lt=self.end).values_list("lead_id", flat=True):
            stage[lead_id] = max(stage[lead_id], 2)
        for lead_id in BookingEvent.objects.filter(
            booking__lead_id__in=cohort_ids, event_type=BookingEvent.Type.ATTENDED, occurred_at__lt=self.end
        ).values_list("booking__lead_id", flat=True):
            stage[lead_id] = max(stage[lead_id], 3)
        for lead_id in Enrollment.objects.filter(lead_id__in=cohort_ids, status=Enrollment.Status.CONFIRMED, confirmed_at__lt=self.end).values_list(
            "lead_id", flat=True
        ):
            stage[lead_id] = max(stage[lead_id], 4)
        return stage

    def funnel(self) -> list[dict]:
        stage = self._cohort_stage_map()
        total = len(stage)
        out = []
        for idx, (key, label) in enumerate(STAGES):
            count = sum(1 for v in stage.values() if v >= idx)
            out.append({"stage": key, "label": label, "count": count, "rate": round(count * 100.0 / total, 1) if total else None})
        return out

    def booking_statuses(self) -> list[dict]:
        rows = self.bookings().filter(confirmed_at__gte=self.start, confirmed_at__lt=self.end).order_by().values("status").annotate(count=Count("id"))
        counts = {r["status"]: r["count"] for r in rows}
        return [{"status": s, "label": label, "count": counts.get(s, 0)} for s, label in TrialBooking.Status.choices]

    def upcoming_bookings(self, limit: int = 6) -> list[dict]:
        now = timezone.now()
        qs = (
            self.bookings()
            .filter(status=TrialBooking.Status.CONFIRMED, slot__starts_at__gte=now)
            .select_related("lead", "slot__group__course", "slot__group__branch")
            .order_by("slot__starts_at")[:limit]
        )
        return [
            {
                "booking_id": b.id,
                "lead_id": b.lead_id,
                "lead_name": b.lead.display_name,
                "course": b.slot.group.course.name,
                "branch": b.slot.group.branch.name,
                "starts_at": timezone.localtime(b.slot.starts_at, self.tz).isoformat(),
                "channel": b.channel,
            }
            for b in qs
        ]

    def recent_activity(self, limit: int = 8) -> list[dict]:
        qs = AuditEvent.objects.filter(organization=self.org).select_related("actor").order_by("-created_at", "-id")[:limit]
        return [
            {
                "id": e.id,
                "action": e.action,
                "summary": e.summary,
                "actor_type": e.actor_type,
                "actor_name": e.actor.full_name if e.actor else None,
                "created_at": timezone.localtime(e.created_at, self.tz).isoformat(),
            }
            for e in qs
        ]

    def overview(self) -> dict:
        return {
            "filters": self.f.as_dict(),
            "period": {
                "start": self.start.isoformat(),
                "end": self.end.isoformat(),
                "previous_from": self.prev_from.isoformat(),
                "previous_to": self.prev_to.isoformat(),
                "timezone": str(self.tz),
            },
            "kpis": self.kpis(),
            "timeseries": self.timeseries(),
            "channels": self.channels(),
            "sources": self.sources(),
            "courses": self.courses(),
            "funnel": self.funnel(),
            "booking_statuses": self.booking_statuses(),
            "upcoming_bookings": self.upcoming_bookings(),
            "recent_activity": self.recent_activity(),
            "has_data": self.leads().exists() or self.bookings().exists(),
        }

    # ------------------------------------------------------------------ drill-down
    def _bucket_range(self, bucket: str | None) -> tuple[datetime, datetime]:
        if not bucket:
            return self.start, self.end
        try:
            d = date.fromisoformat(bucket)
        except ValueError:
            raise BusinessError("invalid_bucket", "Noto'g'ri sana.", status_code=400) from None
        d_end = d + timedelta(days=6 if self.f.granularity == "week" else 0)
        s, e = self.bounds(max(d, self.f.date_from), min(d_end, self.f.date_to))
        return s, e

    def details(
        self,
        metric: str,
        *,
        bucket: str | None = None,
        channel: str | None = None,
        status: str | None = None,
        stage: str | None = None,
        course_id: int | None = None,
    ):
        s, e = self._bucket_range(bucket)
        if metric == "new_leads":
            qs = self.leads().filter(created_at__gte=s, created_at__lt=e)
            if course_id:
                qs = qs.filter(interested_course_id=course_id)
            return "leads", qs.select_related("interested_course", "branch", "assigned_to").order_by("-created_at")
        if metric == "sources":
            return "leads", self.leads().filter(created_at__gte=s, created_at__lt=e, source=status or "").select_related(
                "interested_course", "branch"
            ).order_by("-created_at")
        if metric in ("confirmed_bookings", "booking_status", "course_bookings"):
            qs = self.bookings().filter(confirmed_at__gte=s, confirmed_at__lt=e)
            if status:
                qs = qs.filter(status=status)
            if course_id:
                qs = qs.filter(slot__group__course_id=course_id)
            return "bookings", qs.select_related("lead", "slot__group__course", "slot__group__branch").order_by("-confirmed_at")
        if metric == "cancelled_bookings":
            qs = self.bookings().filter(cancelled_at__gte=s, cancelled_at__lt=e)
            return "bookings", qs.select_related("lead", "slot__group__course", "slot__group__branch").order_by("-cancelled_at")
        if metric == "attended":
            qs = self._attended_qs().filter(slot__starts_at__gte=s, slot__starts_at__lt=e)
            return "bookings", qs.select_related("lead", "slot__group__course", "slot__group__branch").order_by("-slot__starts_at")
        if metric == "enrolled":
            ids = self.enrollments().filter(confirmed_at__gte=s, confirmed_at__lt=e).values_list("lead_id", flat=True)
            return "leads", self.leads().model.objects.filter(pk__in=ids).select_related("interested_course", "branch").order_by("-created_at")
        if metric in ("conversations", "new_conversations"):
            qs = self.conversations().filter(created_at__gte=s, created_at__lt=e)
            if channel:
                qs = qs.filter(channel=channel)
            return "conversations", qs.select_related("lead", "assigned_to").order_by("-created_at")
        if metric == "funnel":
            stage_index = {k: i for i, (k, _) in enumerate(STAGES)}.get(stage or "lead")
            if stage_index is None:
                raise BusinessError("invalid_stage", "Noma'lum bosqich.", status_code=400)
            ids = [lid for lid, v in self._cohort_stage_map().items() if v >= stage_index]
            return "leads", Lead.objects.filter(pk__in=ids).select_related("interested_course", "branch").order_by("-created_at")
        if metric == "course_interest":
            qs = self.leads().filter(created_at__gte=s, created_at__lt=e, interested_course_id=course_id)
            return "leads", qs.select_related("interested_course", "branch").order_by("-created_at")
        raise BusinessError("invalid_metric", "Noma'lum ko'rsatkich.", status_code=400)


def overview(organization, params, membership=None) -> dict:
    return Analytics(organization, parse_filters(organization, params, membership)).overview()
