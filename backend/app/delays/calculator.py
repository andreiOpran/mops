"""Delay of every recorded arrival against its scheduled time (US-03)."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.delays.schedule import interpolate, scheduled_at
from app.models import Arrival, FeedVersion, StopTime, Trip


@dataclass(frozen=True)
class DelayStats:
    updated: int  # arrivals that got their delay in this run
    first_stop: int  # matched, but at the first stop of the trip: no delay (decision 8)
    unmatched: int  # arrivals still without delay (trip or stop not in the schedule)


@dataclass(frozen=True)
class _Pending:
    id: int
    service_date: date
    trip_id: str
    stop_sequence: int
    observed_at: datetime


def compute_delays(session: Session) -> DelayStats:
    """Fill feed_version_id, scheduled_at and delay_seconds for the arrivals
    that don't have them yet. Arrivals already computed are not touched, so
    a later schedule version never changes a delay recorded earlier."""
    pending = [
        _Pending(*row)
        for row in session.execute(
            select(
                Arrival.id,
                Arrival.service_date,
                Arrival.trip_id,
                Arrival.stop_sequence,
                Arrival.observed_at,
            ).where(Arrival.scheduled_at.is_(None))
        )
    ]

    by_version: dict[int, list[_Pending]] = defaultdict(list)
    pick_version = _version_picker(session)
    for arrival in pending:
        version = pick_version(arrival.observed_at)
        if version is not None:
            by_version[version].append(arrival)

    updates = []
    first_stops = 0
    for version, arrivals in by_version.items():
        schedule, first = _trip_times(session, version, {arrival.trip_id for arrival in arrivals})
        for arrival in arrivals:
            stop = (arrival.trip_id, arrival.stop_sequence)
            seconds = schedule.get(stop)
            if seconds is None:
                continue
            planned = scheduled_at(arrival.service_date, seconds)
            # Decision 8: vehicles wait at the terminus long before departure,
            # so the first stop is matched (not looked at again) but gets no delay.
            delay = None if stop in first else round((arrival.observed_at - planned).total_seconds())
            first_stops += delay is None
            updates.append(
                {
                    "id": arrival.id,
                    "feed_version_id": version,
                    "scheduled_at": planned,
                    "delay_seconds": delay,
                }
            )

    if updates:
        session.execute(update(Arrival), updates)
    updated = len(updates) - first_stops
    return DelayStats(updated=updated, first_stop=first_stops, unmatched=len(pending) - len(updates))


def _version_picker(session: Session):
    """Decision 5: an arrival uses the timetable downloaded last before it.

    Arrivals older than every download use the oldest timetable. Versions
    imported by hand (no collector file name) count from their import time.
    """
    downloaded = func.coalesce(FeedVersion.retrieved_at, FeedVersion.imported_at)
    versions = session.execute(
        select(downloaded, FeedVersion.id).order_by(downloaded, FeedVersion.id)
    ).all()
    moments = [moment for moment, _ in versions]
    ids = [version_id for _, version_id in versions]

    def pick(observed_at: datetime) -> int | None:
        if not ids:
            return None
        return ids[max(bisect_right(moments, observed_at) - 1, 0)]

    return pick


def _trip_times(
    session: Session, version: int, trip_ids: set[str]
) -> tuple[dict[tuple[str, int], int], set[tuple[str, int]]]:
    """Scheduled seconds of every stop of these trips in one timetable version,
    with stops that have no time interpolated between their neighbours, and
    the first stop (lowest stop_sequence) of each trip."""
    rows = session.execute(
        select(
            Trip.trip_id,
            StopTime.stop_sequence,
            func.coalesce(StopTime.arrival_seconds, StopTime.departure_seconds),
        )
        .join(StopTime, StopTime.trip_pk == Trip.id)
        .where(Trip.feed_version_id == version, Trip.trip_id.in_(trip_ids))
        .order_by(Trip.trip_id, StopTime.stop_sequence)
    )
    stops: dict[str, list[tuple[int, int | None]]] = defaultdict(list)
    for trip_id, sequence, seconds in rows:
        stops[trip_id].append((sequence, seconds))

    times = {}
    first = {(trip_id, trip_stops[0][0]) for trip_id, trip_stops in stops.items()}
    for trip_id, trip_stops in stops.items():
        filled = interpolate([seconds for _, seconds in trip_stops])
        for (sequence, _), seconds in zip(trip_stops, filled):
            if seconds is not None:
                times[trip_id, sequence] = seconds
    return times, first
