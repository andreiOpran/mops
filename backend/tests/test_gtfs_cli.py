"""US-01: command line entry point for the GTFS import (python -m app.gtfs)."""

from pathlib import Path

from sqlalchemy import func, select

from app.gtfs.cli import main
from app.models import FeedVersion
from tests.gtfs_fixture import build_gtfs_zip


def versions(session) -> list[str]:
    return list(session.scalars(select(FeedVersion.feed_version).order_by(FeedVersion.id)))


def run(argv, db_session) -> int:
    return main(argv, session_factory=lambda: db_session)


def test_imports_the_given_archive(db_session, gtfs_v1, capsys):
    assert run([str(gtfs_v1)], db_session) == 0

    assert versions(db_session) == ["6.41.1"]
    assert "imported 6.41.1" in capsys.readouterr().out


def test_same_archive_again_is_reported_as_skipped(db_session, gtfs_v1, capsys):
    run([str(gtfs_v1)], db_session)

    assert run([str(gtfs_v1)], db_session) == 0

    assert db_session.scalar(select(func.count()).select_from(FeedVersion)) == 1
    assert "already imported" in capsys.readouterr().out


def make_collector_folder(folder: Path) -> Path:
    """Archives as the collector names them: <UTC timestamp>_<hash>.zip,
    so name order = time order. Created out of order on purpose."""
    build_gtfs_zip(folder / "20261104T210057Z_cccc.zip", version="6.41.1")
    build_gtfs_zip(folder / "20261029T205111Z_aaaa.zip", version="6.40.0")
    build_gtfs_zip(folder / "20261103T150012Z_bbbb.zip", version="6.41.0", extra_route=True)
    (folder / "notes.txt").write_text("not an archive")
    return folder


def test_all_imports_every_archive_oldest_first(db_session, tmp_path: Path, capsys):
    folder = make_collector_folder(tmp_path)

    assert run(["--all", str(folder)], db_session) == 0

    # every version is needed: arrivals since 29.10 use the schedule valid that day
    assert versions(db_session) == ["6.40.0", "6.41.0", "6.41.1"]
    assert capsys.readouterr().out.count("imported") == 3


def test_all_run_again_imports_nothing_new(db_session, tmp_path: Path, capsys):
    folder = make_collector_folder(tmp_path)
    run(["--all", str(folder)], db_session)
    capsys.readouterr()

    assert run(["--all", str(folder)], db_session) == 0

    assert len(versions(db_session)) == 3
    assert capsys.readouterr().out.count("already imported") == 3


def test_all_picks_up_a_new_archive_on_the_next_run(db_session, tmp_path: Path):
    folder = make_collector_folder(tmp_path)
    run(["--all", str(folder)], db_session)

    build_gtfs_zip(folder / "20261120T090000Z_dddd.zip", version="6.42.0")
    assert run(["--all", str(folder)], db_session) == 0

    assert versions(db_session) == ["6.40.0", "6.41.0", "6.41.1", "6.42.0"]


def test_all_on_a_folder_without_archives_fails(db_session, tmp_path: Path, capsys):
    assert run(["--all", str(tmp_path)], db_session) == 1

    assert versions(db_session) == []
    assert "no GTFS archive" in capsys.readouterr().err


def test_missing_file_fails(db_session, tmp_path: Path, capsys):
    assert run([str(tmp_path / "missing.zip")], db_session) == 1

    assert "not found" in capsys.readouterr().err
