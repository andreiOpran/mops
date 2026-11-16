"""Compute the delay of the arrivals stored in the database (US-03).

    python -m app.delays

Run it after `python -m app.gtfs --all` (timetables) and
`python -m app.arrivals ... --save` (arrivals). Only arrivals without a
scheduled time are processed, so it is safe to run on a schedule: delays
already computed are never changed.
Exit code 0 = success, 1 = error.
"""

import argparse
import sys
from collections.abc import Callable, Sequence

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.delays.calculator import compute_delays
from app.models import FeedVersion

SessionFactory = Callable[[], Session]


def main(argv: Sequence[str] | None = None, session_factory: SessionFactory | None = None) -> int:
    _parser().parse_args(argv)
    if session_factory is None:
        from app.db import SessionLocal

        session_factory = SessionLocal

    session = session_factory()
    try:
        if not session.scalar(select(exists().select_from(FeedVersion))):
            print("error: no timetable imported; run python -m app.gtfs first", file=sys.stderr)
            return 1
        stats = compute_delays(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"{stats.updated} delays computed")
    print(f"{stats.first_stop} at the first stop (no delay)")
    print(f"{stats.unmatched} without a match in the timetable")
    return 0


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m app.delays",
        description="Compute the delay of the stored arrivals that don't have one yet.",
    )
