"""Builders for test data written straight to the database."""

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Agency,
    Arrival,
    FeedVersion,
    Route,
    Service,
    Stop,
    StopTime,
    Trip,
)
from app.transit import BUCHAREST

TRAM, METRO, BUS = 0, 1, 3


class Schedule:
    """Builds a small schedule version directly in the database."""

    def __init__(self, session: Session, version: str):
        self.session = session
        self.feed = self._add(
            FeedVersion(
                feed_version=version,
                sha256=version.ljust(64, "0"),
                valid_from=date(2026, 10, 7),
                valid_to=date(2027, 1, 5),
            )
        )
        self.agency = self._add(Agency(feed_version_id=self.feed.id, agency_id="1", name="STB SA"))
        self.service = self._add(
            Service(
                feed_version_id=self.feed.id,
                service_id="LV",
                monday=True, tuesday=True, wednesday=True, thursday=True, friday=True,
                saturday=False, sunday=False,
                start_date=date(2026, 10, 7),
                end_date=date(2027, 1, 5),
            )
        )
        self._trips = 0
        self._route_ids: dict[int, str] = {}
        self._stop_sequences: dict[tuple[str, date], int] = {}

    def route(
        self, short_name: str, route_type: int = BUS, long_name: str | None = None, color: str | None = None
    ) -> Route:
        route = self._add(
            Route(
                feed_version_id=self.feed.id,
                agency_pk=self.agency.id,
                route_id=f"R{short_name}",
                short_name=short_name,
                long_name=long_name,
                route_type=route_type,
                color=color,
            )
        )
        self._route_ids[route.id] = route.route_id
        return route

    def stop(self, stop_id: str, name: str, description: str | None = None, parent: Stop | None = None) -> Stop:
        return self._add(
            Stop(
                feed_version_id=self.feed.id,
                stop_id=stop_id,
                name=name,
                description=description,
                lat=44.4,
                lon=26.1,
                parent_stop_pk=parent.id if parent else None,
            )
        )

    def trip(self, route: Route, direction_id: int, headsign: str | None, stops: list[Stop] = ()) -> Trip:
        self._trips += 1
        trip = self._add(
            Trip(
                feed_version_id=self.feed.id,
                trip_id=f"T{self._trips}",
                route_pk=route.id,
                service_pk=self.service.id,
                headsign=headsign,
                direction_id=direction_id,
            )
        )
        for sequence, stop in enumerate(stops):
            self._add(StopTime(trip_pk=trip.id, stop_sequence=sequence, stop_pk=stop.id, arrival_seconds=3600))
        return trip

    def _add(self, row):
        self.session.add(row)
        self.session.flush()
        return row

    def arrival(self, trip: Trip, delay_seconds: int | None, service_date: date) -> Arrival:
        """An observed arrival of `trip`, at the next stop of that trip on that day.

        delay_seconds=None: detected but not yet matched to the timetable, as
        arrival detection saves it before the delay is calculated.
        """
        key = (trip.trip_id, service_date)
        sequence = self._stop_sequences[key] = self._stop_sequences.get(key, -1) + 1
        scheduled_at = datetime.combine(service_date, datetime.min.time(), BUCHAREST) + timedelta(
            hours=8, minutes=sequence
        )
        return self._add(
            Arrival(
                service_date=service_date,
                feed_version_id=None if delay_seconds is None else self.feed.id,
                trip_id=trip.trip_id,
                route_id=self._route_ids[trip.route_pk],
                stop_id=f"S{sequence}",
                stop_sequence=sequence,
                scheduled_at=None if delay_seconds is None else scheduled_at,
                observed_at=scheduled_at + timedelta(seconds=delay_seconds or 0),
                delay_seconds=delay_seconds,
                method="stopped_at",
            )
        )
