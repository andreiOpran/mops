"""Turning GTFS schedule times into real moments (US-03)."""

from datetime import date, datetime

TIMEZONE = "Europe/Bucharest"


def scheduled_at(service_date: date, seconds: int) -> datetime:
    """The moment (UTC) of a GTFS time on a service day.

    GTFS rule: times are counted from "noon minus 12 h" of the service day in
    the agency time zone. That is midnight except on the two DST change days,
    and it handles times past 24:00 (25:10:00 = 01:10 the next morning).
    """
    raise NotImplementedError


def interpolate(times: list[int | None]) -> list[int | None]:
    """Fill missing times of a trip (stops in sequence order) linearly between
    the nearest known times before and after. Gaps at the start or the end
    stay None. Results are rounded to whole seconds."""
    raise NotImplementedError
