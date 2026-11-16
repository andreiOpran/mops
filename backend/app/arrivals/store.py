"""Saving detected arrivals to the database (US-02a)."""

from sqlalchemy.orm import Session

from app.arrivals.detector import Arrival


def save_arrivals(session: Session, arrivals: list[Arrival]) -> int:
    """Insert arrivals; ones already stored for the same (service_date,
    trip_id, stop_sequence) are kept as they are. Returns how many were new."""
    raise NotImplementedError
