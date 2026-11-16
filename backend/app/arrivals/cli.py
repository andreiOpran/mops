"""Replay archived Vehicle Positions snapshots through the arrival detector (US-02a).

    python -m app.arrivals <folder> [--csv arrivals.csv] [--save] [--max-age SECONDS]

<folder> is any part of the collector archive (T-01):
raw/vehiclePositions, one day (raw/vehiclePositions/2026-11-16) or one hour.
Snapshots are read from all subfolders in time order: the file names are
UTC timestamps (YYYYMMDDTHHMMSSZ.pb.gz), so name order = time order.
"""

import argparse
import csv
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path

from google.protobuf.message import DecodeError
from sqlalchemy.orm import Session

from app.arrivals.detector import Arrival, ArrivalDetector
from app.arrivals.feed import read_snapshot
from app.arrivals.store import save_arrivals

CSV_FIELDS = [
    "service_date",
    "trip_id",
    "route_id",
    "stop_id",
    "stop_sequence",
    "observed_at",
    "method",
    "vehicle_id",
]


def main(argv: Sequence[str] | None = None, session_factory: Callable[[], Session] | None = None) -> int:
    args = _parser().parse_args(argv)

    snapshots = sorted(args.folder.rglob("*.pb.gz"), key=lambda path: path.name)
    if not snapshots:
        print(f"error: no snapshots (*.pb.gz) in {args.folder}", file=sys.stderr)
        return 1

    detector = ArrivalDetector(max_age=timedelta(seconds=args.max_age))
    arrivals: list[Arrival] = []
    unreadable = 0
    for path in snapshots:
        try:
            snapshot_time, observations = read_snapshot(path)
        except (OSError, EOFError, DecodeError) as error:
            unreadable += 1
            print(f"warning: skipping {path.name}: {error}", file=sys.stderr)
            continue
        arrivals += detector.process(snapshot_time, observations)

    if args.csv:
        _write_csv(args.csv, arrivals)
    new_in_db = _save(session_factory, arrivals) if args.save else None

    by_method = Counter(arrival.method.value for arrival in arrivals)
    print(f"{len(snapshots)} snapshots ({unreadable} unreadable), {len(arrivals)} arrivals")
    for method, count in sorted(by_method.items()):
        print(f"  {method}: {count}")
    if args.csv:
        print(f"written to {args.csv}")
    if new_in_db is not None:
        print(f"{new_in_db} new in the database ({len(arrivals) - new_in_db} already stored)")
    return 0


def _save(session_factory: Callable[[], Session] | None, arrivals: list[Arrival]) -> int:
    """Store the arrivals in one transaction; returns how many were new."""
    if session_factory is None:
        from app.db import SessionLocal

        session_factory = SessionLocal

    session = session_factory()
    try:
        new = save_arrivals(session, arrivals)
        session.commit()
        return new
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _write_csv(path: Path, arrivals: list[Arrival]) -> None:
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for arrival in arrivals:
            writer.writerow(
                {
                    "service_date": arrival.service_date.isoformat(),
                    "trip_id": arrival.trip_id,
                    "route_id": arrival.route_id,
                    "stop_id": arrival.stop_id,
                    "stop_sequence": arrival.stop_sequence,
                    "observed_at": arrival.observed_at.isoformat(),
                    "method": arrival.method.value,
                    "vehicle_id": arrival.vehicle_id,
                }
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.arrivals",
        description="Detect arrivals in archived Vehicle Positions snapshots.",
    )
    parser.add_argument("folder", type=Path, help="collector archive folder (all subfolders are read)")
    parser.add_argument("--csv", type=Path, help="write the arrivals to this CSV file")
    parser.add_argument(
        "--save",
        action="store_true",
        help="store the arrivals in the database (arrivals already stored are kept)",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=120,
        metavar="SECONDS",
        help="ignore positions older than this (default: 120)",
    )
    return parser
