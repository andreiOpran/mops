"""Turning GTFS schedule times into real moments (US-03)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TIMEZONE = "Europe/Bucharest"
_ZONE = ZoneInfo(TIMEZONE)


def scheduled_at(service_date: date, seconds: int) -> datetime:
    """The moment (UTC) of a GTFS time on a service day.

    GTFS rule: times are counted from "noon minus 12 h" of the service day in
    the agency time zone. That is midnight except on the two DST change days,
    and it handles times past 24:00 (25:10:00 = 01:10 the next morning).
    """
    # Subtract in UTC: arithmetic on a local datetime would keep the wall
    # clock and silently pick up the other offset on DST change days.
    noon = datetime.combine(service_date, time(12), tzinfo=_ZONE).astimezone(UTC)
    return noon - timedelta(hours=12) + timedelta(seconds=seconds)


def interpolate(times: list[int | None]) -> list[int | None]:
    """Fill missing times of a trip (stops in sequence order) linearly between
    the nearest known times before and after. Gaps at the start or the end
    stay None. Results are rounded to whole seconds."""
    result = list(times)
    known = [index for index, value in enumerate(times) if value is not None]
    for before, after in zip(known, known[1:]):
        start, end = times[before], times[after]
        steps = after - before
        for offset in range(1, steps):
            result[before + offset] = round(start + (end - start) * offset / steps)
    return result
