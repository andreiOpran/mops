"""US-03: command line for the delay calculation (issue #6).

    python -m app.delays

Uses the timetable from tests/gtfs_fixture.py (Monday 16.11.2026, UTC+2):
  T112_LV_1: S1 #0 06:00 (first stop), S3 #1 06:07 = 04:07 UTC
"""

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.delays.cli import main
from app.gtfs.importer import import_feed
from app.models import Arrival
from tests.gtfs_fixture import build_gtfs_zip

MONDAY = date(2026, 11, 16)


def at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 11, 16, hour, minute, second, tzinfo=UTC)


def add_arrival(session, trip: str, seq: int, observed: datetime) -> None:
    session.add(
        Arrival(
            service_date=MONDAY,
            trip_id=trip,
            route_id="112",
            stop_id=f"S{seq}",
            stop_sequence=seq,
            observed_at=observed,
            method="stopped_at",
        )
    )
    # already stored, as after `python -m app.arrivals --save`
    session.commit()


def with_timetable_and_arrivals(session, tmp_path) -> None:
    import_feed(session, build_gtfs_zip(tmp_path / "20261029T205111Z_abc.zip", version="6.41"))
    add_arrival(session, "T112_LV_1", 0, at(3, 30))  # first stop: no delay
    add_arrival(session, "T112_LV_1", 1, at(4, 10, 20))  # +200 s
    add_arrival(session, "PV9_UNKNOWN", 3, at(10, 0))  # not in the timetable


def delays(session) -> list[tuple[str, int, int | None]]:
    session.expire_all()
    rows = session.execute(
        select(Arrival.trip_id, Arrival.stop_sequence, Arrival.delay_seconds).order_by(
            Arrival.trip_id, Arrival.stop_sequence
        )
    )
    return [tuple(row) for row in rows]


def test_computes_and_stores_the_delays(db_session, tmp_path):
    with_timetable_and_arrivals(db_session, tmp_path)

    assert main([], session_factory=lambda: db_session) == 0

    assert delays(db_session) == [
        ("PV9_UNKNOWN", 3, None),
        ("T112_LV_1", 0, None),
        ("T112_LV_1", 1, 200),
    ]


def test_prints_a_summary(db_session, tmp_path, capsys):
    with_timetable_and_arrivals(db_session, tmp_path)

    main([], session_factory=lambda: db_session)

    out = capsys.readouterr().out
    assert "1 delays computed" in out
    assert "1 at the first stop (no delay)" in out
    assert "1 without a match in the timetable" in out


def test_running_again_computes_nothing_new(db_session, tmp_path, capsys):
    with_timetable_and_arrivals(db_session, tmp_path)
    main([], session_factory=lambda: db_session)
    capsys.readouterr()

    assert main([], session_factory=lambda: db_session) == 0

    out = capsys.readouterr().out
    assert "0 delays computed" in out
    assert "0 at the first stop" in out
    # still reported, so a missing timetable is noticed
    assert "1 without a match in the timetable" in out


def test_fails_when_no_timetable_was_imported(db_session, capsys):
    add_arrival(db_session, "T112_LV_1", 1, at(4, 10))

    assert main([], session_factory=lambda: db_session) == 1

    assert "python -m app.gtfs" in capsys.readouterr().err
    assert delays(db_session) == [("T112_LV_1", 1, None)]
