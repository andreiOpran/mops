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


def test_latest_imports_the_newest_archive_in_a_folder(db_session, tmp_path: Path):
    # The collector names archives <UTC timestamp>_<hash>.zip, so name order = time order.
    build_gtfs_zip(tmp_path / "20261007T210000Z_aaaa.zip", version="6.40.0")
    build_gtfs_zip(tmp_path / "20261104T210057Z_bbbb.zip", version="6.41.1")
    (tmp_path / "notes.txt").write_text("not an archive")

    assert run(["--latest", str(tmp_path)], db_session) == 0

    assert versions(db_session) == ["6.41.1"]


def test_latest_on_a_folder_without_archives_fails(db_session, tmp_path: Path, capsys):
    assert run(["--latest", str(tmp_path)], db_session) == 1

    assert versions(db_session) == []
    assert "no GTFS archive" in capsys.readouterr().err


def test_missing_file_fails(db_session, tmp_path: Path, capsys):
    assert run([str(tmp_path / "missing.zip")], db_session) == 1

    assert "not found" in capsys.readouterr().err
