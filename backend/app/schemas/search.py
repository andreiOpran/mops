"""Response schemas for the line / stop search."""

from typing import Literal

from pydantic import BaseModel

VehicleType = Literal["tram", "bus", "trolleybus", "other"]


class LineResult(BaseModel):
    route_id: str
    short_name: str
    route_type: int
    vehicle_type: VehicleType
    color: str | None
    # Route ends, from the trip headsigns of each direction (direction 0 first).
    termini: list[str]


class StopResult(BaseModel):
    stop_id: str
    name: str
    description: str | None
    lat: float
    lon: float


class SearchResponse(BaseModel):
    query: str
    lines: list[LineResult]
    stops: list[StopResult]
