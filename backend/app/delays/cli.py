"""Compute the delay of the arrivals stored in the database (US-03).

    python -m app.delays

Run it after `python -m app.gtfs --all` (timetables) and
`python -m app.arrivals ... --save` (arrivals). Only arrivals without a
scheduled time are processed, so it is safe to run on a schedule: delays
already computed are never changed.
Exit code 0 = success, 1 = error.
"""

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

SessionFactory = Callable[[], Session]


def main(argv: Sequence[str] | None = None, session_factory: SessionFactory | None = None) -> int:
    raise NotImplementedError
