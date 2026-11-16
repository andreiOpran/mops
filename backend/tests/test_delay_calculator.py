"""US-03: delay of each recorded arrival (issue #6).

  AC1  Delay = actual time - scheduled time, in seconds (negative = early).
  AC2  Trips with GTFS times past 24:00 belong to the right service day.
  AC4  A recorded arrival keeps its scheduled time when the timetable changes.

Schedule used (tests/gtfs_fixture.py), all on weekdays (service LV):
  T112_LV_1: S1 #0 06:00, S3 #1 06:07
  T41_LV_1:  S3 #0 25:00, S1 #1 (no time), S2 #2 25:10
Monday 16.11.2026 is winter time (UTC+2): 06:00 local = 04:00 UTC.
"""

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import delete, select

from app.delays.calculator import compute_delays
from app.gtfs.importer import import_feed
from app.models import Arrival, FeedVersion
from tests.gtfs_fixture import build_gtfs_zip

MONDAY = date(2026, 11, 16)
THURSDAY = date(2026, 11, 5)


def utc(day: date, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)


def timetable(session, folder: Path, retrieved: str, minutes_later: int = 0) -> FeedVersion:
    """Import a timetable as the collector names it: <retrieved>_<hash>.zip."""
    archive = build_gtfs_zip(
        folder / f"{retrieved}_{minutes_later:04d}.zip",
        version="6.41",
        bus_112_minutes_later=minutes_later,
    )
    return import_feed(session, archive)


def arrival(session, trip: str, seq: int, observed: datetime, day: date = MONDAY) -> Arrival:
    row = Arrival(
        service_date=day,
        trip_id=trip,
        route_id="41" if trip.startswith("T41") else "112",
        stop_id=f"S{seq}",
        stop_sequence=seq,
        observed_at=observed,
        method="stopped_at",
    )
    session.add(row)
    session.flush()
    return row


def reload(session, row: Arrival) -> Arrival:
    session.expire_all()
    return session.get(Arrival, row.id)


# --- AC1: delay = actual - scheduled ----------------------------------------------


def test_late_arrival_gets_a_positive_delay(db_session, tmp_path):
    feed = timetable(db_session, tmp_path, "20261029T205111Z")
    late = arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 3, 20))

    stats = compute_delays(db_session)

    row = reload(db_session, late)
    assert row.scheduled_at == utc(MONDAY, 4, 0)  # 06:00 local
    assert row.delay_seconds == 200
    assert row.feed_version_id == feed.id
    assert (stats.updated, stats.unmatched) == (1, 0)


def test_early_arrival_gets_a_negative_delay(db_session, tmp_path):
    timetable(db_session, tmp_path, "20261029T205111Z")
    early = arrival(db_session, "T112_LV_1", 1, utc(MONDAY, 4, 6))  # scheduled 06:07 local

    compute_delays(db_session)

    assert reload(db_session, early).delay_seconds == -60


# --- AC2: times past 24:00 --------------------------------------------------------


def test_time_past_midnight_belongs_to_the_service_day(db_session, tmp_path):
    timetable(db_session, tmp_path, "20261029T205111Z")
    # 25:10 on Monday's service = 01:10 Tuesday local = 23:10 UTC Monday
    night = arrival(db_session, "T41_LV_1", 2, utc(MONDAY, 23, 12))

    compute_delays(db_session)

    row = reload(db_session, night)
    assert row.scheduled_at == utc(MONDAY, 23, 10)
    assert row.delay_seconds == 120


def test_stop_without_time_in_the_timetable_is_interpolated(db_session, tmp_path):
    timetable(db_session, tmp_path, "20261029T205111Z")
    # S1 (#1) has no time, between 25:00 and 25:10 -> 25:05 = 23:05 UTC
    middle = arrival(db_session, "T41_LV_1", 1, utc(MONDAY, 23, 5, 30))

    compute_delays(db_session)

    row = reload(db_session, middle)
    assert row.scheduled_at == utc(MONDAY, 23, 5)
    assert row.delay_seconds == 30


