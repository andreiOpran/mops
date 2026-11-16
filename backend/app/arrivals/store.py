"""Saving detected arrivals to the database (US-02a)."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.arrivals.detector import Arrival
from app.models import Arrival as ArrivalRow

# PostgreSQL accepts at most 65,535 parameters per statement: 8 columns x 5,000 rows fits.
_BATCH = 5_000


def save_arrivals(session: Session, arrivals: list[Arrival]) -> int:
    """Insert arrivals; ones already stored for the same (service_date,
    trip_id, stop_sequence) are kept as they are. Returns how many were new."""
    new = 0
    for start in range(0, len(arrivals), _BATCH):
        rows = [_row(arrival) for arrival in arrivals[start : start + _BATCH]]
        statement = (
            insert(ArrivalRow)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["service_date", "trip_id", "stop_sequence"])
            .returning(ArrivalRow.id)
        )
        new += len(session.execute(statement).all())
    return new


def _row(arrival: Arrival) -> dict:
    return {
        "service_date": arrival.service_date,
        "trip_id": arrival.trip_id,
        "route_id": arrival.route_id,
        "stop_id": arrival.stop_id,
        "stop_sequence": arrival.stop_sequence,
        "observed_at": arrival.observed_at,
        "method": arrival.method.value,
        "vehicle_id": arrival.vehicle_id,
    }
