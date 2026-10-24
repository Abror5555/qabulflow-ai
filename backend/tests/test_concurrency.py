"""3. Oxirgi bo'sh joy uchun parallel so'rovlar va takroriy idempotency key."""

import threading

import pytest
from django.db import connection

from apps.bookings import services as booking_services
from apps.bookings.models import TrialBooking
from apps.core.exceptions import BusinessError
from apps.courses.models import TrialSlot

pytestmark = pytest.mark.django_db(transaction=True)


def _run_parallel(targets):
    barrier = threading.Barrier(len(targets))
    results = [None] * len(targets)

    def worker(i, fn):
        try:
            barrier.wait()
            results[i] = ("ok", fn())
        except BusinessError as exc:
            results[i] = ("error", exc.code)
        except Exception as exc:  # noqa: BLE001
            results[i] = ("exception", repr(exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i, fn)) for i, fn in enumerate(targets)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=30)
    return results


def test_last_seat_parallel(kit):
    slot = kit.slot(capacity=1)
    leads = [kit.lead() for _ in range(6)]
    results = _run_parallel([lambda lead=lead: booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id).booking.id for lead in leads])
    oks = [r for r in results if r[0] == "ok"]
    errors = [r for r in results if r[0] == "error"]
    assert len(oks) == 1, results
    assert all(code == "slot_full" for _, code in errors) and len(errors) == 5
    slot.refresh_from_db()
    assert slot.seats_taken == 1
    assert TrialBooking.objects.filter(slot=slot).count() == 1


def test_multi_seat_parallel(kit):
    slot = kit.slot(capacity=3)
    leads = [kit.lead() for _ in range(8)]
    results = _run_parallel([lambda lead=lead: booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id).booking.id for lead in leads])
    assert sum(1 for r in results if r[0] == "ok") == 3, results
    slot.refresh_from_db()
    assert slot.seats_taken == 3 == TrialBooking.objects.filter(slot=slot).count()


def test_same_idempotency_key_parallel(kit):
    slot = kit.slot(capacity=5)
    lead = kit.lead()
    results = _run_parallel(
        [lambda: booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id, idempotency_key="retry-key-1").booking.id for _ in range(4)]
    )
    ids = {r[1] for r in results if r[0] == "ok"}
    assert len(ids) == 1, results
    assert TrialBooking.objects.filter(lead=lead).count() == 1
    assert TrialSlot.objects.get(pk=slot.pk).seats_taken == 1


def test_same_lead_parallel_without_key(kit):
    slot = kit.slot(capacity=5)
    lead = kit.lead()
    results = _run_parallel([lambda: booking_services.create_trial_booking(kit.org, lead=lead, slot_id=slot.id).booking.id for _ in range(3)])
    assert sum(1 for r in results if r[0] == "ok") == 1
    assert all(r[1] == "already_booked" for r in results if r[0] == "error")
    assert TrialSlot.objects.get(pk=slot.pk).seats_taken == 1
