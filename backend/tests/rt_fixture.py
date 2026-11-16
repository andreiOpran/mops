"""Builds archived Vehicle Positions snapshots (*.pb.gz) like the collector saves them."""

import gzip
from datetime import datetime
from pathlib import Path

from google.transit import gtfs_realtime_pb2

STOPPED_AT = gtfs_realtime_pb2.VehiclePosition.STOPPED_AT
IN_TRANSIT_TO = gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO


def write_snapshot(archive: Path, time: datetime, vehicles: list[tuple[str, int, int]]) -> Path:
    """Write one snapshot at <archive>/YYYY-MM-DD/HH/YYYYMMDDTHHMMSSZ.pb.gz.

    `vehicles`: (trip_id, stop_sequence, status); vehicle timestamp = `time`.
    """
    message = gtfs_realtime_pb2.FeedMessage()
    message.header.gtfs_realtime_version = "2.0"
    message.header.timestamp = int(time.timestamp())
    for trip_id, sequence, status in vehicles:
        vehicle = message.entity.add(id=f"veh-{trip_id}").vehicle
        vehicle.trip.trip_id = trip_id
        vehicle.trip.route_id = "41"
        vehicle.trip.start_date = time.strftime("%Y%m%d")
        vehicle.vehicle.id = f"veh-{trip_id}"
        vehicle.stop_id = f"S{sequence}"
        vehicle.current_stop_sequence = sequence
        vehicle.current_status = status
        vehicle.timestamp = int(time.timestamp())

    path = archive / time.strftime("%Y-%m-%d") / time.strftime("%H") / time.strftime("%Y%m%dT%H%M%SZ.pb.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(message.SerializeToString()))
    return path