# --- which timetable version applies (decision 5: retrieved_at) ------------------


def test_the_timetable_downloaded_last_before_the_arrival_is_used(db_session, tmp_path):
    old = timetable(db_session, tmp_path, "20261029T205111Z")  # 112 at 06:00
    new = timetable(db_session, tmp_path, "20261110T090000Z", minutes_later=10)  # 112 at 06:10
    before_change = arrival(db_session, "T112_LV_1", 0, utc(THURSDAY, 4, 1), day=THURSDAY)
    after_change = arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 11))

    compute_delays(db_session)

    first, second = reload(db_session, before_change), reload(db_session, after_change)
    assert (first.feed_version_id, first.scheduled_at, first.delay_seconds) == (old.id, utc(THURSDAY, 4, 0), 60)
    assert (second.feed_version_id, second.scheduled_at, second.delay_seconds) == (new.id, utc(MONDAY, 4, 10), 60)


def test_arrival_before_the_first_download_uses_the_oldest_timetable(db_session, tmp_path):
    oldest = timetable(db_session, tmp_path, "20261029T205111Z")
    morning = date(2026, 10, 29)  # Thursday, winter time (UTC+2 since 25.10): 06:00 = 04:00 UTC
    row = arrival(db_session, "T112_LV_1", 0, utc(morning, 4, 2), day=morning)

    compute_delays(db_session)

    row = reload(db_session, row)
    assert row.feed_version_id == oldest.id
    assert row.delay_seconds == 120


# --- arrivals that can't be matched ------------------------------------------------


def test_trip_missing_from_the_timetable_stays_without_delay(db_session, tmp_path):
    timetable(db_session, tmp_path, "20261029T205111Z")
    unknown = arrival(db_session, "PV9_UNKNOWN", 3, utc(MONDAY, 10, 0))
    known = arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 0))

    stats = compute_delays(db_session)

    assert reload(db_session, unknown).delay_seconds is None
    assert reload(db_session, unknown).scheduled_at is None
    assert reload(db_session, known).delay_seconds == 0
    assert (stats.updated, stats.unmatched) == (1, 1)


def test_nothing_to_compute_without_a_timetable(db_session):
    arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 0))

    stats = compute_delays(db_session)

    assert (stats.updated, stats.unmatched) == (0, 1)


# --- AC4: a recorded arrival keeps its scheduled time ------------------------------


def test_running_again_changes_nothing(db_session, tmp_path):
    timetable(db_session, tmp_path, "20261029T205111Z")
    arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 3, 20))
    compute_delays(db_session)

    assert compute_delays(db_session).updated == 0


def test_a_later_timetable_does_not_change_delays_already_computed(db_session, tmp_path):
    timetable(db_session, tmp_path, "20261029T205111Z")
    row = arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 3, 20))
    compute_delays(db_session)

    # a new version, downloaded before the arrival, is imported afterwards
    timetable(db_session, tmp_path, "20261110T090000Z", minutes_later=10)
    compute_delays(db_session)

    row = reload(db_session, row)
    assert (row.scheduled_at, row.delay_seconds) == (utc(MONDAY, 4, 0), 200)


def test_deleting_the_timetable_keeps_the_recorded_delay(db_session, tmp_path):
    feed = timetable(db_session, tmp_path, "20261029T205111Z")
    row = arrival(db_session, "T112_LV_1", 0, utc(MONDAY, 4, 3, 20))
    compute_delays(db_session)

    db_session.execute(delete(FeedVersion).where(FeedVersion.id == feed.id))

    row = reload(db_session, row)
    assert (row.scheduled_at, row.delay_seconds) == (utc(MONDAY, 4, 0), 200)
    assert row.feed_version_id is None
    assert db_session.scalar(select(Arrival.id).where(Arrival.id == row.id)) is not None
