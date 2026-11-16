"""GTFS schedule importer (US-01)."""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models import FeedVersion


def parse_gtfs_time(value: str) -> int | None:
    """Convert a GTFS time ("H:MM:SS" or "HH:MM:SS", may exceed 24:00) to
    seconds since the start of the service day. Empty -> None."""
    raise NotImplementedError


def import_feed(session: Session, zip_path: Path) -> FeedVersion | None:
    """Import one GTFS archive as a new feed version.

    Returns the new FeedVersion, or None if this exact archive (same sha256)
    was already imported.
    """
    raise NotImplementedError
