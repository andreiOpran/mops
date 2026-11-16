"""Arrival detection from Vehicle Positions (US-02a).

The detector is fed one Vehicle Positions snapshot at a time, in time order,
and returns the arrivals it can confirm:

- `stopped_at`: the vehicle is reported STOPPED_AT a stop;
- `sequence_advance`: the vehicle was heading to a stop and is next seen with a
  higher stop sequence, so it passed that stop between two polls.

Stops skipped entirely between two observations are not handled here (US-02b).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum


class VehicleStatus(Enum):
    INCOMING_AT = 0
    STOPPED_AT = 1
    IN_TRANSIT_TO = 2


class ArrivalMethod(Enum):
    STOPPED_AT = "stopped_at"
    SEQUENCE_ADVANCE = "sequence_advance"


@dataclass(frozen=True)
class VehicleObservation:
    """One vehicle in one Vehicle Positions snapshot."""

    vehicle_id: str
    trip_id: str
    route_id: str
    service_date: date  # trip.start_date
    stop_id: str
    stop_sequence: int
    status: VehicleStatus
    timestamp: datetime  # when the vehicle reported this position (UTC)


@dataclass(frozen=True)
class Arrival:
    service_date: date
    trip_id: str
    route_id: str
    stop_id: str
    stop_sequence: int
    observed_at: datetime
    method: ArrivalMethod
    vehicle_id: str


class ArrivalDetector:
    def __init__(self, max_age: timedelta = timedelta(minutes=2)) -> None:
        self.max_age = max_age
        # last fresh observation per trip, keyed by (service_date, trip_id)
        self._last: dict[tuple[date, str], VehicleObservation] = {}
        # arrivals already emitted: (service_date, trip_id, stop_sequence)
        self._seen: set[tuple[date, str, int]] = set()

    def process(self, snapshot_time: datetime, observations: list[VehicleObservation]) -> list[Arrival]:
        """Process one snapshot and return the new arrivals it confirms."""
        arrivals: list[Arrival] = []
        for current in observations:
            if snapshot_time - current.timestamp > self.max_age:
                continue

            trip = (current.service_date, current.trip_id)
            previous = self._last.get(trip)
            if previous is not None:
                if current.stop_sequence < previous.stop_sequence:
                    continue
                if current.stop_sequence > previous.stop_sequence:
                    self._emit(arrivals, previous, current.timestamp, ArrivalMethod.SEQUENCE_ADVANCE, current.vehicle_id)

            if current.status is VehicleStatus.STOPPED_AT:
                self._emit(arrivals, current, current.timestamp, ArrivalMethod.STOPPED_AT, current.vehicle_id)
            self._last[trip] = current
        return arrivals

    def _emit(
        self,
        arrivals: list[Arrival],
        at_stop: VehicleObservation,
        observed_at: datetime,
        method: ArrivalMethod,
        vehicle_id: str,
    ) -> None:
        key = (at_stop.service_date, at_stop.trip_id, at_stop.stop_sequence)
        if key in self._seen:
            return
        self._seen.add(key)
        arrivals.append(
            Arrival(
                service_date=at_stop.service_date,
                trip_id=at_stop.trip_id,
                route_id=at_stop.route_id,
                stop_id=at_stop.stop_id,
                stop_sequence=at_stop.stop_sequence,
                observed_at=observed_at,
                method=method,
                vehicle_id=vehicle_id,
            )
        )
