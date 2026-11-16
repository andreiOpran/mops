"""Command line entry point for the GTFS import (US-01).

Where the archives come from: the collector (T-01) downloads the TPBI GTFS
zip every 6 hours and keeps one copy per distinct version in
/var/lib/stb-collector/static/<UTC timestamp>_<hash>.zip.

    python -m app.gtfs <archive.zip>     import one archive
    python -m app.gtfs --all <folder>    import every *.zip in the folder,
                                         oldest first (e.g. the collector's static/)

Archives already imported are skipped, so --all is safe to run on a schedule:
the first run loads the whole history, later runs only the new versions.
Exit code 0 = success (imported or already present), 1 = error.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from app.gtfs.importer import import_feed

SessionFactory = Callable[[], Session]


def main(argv: Sequence[str] | None = None, session_factory: SessionFactory | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.all:
        archives = _archives_oldest_first(args.all)
        if not archives:
            print(f"error: no GTFS archive (*.zip) in {args.all}", file=sys.stderr)
            return 1
    else:
        if not args.archive.is_file():
            print(f"error: {args.archive} not found", file=sys.stderr)
            return 1
        archives = [args.archive]

    if session_factory is None:
        from app.db import SessionLocal

        session_factory = SessionLocal

    for archive in archives:
        print(_import_one(session_factory, archive))
    return 0


def _import_one(session_factory: SessionFactory, archive: Path) -> str:
    """Import one archive in its own transaction, so earlier versions stay
    imported even if a later archive fails."""
    session = session_factory()
    try:
        feed = import_feed(session, archive)
        # Read the values now: after commit + close the object can't load them.
        if feed is None:
            message = f"{archive.name}: already imported, nothing to do"
        else:
            message = f"{archive.name}: imported {feed.feed_version} (feed_version_id={feed.id})"
        session.commit()
        return message
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.gtfs", description="Import GTFS schedule archives.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("archive", nargs="?", type=Path, help="GTFS .zip to import")
    source.add_argument("--all", type=Path, metavar="FOLDER", help="import every *.zip in FOLDER, oldest first")
    return parser


def _archives_oldest_first(folder: Path) -> list[Path]:
    """Collector archives are named <UTC timestamp>_<hash>.zip: name order = time order."""
    return sorted(folder.glob("*.zip"))
