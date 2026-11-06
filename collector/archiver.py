"""Raw archiver for the TPBI GTFS-RT feeds and the static GTFS schedule (task T-01).

Stores every snapshot exactly as received (gzip-compressed), without parsing it.
Arrival detection and delay calculation (US-02, US-03) are built later and
replay these files.

Layout under DATA_DIR (all timestamps UTC, so the DST change cannot create
duplicate or missing names):

    raw/<feed>/YYYY-MM-DD/HH/YYYYMMDDTHHMMSSZ.pb.gz   one file per new snapshot
    static/YYYYMMDDTHHMMSSZ_<sha12>.zip              one file per schedule version
    polls/YYYY-MM-DD.jsonl                           one line per request (coverage / gaps)
    status.json                                      last success per feed
"""

import gzip
import hashlib
import json
import logging
import os
import shutil
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

RT_BASE_URL = "https://gtfs.tpbi.ro/api/gtfs-rt/"
RT_FEEDS = ("vehiclePositions", "tripUpdates")
STATIC_URL = "https://gtfs.tpbi.ro/regional/BUCHAREST-REGION.zip"

POLL_SECONDS = float(os.environ.get("STB_POLL_SECONDS", "15"))
STATIC_CHECK_SECONDS = float(os.environ.get("STB_STATIC_CHECK_SECONDS", str(6 * 3600)))
MIN_FREE_BYTES = int(float(os.environ.get("STB_MIN_FREE_GB", "5")) * 1024**3)
USER_AGENT = os.environ.get(
    "STB_USER_AGENT", "stb-delay-monitor/0.1 (MOPS student project)"
)

log = logging.getLogger("archiver")


def utc_stamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def snapshot_path(data_dir: Path, feed: str, now: datetime) -> Path:
    return (
        data_dir / "raw" / feed / now.strftime("%Y-%m-%d") / now.strftime("%H")
        / f"{utc_stamp(now)}.pb.gz"
    )


def write_atomic(path: Path, data: bytes) -> None:
    """Write via a temp file + rename, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Archiver:
    def __init__(self, client: httpx.Client, data_dir: Path, min_free_bytes: int = MIN_FREE_BYTES):
        self.client = client
        self.data_dir = data_dir
        self.min_free_bytes = min_free_bytes
        self.etags: dict[str, str] = {}
        self.status: dict[str, str] = {}

    def disk_ok(self) -> bool:
        return shutil.disk_usage(self.data_dir).free >= self.min_free_bytes

    def record_poll(self, now: datetime, feed: str, outcome: str, **extra) -> None:
        line = {"t": now.isoformat(timespec="seconds"), "feed": feed, "outcome": outcome, **extra}
        path = self.data_dir / "polls" / f"{now:%Y-%m-%d}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")

    def mark_success(self, key: str, now: datetime) -> None:
        self.status[key] = now.isoformat(timespec="seconds")
        write_atomic(self.data_dir / "status.json", json.dumps(self.status, indent=2).encode())

    def fetch(self, key: str, url: str) -> httpx.Response:
        headers = {"If-None-Match": self.etags[key]} if key in self.etags else {}
        response = self.client.get(url, headers=headers)
        if response.status_code == 200 and "etag" in response.headers:
            self.etags[key] = response.headers["etag"]
        return response

    def poll_feed(self, feed: str, now: datetime) -> str:
        """Fetch one RT feed; save it if it changed. Returns the recorded outcome."""
        started = time.monotonic()
        try:
            response = self.fetch(feed, RT_BASE_URL + feed)
        except httpx.HTTPError as exc:
            self.record_poll(now, feed, "error", error=f"{type(exc).__name__}: {exc}")
            log.warning("%s: %s", feed, exc)
            return "error"
        ms = round((time.monotonic() - started) * 1000)

        if response.status_code == 304:
            self.record_poll(now, feed, "not_modified", ms=ms)
            self.mark_success(feed, now)
            return "not_modified"
        if response.status_code != 200:
            self.record_poll(now, feed, "error", http=response.status_code, ms=ms)
            log.warning("%s: HTTP %s", feed, response.status_code)
            return "error"
        if not self.disk_ok():
            self.etags.pop(feed, None)  # so the next poll downloads it again
            self.record_poll(now, feed, "disk_full", bytes=len(response.content), ms=ms)
            log.error("free space below limit, snapshot not saved")
            return "disk_full"

        write_atomic(snapshot_path(self.data_dir, feed, now), gzip.compress(response.content, 6))
        self.record_poll(now, feed, "saved", bytes=len(response.content), ms=ms)
        self.mark_success(feed, now)
        return "saved"

    def check_static(self, now: datetime) -> str:
        """Download the static GTFS zip if it changed; keep one copy per distinct content."""
        try:
            response = self.fetch("static", STATIC_URL)
        except httpx.HTTPError as exc:
            self.record_poll(now, "static", "error", error=f"{type(exc).__name__}: {exc}")
            log.warning("static: %s", exc)
            return "error"
        if response.status_code == 304:
            self.record_poll(now, "static", "not_modified")
            self.mark_success("static", now)
            return "not_modified"
        if response.status_code != 200:
            self.record_poll(now, "static", "error", http=response.status_code)
            return "error"

        sha = hashlib.sha256(response.content).hexdigest()
        static_dir = self.data_dir / "static"
        if any(static_dir.glob(f"*_{sha[:12]}.zip")):
            outcome = "unchanged"
        else:
            write_atomic(static_dir / f"{utc_stamp(now)}_{sha[:12]}.zip", response.content)
            outcome = "saved"
            log.info("new static GTFS version saved (%s)", sha[:12])
        self.record_poll(now, "static", outcome, bytes=len(response.content), sha256=sha)
        self.mark_success("static", now)
        return outcome


def run(data_dir: Path) -> None:
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=10.0) as client:
        archiver = Archiver(client, data_dir)
        next_static = 0.0
        next_tick = time.monotonic()
        log.info("archiver started, data dir %s, every %ss", data_dir, POLL_SECONDS)
        while not stop.is_set():
            now = datetime.now(timezone.utc)
            for feed in RT_FEEDS:
                archiver.poll_feed(feed, now)
            if time.monotonic() >= next_static:
                archiver.check_static(now)
                next_static = time.monotonic() + STATIC_CHECK_SECONDS

            # Fixed schedule: a slow request delays this tick, not every following one.
            # No extra retries: a failed poll is retried at the next tick (NFR-02).
            next_tick += POLL_SECONDS
            stop.wait(max(0.0, next_tick - time.monotonic()))
        log.info("archiver stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # every request is already in polls/
    run(Path(os.environ.get("STB_DATA_DIR", "/var/lib/stb-collector")))
