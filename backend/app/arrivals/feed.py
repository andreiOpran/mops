"""Reading archived Vehicle Positions snapshots (*.pb.gz saved by the collector, T-01)."""

from datetime import datetime
from pathlib import Path

from app.arrivals.detector import VehicleObservation


def parse_vehicle_positions(data: bytes) -> tuple[datetime, list[VehicleObservation]]:
    """Decode one GTFS-RT Vehicle Positions message.

    Returns (feed header time, observations). Vehicles without a trip,
    start date or stop sequence are skipped: they can't produce an arrival.
    """
    raise NotImplementedError


def read_snapshot(path: Path) -> tuple[datetime, list[VehicleObservation]]:
    """Read one gzip-compressed snapshot file from the collector archive."""
    raise NotImplementedError
