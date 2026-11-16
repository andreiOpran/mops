"""US-02a: saving detected arrivals (issue #24).

  AC2  Exactly one arrival per (service date, trip, stop sequence).
  AC3  Reprocessing the same period produces the same arrivals (no duplicates).
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.arrivals.detector import Arrival, ArrivalMethod
from app.arrivals.store import save_arrivals
from app.models import Arrival as ArrivalRow

T0 = datetime(2026, 11, 16, 12, 0, 11, tzinfo=UTC)
DAY = date(2026, 11, 16)


def arrival(seq: int, method: ArrivalMethod = ArrivalMethod.STOPPED_AT, trip: str = "T41", at: datetime = T0) -> Arrival:
    return Arrival(
        service_date=DAY,
        trip_id=trip,
        route_id="41",
        stop_id=f"S{seq}",
        stop_sequence=seq,
        observed_at=at,
        method=method,
        vehicle_id="V1",
    )


def stored(session) -> list[ArrivalRow]:
    return list(session.scalars(select(ArrivalRow).order_by(ArrivalRow.trip_id, ArrivalRow.stop_sequence)))


def test_saves_every_field(db_session):
    assert save_arrivals(db_session, [arrival(5, ArrivalMethod.SEQUENCE_ADVANCE)]) == 1

    row = stored(db_session)[0]
    assert (row.service_date, row.trip_id, row.route_id) == (DAY, "T41", "41")
    assert (row.stop_id, row.stop_sequence) == ("S5", 5)
    assert row.observed_at == T0
    assert row.method == "sequence_advance"
    assert row.vehicle_id == "V1"
    # filled later by the delay calculation (US-03)
    assert (row.feed_version_id, row.scheduled_at, row.delay_seconds) == (None, None, None)


def test_saving_the_same_arrivals_again_adds_nothing(db_session):
    batch = [arrival(5), arrival(6), arrival(1, trip="T112")]
    assert save_arrivals(db_session, batch) == 3

    assert save_arrivals(db_session, batch) == 0

    assert db_session.scalar(select(func.count()).select_from(ArrivalRow)) == 3


def test_an_arrival_already_stored_is_kept_as_it_was(db_session):
    save_arrivals(db_session, [arrival(5)])
    later = replace(arrival(5), observed_at=T0 + timedelta(minutes=3), method=ArrivalMethod.SEQUENCE_ADVANCE)

    assert save_arrivals(db_session, [later, arrival(6)]) == 1

    rows = stored(db_session)
    assert [(r.stop_sequence, r.observed_at, r.method) for r in rows] == [
        (5, T0, "stopped_at"),
        (6, T0, "stopped_at"),
    ]


def test_same_stop_on_another_day_is_another_arrival(db_session):
    next_day = replace(arrival(5), service_date=DAY + timedelta(days=1))

    assert save_arrivals(db_session, [arrival(5), next_day]) == 2


def test_nothing_to_save(db_session):
    assert save_arrivals(db_session, []) == 0
