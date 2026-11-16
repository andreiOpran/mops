"""Command line entry point for the GTFS import (US-01)."""

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session


def main(argv: Sequence[str] | None = None, session_factory: Callable[[], Session] | None = None) -> int:
    raise NotImplementedError
