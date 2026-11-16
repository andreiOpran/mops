"""GTFS schedule importer (US-01).

Each GTFS archive becomes a new feed version; nothing from earlier versions
is changed. Tables are loaded in dependency order and linked through the
internal ids returned by each insert ({GTFS code: id}).
"""

import csv
import hashlib
import io
import re
import zipfile
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import bindparam, insert, select, update
from sqlalchemy.orm import Session

from app.models import Agency, FeedVersion, Route, Service, Stop, StopTime, Trip

Row = dict[str, str]
IdMap = dict[str, int]

_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_gtfs_time(value: str) -> int | None:
    """Convert a GTFS time ("H:MM:SS" or "HH:MM:SS", may exceed 24:00) to
    seconds since the start of the service day. Empty -> None."""
    value = value.strip()
    if not value:
        return None
    match = _TIME.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid GTFS time: {value!r}")
    hours, minutes, seconds = (int(part) for part in match.groups())
    if minutes > 59 or seconds > 59:
        raise ValueError(f"invalid GTFS time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def retrieved_at_from_name(path: Path) -> datetime | None:
    """Download time encoded by the collector in the archive name
    (<YYYYMMDDTHHMMSSZ>_<hash>.zip, UTC). None for any other name."""
    raise NotImplementedError


def import_feed(session: Session, zip_path: Path) -> FeedVersion | None:
    """Import one GTFS archive as a new feed version.

    Returns the new FeedVersion, or None if this exact archive (same sha256)
    was already imported. Does not commit: the caller owns the transaction,
    so a failed import leaves nothing behind.
    """
    sha256 = _sha256(zip_path)
    if session.scalar(select(FeedVersion.id).where(FeedVersion.sha256 == sha256)):
        return None

    with zipfile.ZipFile(zip_path) as archive:
        calendar = _read(archive, "calendar.txt")
        feed = _create_feed_version(session, archive, sha256, calendar)

        agencies = _import_agencies(session, feed.id, archive)
        routes = _import_routes(session, feed.id, archive, agencies)
        stops = _import_stops(session, feed.id, archive)
        services = _import_services(session, feed.id, calendar)
        trips = _import_trips(session, feed.id, archive, routes, services)
        _import_stop_times(session, archive, trips, stops)

    return feed


# --- one function per table, in dependency order -------------------------------


def _create_feed_version(
    session: Session, archive: zipfile.ZipFile, sha256: str, calendar: list[Row]
) -> FeedVersion:
    feed = FeedVersion(
        feed_version=_read(archive, "feed_info.txt")[0]["feed_version"],
        sha256=sha256,
        valid_from=min(_date(row["start_date"]) for row in calendar),
        valid_to=max(_date(row["end_date"]) for row in calendar),
    )
    session.add(feed)
    session.flush()  # assigns feed.id
    return feed


def _import_agencies(session: Session, feed_id: int, archive: zipfile.ZipFile) -> IdMap:
    rows = [
        {"feed_version_id": feed_id, "agency_id": row["agency_id"], "name": row["agency_name"]}
        for row in _iter(archive, "agency.txt")
    ]
    return _insert(session, Agency, "agency_id", rows)


def _import_routes(
    session: Session, feed_id: int, archive: zipfile.ZipFile, agencies: IdMap
) -> IdMap:
    rows = [
        {
            "feed_version_id": feed_id,
            "agency_pk": agencies[row["agency_id"]],
            "route_id": row["route_id"],
            "short_name": row["route_short_name"],
            "long_name": _text_or_none(row.get("route_long_name")),
            "route_type": int(row["route_type"]),
            "color": _text_or_none(row.get("route_color")),
        }
        for row in _iter(archive, "routes.txt")
    ]
    return _insert(session, Route, "route_id", rows)


def _import_stops(session: Session, feed_id: int, archive: zipfile.ZipFile) -> IdMap:
    """Insert all stops, then link platforms to their parent station.

    Two passes because a platform may appear in stops.txt before its parent.
    """
    source = _read(archive, "stops.txt")
    rows = [
        {
            "feed_version_id": feed_id,
            "stop_id": row["stop_id"],
            "name": row["stop_name"],
            "lat": float(row["stop_lat"]),
            "lon": float(row["stop_lon"]),
        }
        for row in source
    ]
    stops = _insert(session, Stop, "stop_id", rows)

    links = [
        {"child": stops[row["stop_id"]], "parent": stops[row["parent_station"]]}
        for row in source
        if row.get("parent_station")
    ]
    if links:
        table = Stop.__table__
        session.execute(
            update(table)
            .where(table.c.id == bindparam("child"))
            .values(parent_stop_pk=bindparam("parent")),
            links,
        )
    return stops


def _import_services(session: Session, feed_id: int, calendar: list[Row]) -> IdMap:
    rows = [
        {
            "feed_version_id": feed_id,
            "service_id": row["service_id"],
            **{day: row[day] == "1" for day in _WEEKDAYS},
            "start_date": _date(row["start_date"]),
            "end_date": _date(row["end_date"]),
        }
        for row in calendar
    ]
    return _insert(session, Service, "service_id", rows)


def _import_trips(
    session: Session,
    feed_id: int,
    archive: zipfile.ZipFile,
    routes: IdMap,
    services: IdMap,
) -> IdMap:
    rows = [
        {
            "feed_version_id": feed_id,
            "trip_id": row["trip_id"],
            "route_pk": routes[row["route_id"]],
            "service_pk": services[row["service_id"]],
            "headsign": _text_or_none(row.get("trip_headsign")),
            "direction_id": _int_or_none(row.get("direction_id")),
        }
        for row in _iter(archive, "trips.txt")
    ]
    return _insert(session, Trip, "trip_id", rows)


def _import_stop_times(
    session: Session, archive: zipfile.ZipFile, trips: IdMap, stops: IdMap
) -> None:
    """Stream stop_times into PostgreSQL with COPY (~1.45M rows per version)."""
    columns = "trip_pk, stop_sequence, stop_pk, arrival_seconds, departure_seconds"
    sql = f"COPY {StopTime.__tablename__} ({columns}) FROM STDIN"
    raw = session.connection().connection.driver_connection
    with raw.cursor() as cursor, cursor.copy(sql) as copy:
        for row in _iter(archive, "stop_times.txt"):
            copy.write_row(
                (
                    trips[row["trip_id"]],
                    int(row["stop_sequence"]),
                    stops[row["stop_id"]],
                    parse_gtfs_time(row["arrival_time"]),
                    parse_gtfs_time(row["departure_time"]),
                )
            )


# --- helpers ---------------------------------------------------------------------


def _insert(session: Session, model: type, code_column: str, rows: list[dict]) -> IdMap:
    """Insert rows in one batch and return {GTFS code: internal id}."""
    if not rows:
        return {}
    table = model.__table__
    result = session.execute(insert(table).returning(table.c[code_column], table.c.id), rows)
    return {code: pk for code, pk in result}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter(archive: zipfile.ZipFile, name: str) -> Iterator[Row]:
    """Rows of one GTFS file; utf-8-sig drops the BOM the TPBI feed uses."""
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _read(archive: zipfile.ZipFile, name: str) -> list[Row]:
    return list(_iter(archive, name))


def _date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _text_or_none(value: str | None) -> str | None:
    return value or None


def _int_or_none(value: str | None) -> int | None:
    return int(value) if value else None
