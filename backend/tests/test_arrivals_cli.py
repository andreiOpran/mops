"""US-02a: replay archived Vehicle Positions snapshots and export the arrivals.

    python -m app.arrivals <folder> [--csv arrivals.csv] [--save]

<folder> is any part of the collector archive (raw/vehiclePositions, one day,
one hour); snapshots are read in time order from all subfolders.
"""

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.arrivals.cli import main
from app.models import Arrival as ArrivalRow
from tests.rt_fixture import IN_TRANSIT_TO, STOPPED_AT, write_snapshot

T0 = datetime(2026, 11, 16, 12, 59, 30, tzinfo=UTC)


def poll(n: int) -> datetime:
    return T0 + timedelta(seconds=15 * n)


def make_archive(root: Path) -> Path:
    """3 polls across the 12h -> 13h folder boundary, written out of order.

    Trip A: stopped at 5, then in transit to 6, then stopped at 6 -> 2 arrivals.
    Trip B: in transit to 2, then to 3                            -> 1 arrival.
    """
    write_snapshot(root, poll(2), [("A", 6, STOPPED_AT), ("B", 3, IN_TRANSIT_TO)])
    write_snapshot(root, poll(0), [("A", 5, STOPPED_AT), ("B", 2, IN_TRANSIT_TO)])
    write_snapshot(root, poll(1), [("A", 6, IN_TRANSIT_TO), ("B", 2, IN_TRANSIT_TO)])
    return root


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as file:
        return list(csv.DictReader(file))


def test_replays_snapshots_in_time_order_and_writes_csv(tmp_path, capsys):
    archive = make_archive(tmp_path / "vehiclePositions")
    out = tmp_path / "arrivals.csv"

    assert main([str(archive), "--csv", str(out)]) == 0

    rows = read_csv(out)
    # poll 0: A stopped at 5; poll 1: nothing new; poll 2: A stopped at 6, B passed 2
    assert [(r["trip_id"], r["stop_sequence"], r["method"]) for r in rows] == [
        ("A", "5", "stopped_at"),
        ("A", "6", "stopped_at"),
        ("B", "2", "sequence_advance"),
    ]
    assert "3 snapshots" in capsys.readouterr().out


def test_csv_has_all_arrival_fields(tmp_path):
    archive = make_archive(tmp_path / "vehiclePositions")
    out = tmp_path / "arrivals.csv"

    main([str(archive), "--csv", str(out)])

    first = read_csv(out)[0]
    assert first == {
        "service_date": "2026-11-16",
        "trip_id": "A",
        "route_id": "41",
        "stop_id": "S5",
        "stop_sequence": "5",
        "observed_at": "2026-11-16T12:59:30+00:00",
        "method": "stopped_at",
        "vehicle_id": "veh-A",
    }


def test_summary_counts_arrivals_by_method(tmp_path, capsys):
    archive = make_archive(tmp_path / "vehiclePositions")

    assert main([str(archive)]) == 0

    out = capsys.readouterr().out
    assert "3 arrivals" in out
    assert "stopped_at: 2" in out
    assert "sequence_advance: 1" in out


def test_unreadable_snapshot_is_skipped_and_reported(tmp_path, capsys):
    archive = make_archive(tmp_path / "vehiclePositions")
    broken = archive / "2026-11-16" / "13" / "20261116T130500Z.pb.gz"
    broken.write_bytes(b"not a gzip file")

    assert main([str(archive)]) == 0

    out = capsys.readouterr().out
    assert "3 arrivals" in out
    assert "1 unreadable" in out


def test_folder_without_snapshots_fails(tmp_path, capsys):
    assert main([str(tmp_path)]) == 1

    assert "no snapshots" in capsys.readouterr().err


# --- --save: store the arrivals in the database --------------------------------


def saved(session) -> list[tuple[str, int, str]]:
    rows = session.scalars(select(ArrivalRow).order_by(ArrivalRow.trip_id, ArrivalRow.stop_sequence))
    return [(r.trip_id, r.stop_sequence, r.method) for r in rows]


def test_save_stores_the_arrivals_in_the_database(db_session, tmp_path, capsys):
    archive = make_archive(tmp_path / "vehiclePositions")

    assert main([str(archive), "--save"], session_factory=lambda: db_session) == 0

    assert saved(db_session) == [
        ("A", 5, "stopped_at"),
        ("A", 6, "stopped_at"),
        ("B", 2, "sequence_advance"),
    ]
    assert "3 new in the database" in capsys.readouterr().out


def test_replaying_the_same_period_again_saves_nothing_new(db_session, tmp_path, capsys):
    archive = make_archive(tmp_path / "vehiclePositions")
    main([str(archive), "--save"], session_factory=lambda: db_session)
    capsys.readouterr()

    assert main([str(archive), "--save"], session_factory=lambda: db_session) == 0

    assert db_session.scalar(select(func.count()).select_from(ArrivalRow)) == 3
    assert "0 new in the database" in capsys.readouterr().out


def test_save_and_csv_together(db_session, tmp_path):
    archive = make_archive(tmp_path / "vehiclePositions")
    out = tmp_path / "arrivals.csv"

    main([str(archive), "--save", "--csv", str(out)], session_factory=lambda: db_session)

    assert len(read_csv(out)) == 3
    assert len(saved(db_session)) == 3


def test_without_save_nothing_is_written_to_the_database(db_session, tmp_path):
    archive = make_archive(tmp_path / "vehiclePositions")

    main([str(archive)], session_factory=lambda: db_session)

    assert saved(db_session) == []
