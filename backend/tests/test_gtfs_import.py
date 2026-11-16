"""US-01: Import GTFS schedule.

Acceptance criteria (issue #4):
  AC1  On initial import, routes, stops, trips, calendars and scheduled times
       are loaded from the GTFS archive.
  AC2  If the archive has not changed since the last import, the import is skipped.
  AC3  Importing a new version leaves previously imported data unchanged.
"""

import hashlib
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.gtfs.importer import import_feed, parse_gtfs_time
from app.models import (
    Agency,
    FeedVersion,
    Route,
    Service,
    Stop,
    StopTime,
    Trip,
)
from tests.gtfs_fixture import BASE_COUNTS

TABLES = {
    "agencies": Agency,
    "routes": Route,
    "stops": Stop,
    "services": Service,
    "trips": Trip,
    "stop_times": StopTime,
}


def count_rows(session: Session) -> dict[str, int]:
    return {
        name: session.scalar(select(func.count()).select_from(model))
        for name, model in TABLES.items()
    }


def trip_of(session: Session, feed: FeedVersion, trip_id: str) -> Trip:
    return session.scalars(
        select(Trip).where(Trip.feed_version_id == feed.id, Trip.trip_id == trip_id)
    ).one()


# --- parse_gtfs_time ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("00:00:00", 0),
        ("08:05:00", 8 * 3600 + 5 * 60),
        ("8:15:00", 8 * 3600 + 15 * 60),  # GTFS allows a one-digit hour
        ("23:59:59", 86399),
        ("25:10:00", 25 * 3600 + 10 * 60),  # after midnight, same service day
        (" 06:00:00 ", 6 * 3600),
    ],
)
def test_parse_gtfs_time_returns_seconds_since_service_day_start(text, seconds):
    assert parse_gtfs_time(text) == seconds


def test_parse_gtfs_time_empty_means_no_time():
    assert parse_gtfs_time("") is None


@pytest.mark.parametrize("text", ["8:15", "ab:cd:ef", "08:60:00", "08:00:60", "-1:00:00"])
def test_parse_gtfs_time_rejects_malformed_values(text):
    with pytest.raises(ValueError):
        parse_gtfs_time(text)


# --- AC1: initial import -----------------------------------------------------


