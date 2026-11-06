"""Print a summary of an archived GTFS-RT snapshot (debug tool, not used by the archiver).

Usage:
    python peek.py <file.pb.gz> [number_of_entities_to_print]
    python peek.py latest vehiclePositions|tripUpdates [n]   # newest file in the archive
"""

import collections
import gzip
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from google.transit import gtfs_realtime_pb2

DATA_DIR = Path(os.environ.get("STB_DATA_DIR", "/var/lib/stb-collector"))


def latest(feed: str) -> Path:
    newest_day = max((DATA_DIR / "raw" / feed).iterdir())
    newest_hour = max(newest_day.iterdir())
    return max(newest_hour.glob("*.pb.gz"))


def main(args: list[str]) -> None:
    if args[0] == "latest":
        path, rest = latest(args[1]), args[2:]
    else:
        path, rest = Path(args[0]), args[1:]
    n = int(rest[0]) if rest else 2

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(gzip.decompress(path.read_bytes()))
    ts = datetime.fromtimestamp(feed.header.timestamp, timezone.utc)
    print(f"{path}\nfeed time {ts:%Y-%m-%d %H:%M:%S} UTC, {len(feed.entity)} entities")

    routes = collections.Counter(
        e.vehicle.trip.route_id or e.trip_update.trip.route_id for e in feed.entity
    )
    print(f"{len(routes)} routes, most entities: {routes.most_common(8)}")
    if any(e.HasField("vehicle") for e in feed.entity):
        status = collections.Counter(
            gtfs_realtime_pb2.VehiclePosition.VehicleStopStatus.Name(e.vehicle.current_status)
            for e in feed.entity
        )
        print(f"vehicle status: {dict(status)}")
    for e in feed.entity[:n]:
        print(MessageToDict(e))


if __name__ == "__main__":
    main(sys.argv[1:] or ["latest", "vehiclePositions"])
