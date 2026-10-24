from __future__ import annotations

from datetime import datetime, time

from django.utils import timezone

from apps.ai_agent.models import AISettings
from apps.core.utils import org_tz


def get_ai_settings(organization) -> AISettings:
    obj, _ = AISettings.objects.get_or_create(organization=organization)
    return obj


def _parse_hhmm(value: str, default: time) -> time:
    try:
        hh, mm = str(value).split(":")
        return time(int(hh), int(mm))
    except Exception:  # noqa: BLE001
        return default


def in_working_hours(ai_settings: AISettings, now: datetime | None = None) -> bool:
    now = timezone.localtime(now or timezone.now(), org_tz(ai_settings.organization))
    wh = ai_settings.working_hours or {}
    days = wh.get("days", [0, 1, 2, 3, 4, 5])
    start = _parse_hhmm(wh.get("start", "09:00"), time(9, 0))
    end = _parse_hhmm(wh.get("end", "20:00"), time(20, 0))
    return now.weekday() in days and start <= now.time() < end


def working_hours_label(ai_settings: AISettings, lang: str = "uz") -> str:
    from apps.ai_agent.texts import WEEKDAYS

    wh = ai_settings.working_hours or {}
    names = WEEKDAYS.get(lang, WEEKDAYS["uz"])
    days = sorted(wh.get("days", []))
    if days and days == list(range(days[0], days[-1] + 1)):
        day_label = f"{names[days[0]]}–{names[days[-1]]}"
    else:
        day_label = ", ".join(names[d] for d in days)
    return f"{day_label} {wh.get('start', '09:00')}–{wh.get('end', '20:00')}"
