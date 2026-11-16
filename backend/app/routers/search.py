"""Search a line by number or a stop by name, in the latest schedule version.

Metro routes and stops without surface transport are left out: they have no
real-time data.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, case, func, literal, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import FeedVersion, Route, Stop, StopTime, Trip
from app.schemas.search import LineResult, SearchResponse, StopResult
from app.transit import METRO, vehicle_type

router = APIRouter(prefix="/api", tags=["search"])

MAX_LINES = 10
MAX_STOPS = 20


@router.get("/search")
def search(
    q: str = Query(min_length=1, max_length=100, description="Line number or (part of) a stop name"),
    session: Session = Depends(get_session),
) -> SearchResponse:
    query = q.strip()
    feed_id = session.scalar(select(func.max(FeedVersion.id)))
    if not query or feed_id is None:
        return SearchResponse(query=query, lines=[], stops=[])
    return SearchResponse(
        query=query,
        lines=_search_lines(session, feed_id, query),
        stops=_search_stops(session, feed_id, query),
    )


def _search_lines(session: Session, feed_id: int, query: str) -> list[LineResult]:
    """Lines whose number starts with the query; the exact match comes first."""
    name = func.lower(Route.short_name)
    needle = query.lower()
    routes = session.execute(
        select(Route)
        .where(
            Route.feed_version_id == feed_id,
            Route.route_type != METRO,
            name.startswith(needle, autoescape=True),
        )
        .order_by(
            case((name == needle, 0), else_=1),
            func.length(Route.short_name),
            Route.short_name,
        )
        .limit(MAX_LINES)
    ).scalars().all()

    termini = _termini(session, [route.id for route in routes])
    return [
        LineResult(
            route_id=route.route_id,
            short_name=route.short_name,
            route_type=route.route_type,
            vehicle_type=vehicle_type(route.route_type),
            color=route.color,
            termini=termini.get(route.id) or _split_long_name(route.long_name),
        )
        for route in routes
    ]


def _termini(session: Session, route_pks: list[int]) -> dict[int, list[str]]:
    """The most common headsign of each direction, direction 0 first."""
    if not route_pks:
        return {}
    rows = session.execute(
        select(Trip.route_pk, func.mode().within_group(Trip.headsign))
        .where(Trip.route_pk.in_(route_pks), Trip.headsign.is_not(None))
        .group_by(Trip.route_pk, Trip.direction_id)
        .order_by(Trip.route_pk, Trip.direction_id)
    )
    termini: dict[int, list[str]] = defaultdict(list)
    for route_pk, headsign in rows:
        if headsign not in termini[route_pk]:
            termini[route_pk].append(headsign)
    return termini


def _split_long_name(long_name: str | None) -> list[str]:
    """Fallback for routes without headsigns: "Ghencea - Piata Presei"."""
    if not long_name:
        return []
    return [part.strip() for part in long_name.split(" - ") if part.strip()]


def _search_stops(session: Session, feed_id: int, query: str) -> list[StopResult]:
    """Stops whose name contains the query, ignoring case and diacritics."""
    name = func.f_unaccent(func.lower(Stop.name))
    plain = func.f_unaccent(func.lower(literal(query)))
    pattern = func.f_unaccent(func.lower(literal(_escape_like(query))))
    stmt: Select = (
        select(Stop)
        .where(
            Stop.feed_version_id == feed_id,
            name.contains(pattern, escape="\\"),
            _served_by_surface_transport(),
        )
        .order_by(
            case((name.startswith(pattern, escape="\\"), 0), else_=1),
            func.similarity(name, plain).desc(),
            Stop.name,
            Stop.description,
        )
        .limit(MAX_STOPS)
    )
    return [
        StopResult(
            stop_id=stop.stop_id,
            name=stop.name,
            description=stop.description,
            lat=stop.lat,
            lon=stop.lon,
        )
        for stop in session.scalars(stmt)
    ]


def _escape_like(value: str) -> str:
    return value.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


def _served_by_surface_transport():
    """At least one bus / tram / trolleybus trip stops here.

    A correlated LIMIT 1 instead of EXISTS: with EXISTS, PostgreSQL hash-joins
    all of stop_times (~0.9 s) for short queries such as "a".
    """
    return (
        select(literal(True))
        .select_from(StopTime)
        .join(Trip, Trip.id == StopTime.trip_pk)
        .join(Route, Route.id == Trip.route_pk)
        .where(StopTime.stop_pk == Stop.id, Route.route_type != METRO)
        .limit(1)
        .correlate(Stop)
        .scalar_subquery()
        .is_(True)
    )
