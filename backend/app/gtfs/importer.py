"""GTFS schedule importer (US-01)."""

import csv
import hashlib
import io
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import bindparam, insert, select, update
from sqlalchemy.orm import Session

from app.models import Agency, FeedVersion, Route, Service, Stop, StopTime, Trip

_TIME = re.compile(r"(\d+):(\d{2}):(\d{2})")


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


def import_feed(session: Session, zip_path: Path) -> FeedVersion | None:
    """Import one GTFS archive as a new feed version.

    Returns the new FeedVersion, or None if this exact archive (same sha256)
    was already imported.
    """
    sha256 = hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()
    if session.scalar(select(FeedVersion.id).where(FeedVersion.sha256 == sha256)):
        return None

    with zipfile.ZipFile(zip_path) as archive:
        calendar = _read(archive, "calendar.txt")
        feed = FeedVersion(
            feed_version=_read(archive, "feed_info.txt")[0]["feed_version"],
            sha256=sha256,
            valid_from=min(_date(row["start_date"]) for row in calendar),
            valid_to=max(_date(row["end_date"]) for row in calendar),
        )
        session.add(feed)
        session.flush()

        agencies = _insert(
            session,
            Agency,
            "agency_id",
            [
                {"feed_version_id": feed.id, "agency_id": row["agency_id"], "name": row["agency_name"]}
                for row in _read(archive, "agency.txt")
            ],
        )

        routes = _insert(
            session,
            Route,
            "route_id",
            [
                {
                    "feed_version_id": feed.id,
                    "agency_pk": agencies[row["agency_id"]],
                    "route_id": row["route_id"],
                    "short_name": row["route_short_name"],
                    "long_name": _empty_to_none(row.get("route_long_name", "")),
                    "route_type": int(row["route_type"]),
                    "color": _empty_to_none(row.get("route_color", "")),
                }
                for row in _read(archive, "routes.txt")
            ],
        )

        stop_rows = _read(archive, "stops.txt")
        stops = _insert(
            session,
            Stop,
            "stop_id",
            [
                {
                    "feed_version_id": feed.id,
                    "stop_id": row["stop_id"],
                    "name": row["stop_name"],
                    "lat": float(row["stop_lat"]),
                    "lon": float(row["stop_lon"]),
                }
                for row in stop_rows
            ],
        )
        parents = [
            {"child": stops[row["stop_id"]], "parent": stops[row["parent_station"]]}
            for row in stop_rows
            if row.get("parent_station")
        ]
        if parents:
            session.execute(
                update(Stop.__table__)
                .where(Stop.__table__.c.id == bindparam("child"))
                .values(parent_stop_pk=bindparam("parent")),
                parents,
            )

        days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        services = _insert(
            session,
            Service,
            "service_id",
            [
                {
                    "feed_version_id": feed.id,
                    "service_id": row["service_id"],
                    **{day: row[day] == "1" for day in days},
                    "start_date": _date(row["start_date"]),
                    "end_date": _date(row["end_date"]),
                }
                for row in calendar
            ],
        )

        trips = _insert(
            session,
            Trip,
            "trip_id",
            [
                {
                    "feed_version_id": feed.id,
                    "trip_id": row["trip_id"],
                    "route_pk": routes[row["route_id"]],
                    "service_pk": services[row["service_id"]],
                    "headsign": _empty_to_none(row.get("trip_headsign", "")),
                    "direction_id": _int_or_none(row.get("direction_id", "")),
                }
                for row in _read(archive, "trips.txt")
            ],
        )

        _copy_stop_times(session, archive, trips, stops)

    return feed


def _copy_stop_times(
    session: Session,
    archive: zipfile.ZipFile,
    trips: dict[str, int],
    stops: dict[str, int],
) -> None:
    """Load stop_times with COPY: ~1.45M rows per version in the real feed."""
    raw = session.connection().connection.driver_connection
    columns = "trip_pk, stop_sequence, stop_pk, arrival_seconds, departure_seconds"
    with raw.cursor() as cursor:
        with cursor.copy(f"COPY {StopTime.__tablename__} ({columns}) FROM STDIN") as copy:
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


def _insert(session: Session, model, code_column: str, rows: list[dict]) -> dict[str, int]:
    """Insert rows and return {GTFS code: internal id}."""
    if not rows:
        return {}
    table = model.__table__
    result = session.execute(
        insert(table).returning(table.c[code_column], table.c.id), rows
    )
    return {code: pk for code, pk in result}


def _iter(archive: zipfile.ZipFile, name: str):
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _read(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    return list(_iter(archive, name))


def _date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _empty_to_none(value: str | None) -> str | None:
    return value or None


def _int_or_none(value: str | None) -> int | None:
    return int(value) if value else None
