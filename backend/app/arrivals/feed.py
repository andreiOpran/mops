"""Reading archived Vehicle Positions snapshots (*.pb.gz saved by the collector, T-01)."""

import gzip
from datetime import UTC, datetime
from pathlib import Path

from google.transit import gtfs_realtime_pb2

from app.arrivals.detector import VehicleObservation, VehicleStatus


def parse_vehicle_positions(data: bytes) -> tuple[datetime, list[VehicleObservation]]:
    """Decode one GTFS-RT Vehicle Positions message.

    Returns (feed header time, observations). Vehicles without a trip,
    start date or stop sequence are skipped: they can't produce an arrival.
    """
    message = gtfs_realtime_pb2.FeedMessage()
    message.ParseFromString(data)
    header_time = datetime.fromtimestamp(message.header.timestamp, UTC)

    observations = []
    for entity in message.entity:
        if not entity.HasField("vehicle"):
            continue
        vehicle = entity.vehicle
        if not (vehicle.trip.trip_id and vehicle.trip.start_date and vehicle.HasField("current_stop_sequence")):
            continue
        observations.append(
            VehicleObservation(
                vehicle_id=vehicle.vehicle.id or entity.id,
                trip_id=vehicle.trip.trip_id,
                route_id=vehicle.trip.route_id,
                service_date=datetime.strptime(vehicle.trip.start_date, "%Y%m%d").date(),
                stop_id=vehicle.stop_id,
                stop_sequence=vehicle.current_stop_sequence,
                status=VehicleStatus(vehicle.current_status),
                timestamp=datetime.fromtimestamp(vehicle.timestamp, UTC) if vehicle.timestamp else header_time,
            )
        )
    return header_time, observations


def read_snapshot(path: Path) -> tuple[datetime, list[VehicleObservation]]:
    """Read one gzip-compressed snapshot file from the collector archive."""
    return parse_vehicle_positions(gzip.decompress(Path(path).read_bytes()))
