"""Response schemas for line statistics."""

from datetime import date

from pydantic import BaseModel

from app.transit import VehicleType

NO_DATA_MESSAGE = "Nu există date pentru intervalul selectat."


class DirectionStats(BaseModel):
    """Delay statistics for one direction of a line, in seconds."""

    # None groups arrivals whose trip is not in their schedule version.
    direction_id: int | None
    # The most common trip headsign of the direction.
    headsign: str | None
    observation_count: int
    mean_delay_seconds: float
    median_delay_seconds: float
    p90_delay_seconds: float
    # Share of arrivals on time, 0-100.
    on_time_pct: float


class LineStats(BaseModel):
    route_id: str
    short_name: str
    vehicle_type: VehicleType
    color: str | None
    date_from: date
    date_to: date
    directions: list[DirectionStats]
    # Set when there is no arrival in the range.
    message: str | None
