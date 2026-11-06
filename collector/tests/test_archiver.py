# Tests written after the code (T-01 is a technical task, not developed with TDD).
import gzip
import json
from datetime import datetime, timezone

import httpx
import pytest

import archiver
from archiver import Archiver, snapshot_path

NOW = datetime(2026, 10, 25, 1, 30, 15, tzinfo=timezone.utc)


def make_archiver(tmp_path, handler, min_free_bytes=0):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Archiver(client, tmp_path, min_free_bytes=min_free_bytes)


def poll_lines(tmp_path):
    path = tmp_path / "polls" / "2026-10-25.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_snapshot_path_uses_utc_date_and_hour(tmp_path):
    path = snapshot_path(tmp_path, "tripUpdates", NOW)
    assert path == tmp_path / "raw/tripUpdates/2026-10-25/01/20261025T013015Z.pb.gz"


def test_new_snapshot_is_saved_gzipped_and_unchanged(tmp_path):
    body = b"\x0a\x03raw-protobuf"
    a = make_archiver(tmp_path, lambda r: httpx.Response(200, content=body, headers={"etag": "v1"}))

    assert a.poll_feed("vehiclePositions", NOW) == "saved"

    saved = snapshot_path(tmp_path, "vehiclePositions", NOW)
    assert gzip.decompress(saved.read_bytes()) == body
    assert poll_lines(tmp_path)[0]["outcome"] == "saved"
    assert json.loads((tmp_path / "status.json").read_text())["vehiclePositions"] == NOW.isoformat()


def test_etag_is_sent_and_304_saves_nothing(tmp_path):
    seen = []

    def handler(request):
        seen.append(request.headers.get("if-none-match"))
        if request.headers.get("if-none-match") == "v1":
            return httpx.Response(304)
        return httpx.Response(200, content=b"x", headers={"etag": "v1"})

    a = make_archiver(tmp_path, handler)
    a.poll_feed("tripUpdates", NOW)
    later = NOW.replace(second=30)

    assert a.poll_feed("tripUpdates", later) == "not_modified"
    assert seen == [None, "v1"]
    assert not snapshot_path(tmp_path, "tripUpdates", later).exists()


@pytest.mark.parametrize(
    "handler, expected",
    [
        (lambda r: httpx.Response(403), {"outcome": "error", "http": 403}),
        (lambda r: (_ for _ in ()).throw(httpx.ConnectTimeout("timed out")), {"outcome": "error"}),
    ],
)
def test_failures_are_logged_as_gaps(tmp_path, handler, expected):
    a = make_archiver(tmp_path, handler)

    assert a.poll_feed("vehiclePositions", NOW) == "error"

    line = poll_lines(tmp_path)[0]
    assert expected.items() <= line.items()
    assert not (tmp_path / "raw").exists()


def test_low_disk_skips_write_and_forgets_etag(tmp_path):
    a = make_archiver(
        tmp_path, lambda r: httpx.Response(200, content=b"x", headers={"etag": "v1"}),
        min_free_bytes=10**18,
    )

    assert a.poll_feed("vehiclePositions", NOW) == "disk_full"
    assert "vehiclePositions" not in a.etags
    assert not (tmp_path / "raw").exists()


def test_static_keeps_one_copy_per_distinct_content(tmp_path):
    bodies = iter([b"zip-v1", b"zip-v1", b"zip-v2"])
    a = make_archiver(tmp_path, lambda r: httpx.Response(200, content=next(bodies)))

    outcomes = [a.check_static(NOW.replace(hour=h)) for h in (1, 7, 13)]

    assert outcomes == ["saved", "unchanged", "saved"]
    assert len(list((tmp_path / "static").glob("*.zip"))) == 2


def test_static_url_and_feeds_point_to_tpbi():
    assert archiver.STATIC_URL.startswith("https://gtfs.tpbi.ro/")
    assert archiver.RT_FEEDS == ("vehiclePositions", "tripUpdates")