def test_initial_import_loads_every_table(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    assert feed is not None
    assert count_rows(db_session) == BASE_COUNTS


def test_initial_import_records_the_feed_version(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    assert feed.feed_version == "6.41.1"
    assert feed.sha256 == hashlib.sha256(gtfs_v1.read_bytes()).hexdigest()
    # validity = earliest start_date .. latest end_date in calendar.txt
    assert feed.valid_from == date(2026, 10, 7)
    assert feed.valid_to == date(2027, 1, 5)
    assert feed.imported_at is not None


def test_routes_keep_line_number_type_and_color(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    routes = {
        r.route_id: r
        for r in db_session.scalars(select(Route).where(Route.feed_version_id == feed.id))
    }
    tram, bus = routes["R41"], routes["R112"]
    assert (tram.short_name, tram.route_type, tram.color) == ("41", 0, "E30613")
    assert tram.long_name == "Ghencea - Piata Presei Libere"
    assert (bus.short_name, bus.route_type) == ("112", 3)
    assert bus.color is None
    assert bus.long_name is None
    agency = db_session.get(Agency, tram.agency_pk)
    assert agency.name == "STB SA"


def test_stops_keep_diacritics_and_parent_station(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    stops = {
        s.stop_id: s
        for s in db_session.scalars(select(Stop).where(Stop.feed_version_id == feed.id))
    }
    assert stops["S1"].name == "Piața Unirii"
    assert stops["S1"].parent_stop_pk == stops["P1"].id
    assert stops["S2"].parent_stop_pk == stops["P1"].id
    assert stops["S3"].parent_stop_pk is None
    assert stops["S3"].lat == pytest.approx(44.411)
    assert stops["S3"].lon == pytest.approx(26.042)


def test_services_keep_running_days_and_dates(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    weekdays = db_session.scalars(
        select(Service).where(Service.feed_version_id == feed.id, Service.service_id == "LV")
    ).one()
    days = [
        weekdays.monday, weekdays.tuesday, weekdays.wednesday, weekdays.thursday,
        weekdays.friday, weekdays.saturday, weekdays.sunday,
    ]
    assert days == [True, True, True, True, True, False, False]
    assert (weekdays.start_date, weekdays.end_date) == (date(2026, 10, 7), date(2027, 1, 5))


def test_trips_link_to_their_route_and_service(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    trip = trip_of(db_session, feed, "T41_D_1")
    assert db_session.get(Route, trip.route_pk).route_id == "R41"
    assert db_session.get(Service, trip.service_pk).service_id == "D"
    assert trip.headsign == "Ghencea"
    assert trip.direction_id == 1


def test_stop_times_keep_order_stop_and_times_past_midnight(db_session, gtfs_v1):
    feed = import_feed(db_session, gtfs_v1)

    trip = trip_of(db_session, feed, "T41_LV_1")
    rows = db_session.scalars(
        select(StopTime).where(StopTime.trip_pk == trip.id).order_by(StopTime.stop_sequence)
    ).all()

    assert [db_session.get(Stop, r.stop_pk).stop_id for r in rows] == ["S3", "S1", "S2"]
    assert (rows[0].arrival_seconds, rows[0].departure_seconds) == (90000, 90030)
    assert rows[2].arrival_seconds == 90600  # 25:10:00
    # non-timepoint stop: no time in the archive, stored as NULL (interpolated in US-03)
    assert rows[1].arrival_seconds is None
    assert rows[1].departure_seconds is None


# --- AC2: unchanged archive is skipped -----------------------------------------


def test_same_archive_is_not_imported_twice(db_session, gtfs_v1):
    import_feed(db_session, gtfs_v1)
    before = count_rows(db_session)

    second = import_feed(db_session, gtfs_v1)

    assert second is None
    assert count_rows(db_session) == before
    assert db_session.scalar(select(func.count()).select_from(FeedVersion)) == 1


# --- AC3: a new version does not change existing data --------------------------


def test_new_version_is_added_next_to_the_old_one(db_session, gtfs_v1, gtfs_v2):
    first = import_feed(db_session, gtfs_v1)
    second = import_feed(db_session, gtfs_v2)

    assert second is not None
    assert second.id != first.id
    assert second.feed_version == "6.42.0"
    # v2 = v1 + line 133 (1 route, 1 trip, 2 stop times)
    v2_routes = db_session.scalar(
        select(func.count()).select_from(Route).where(Route.feed_version_id == second.id)
    )
    assert v2_routes == BASE_COUNTS["routes"] + 1


def test_new_version_leaves_previous_version_unchanged(db_session, gtfs_v1, gtfs_v2):
    first = import_feed(db_session, gtfs_v1)
    old_trip = trip_of(db_session, first, "T41_LV_1")
    old_snapshot = (old_trip.id, old_trip.route_pk, old_trip.service_pk)

    import_feed(db_session, gtfs_v2)
    db_session.expire_all()

    for name, model in TABLES.items():
        if name == "stop_times":
            continue  # no feed_version_id column; checked through the trip below
        v1_rows = db_session.scalar(
            select(func.count()).select_from(model).where(model.feed_version_id == first.id)
        )
        assert v1_rows == BASE_COUNTS[name], name
    old_trip = trip_of(db_session, first, "T41_LV_1")
    assert (old_trip.id, old_trip.route_pk, old_trip.service_pk) == old_snapshot
    old_times = db_session.scalar(
        select(func.count()).select_from(StopTime).where(StopTime.trip_pk == old_trip.id)
    )
    assert old_times == 3
