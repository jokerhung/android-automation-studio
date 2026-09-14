from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil.tz import datetime_ambiguous, datetime_exists, gettz

try:
    from admin_console.schemas.schedule_schema import ScheduleRule
except ImportError:
    from apps.admin_console.schemas.schedule_schema import ScheduleRule


def utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)


def _zone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        zone = gettz(name)
        if zone is None:
            raise ValueError(f"IANA timezone is unavailable: {name}")
        return zone


def _valid_local_candidate(day: date, wall: time, zone) -> datetime | None:
    naive = datetime.combine(day, wall)
    candidate = naive.replace(tzinfo=zone, fold=0)
    if not datetime_exists(candidate):
        return None
    return candidate.astimezone(UTC)


def next_occurrence(
    rule: ScheduleRule, *, after: datetime, anchor_at: datetime | None = None
) -> datetime:
    after = _as_utc(after)
    if rule.schedule_type == "interval":
        anchor = _as_utc(anchor_at or after)
        seconds = int(rule.interval_minutes or 0) * 60
        elapsed = (after - anchor).total_seconds()
        steps = max(1, int(elapsed // seconds) + 1)
        return anchor + timedelta(seconds=steps * seconds)

    zone = _zone(rule.timezone)
    wall = datetime.strptime(rule.time_of_day or "", "%H:%M:%S").time()
    local_after = after.astimezone(zone)
    allowed = set(rule.weekdays) if rule.schedule_type == "weekly" else set(range(1, 8))
    for offset in range(0, 370):
        day = local_after.date() + timedelta(days=offset)
        if day.isoweekday() not in allowed:
            continue
        candidate = _valid_local_candidate(day, wall, zone)
        if candidate is not None and candidate > after:
            return candidate
    raise ValueError("no valid occurrence found in the next year")


def preview_occurrences(
    rule: ScheduleRule, *, after: datetime, count: int = 5, anchor_at: datetime | None = None
) -> list[datetime]:
    values: list[datetime] = []
    cursor = _as_utc(after)
    anchor = anchor_at
    for _ in range(count):
        cursor = next_occurrence(rule, after=cursor, anchor_at=anchor)
        values.append(cursor)
        if rule.schedule_type == "interval" and anchor is None:
            anchor = after
    return values
