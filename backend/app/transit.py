"""Domain constants shared by the API endpoints."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

BUCHAREST = ZoneInfo("Europe/Bucharest")

# GTFS route_type values in the TPBI feed.
METRO = 1
VehicleType = Literal["tram", "bus", "trolleybus", "other"]
VEHICLE_TYPES: dict[int, VehicleType] = {0: "tram", 3: "bus", 11: "trolleybus"}

# On time: delay between -1 min and +3 min, both included.
ON_TIME_MIN_SECONDS = -60
ON_TIME_MAX_SECONDS = 180


def vehicle_type(route_type: int) -> VehicleType:
    return VEHICLE_TYPES.get(route_type, "other")


def today() -> date:
    """Today's date in Bucharest (not the server's time zone)."""
    return datetime.now(BUCHAREST).date()
