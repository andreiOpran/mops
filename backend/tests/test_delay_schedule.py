"""US-03: scheduled times as real moments (issue #6).

  AC2  Trips with GTFS times past 24:00 belong to the right service day.
  AC3  Calculations stay correct across daylight saving time changes.

Bucharest is UTC+2 in winter (EET) and UTC+3 in summer (EEST).
DST ended on 25.10.2026 and started on 29.03.2026.
"""

from datetime import UTC, date, datetime

import pytest

from app.delays.schedule import interpolate, scheduled_at

H = 3600


@pytest.mark.parametrize(
    ("service_date", "seconds", "expected_utc"),
    [
        # winter day (UTC+2): 08:00 local = 06:00 UTC
        (date(2026, 11, 16), 8 * H, datetime(2026, 11, 16, 6, 0, tzinfo=UTC)),
        # summer day (UTC+3): 08:00 local = 05:00 UTC
        (date(2026, 10, 24), 8 * H, datetime(2026, 10, 24, 5, 0, tzinfo=UTC)),
        # DST ends this night: noon is already UTC+2, so 08:00 is still 08:00 local = 06:00 UTC
        (date(2026, 10, 25), 8 * H, datetime(2026, 10, 25, 6, 0, tzinfo=UTC)),
        # DST starts this night: noon is UTC+3, 08:00 local = 05:00 UTC
        (date(2026, 3, 29), 8 * H, datetime(2026, 3, 29, 5, 0, tzinfo=UTC)),
        # past midnight: 25:10 of 16.11 = 01:10 on 17.11 local = 23:10 UTC on 16.11
        (date(2026, 11, 16), 25 * H + 10 * 60, datetime(2026, 11, 16, 23, 10, tzinfo=UTC)),
        # start of the service day
        (date(2026, 11, 16), 0, datetime(2026, 11, 15, 22, 0, tzinfo=UTC)),
    ],
)
def test_scheduled_at_follows_the_gtfs_noon_minus_12h_rule(service_date, seconds, expected_utc):
    assert scheduled_at(service_date, seconds) == expected_utc


def test_scheduled_at_returns_a_utc_moment():
    assert scheduled_at(date(2026, 11, 16), 8 * H).utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    ("times", "expected"),
    [
        ([100, None, 300], [100, 200, 300]),
        ([100, None, None, 400], [100, 200, 300, 400]),
        ([0, None, None, 100], [0, 33, 67, 100]),  # rounded to whole seconds
        ([90000, None, 90600], [90000, 90300, 90600]),  # past midnight
        ([None, 100, 200], [None, 100, 200]),  # nothing before: unknown
        ([100, 200, None], [100, 200, None]),  # nothing after: unknown
        ([100, 200, 300], [100, 200, 300]),
        ([None], [None]),
        ([], []),
    ],
)
def test_interpolate_fills_missing_times_between_known_ones(times, expected):
    assert interpolate(times) == expected
