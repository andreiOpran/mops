"""Delay statistics of a line, per direction, over a range of service days.

Computed by PostgreSQL in one query on the (route_id, service_date) index.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Arrival, Route, Trip
from app.schemas.lines import NO_DATA_MESSAGE, DirectionStats, LineStats
from app.transit import ON_TIME_MAX_SECONDS, ON_TIME_MIN_SECONDS, today, vehicle_type

router = APIRouter(prefix="/api/lines", tags=["lines"])

DEFAULT_RANGE_DAYS = 7
# Every request sorts all arrivals in the range (median, p90): cap it at a year.
MAX_RANGE_DAYS = 366


@router.get("/{route_id}/stats")
def line_stats(
    route_id: str,
    date_from: date | None = Query(None, description="First service day (default: 6 days before date_to)"),
    date_to: date | None = Query(None, description="Last service day, included (default: today)"),
    session: Session = Depends(get_session),
) -> LineStats:
    route = _latest_route(session, route_id)
    if route is None:
        raise HTTPException(404, "Linia nu există.")
    date_from, date_to = _date_range(date_from, date_to)

    directions = _direction_stats(session, route_id, date_from, date_to)
    return LineStats(
        route_id=route.route_id,
        short_name=route.short_name,
        vehicle_type=vehicle_type(route.route_type),
        color=route.color,
        date_from=date_from,
        date_to=date_to,
        directions=directions,
        message=None if directions else NO_DATA_MESSAGE,
    )


def _latest_route(session: Session, route_id: str) -> Route | None:
    """The line as described by the newest schedule version that has it."""
    return session.scalars(
        select(Route)
        .where(Route.route_id == route_id)
        .order_by(Route.feed_version_id.desc())
        .limit(1)
    ).first()


def _date_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    date_to = date_to or today()
    date_from = date_from or date_to - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if date_from > date_to:
        raise HTTPException(422, "date_from trebuie să fie cel mult date_to.")
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(422, f"Intervalul poate avea cel mult {MAX_RANGE_DAYS} de zile.")
    return date_from, date_to


def _direction_stats(
    session: Session, route_id: str, date_from: date, date_to: date
) -> list[DirectionStats]:
    delay = Arrival.delay_seconds
    # Trip codes are only unique inside a schedule version, so the direction
    # comes from the version each arrival was calculated with.
    trip = and_(Trip.feed_version_id == Arrival.feed_version_id, Trip.trip_id == Arrival.trip_id)
    rows = session.execute(
        select(
            Trip.direction_id,
            func.mode().within_group(Trip.headsign).label("headsign"),
            func.count().label("observations"),
            func.avg(delay).label("mean"),
            func.percentile_cont(0.5).within_group(delay).label("median"),
            func.percentile_cont(0.9).within_group(delay).label("p90"),
            func.count()
            .filter(delay.between(ON_TIME_MIN_SECONDS, ON_TIME_MAX_SECONDS))
            .label("on_time"),
        )
        .select_from(Arrival)
        .outerjoin(Trip, trip)
        .where(
            Arrival.route_id == route_id,
            Arrival.service_date.between(date_from, date_to),
            # Detected but not yet matched to the timetable: no delay to count.
            delay.is_not(None),
        )
        .group_by(Trip.direction_id)
        .order_by(Trip.direction_id.asc().nulls_last())
    )
    return [
        DirectionStats(
            direction_id=row.direction_id,
            headsign=row.headsign,
            observation_count=row.observations,
            mean_delay_seconds=float(row.mean),
            median_delay_seconds=row.median,
            p90_delay_seconds=row.p90,
            on_time_pct=100 * row.on_time / row.observations,
        )
        for row in rows
    ]
