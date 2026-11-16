"""GTFS schedule tables (US-01).

Every imported GTFS archive is a separate feed version; all schedule rows
belong to exactly one version and are deleted with it. Inside a version,
the GTFS codes (route_id, stop_id, trip_id, ...) are unique. See
docs/model-date.md, section 2.1.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CHAR,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _feed_version_fk() -> Mapped[int]:
    return mapped_column(
        ForeignKey("feed_versions.id", ondelete="CASCADE"), nullable=False
    )


class FeedVersion(Base):
    __tablename__ = "feed_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_version: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # When the collector downloaded this archive (from its file name). TPBI
    # republishes changed timetables with the same version and dates, so this
    # is what tells which version applied on a given day (migration 0003).
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Agency(Base):
    __tablename__ = "agencies"
    __table_args__ = (UniqueConstraint("feed_version_id", "agency_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_version_id: Mapped[int] = _feed_version_fk()
    agency_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (UniqueConstraint("feed_version_id", "route_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_version_id: Mapped[int] = _feed_version_fk()
    agency_pk: Mapped[int] = mapped_column(
        ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    route_id: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    long_name: Mapped[str | None] = mapped_column(Text)
    # 0 tram, 1 metro, 3 bus, 11 trolleybus
    route_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    color: Mapped[str | None] = mapped_column(CHAR(6))


class Stop(Base):
    __tablename__ = "stops"
    __table_args__ = (UniqueConstraint("feed_version_id", "stop_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_version_id: Mapped[int] = _feed_version_fk()
    stop_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    parent_stop_pk: Mapped[int | None] = mapped_column(
        ForeignKey("stops.id", ondelete="SET NULL")
    )


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("feed_version_id", "service_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_version_id: Mapped[int] = _feed_version_fk()
    service_id: Mapped[str] = mapped_column(Text, nullable=False)
    monday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tuesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wednesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    thursday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    friday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    saturday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sunday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class ServiceException(Base):
    __tablename__ = "service_exceptions"

    service_pk: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    # 1 = service added, 2 = service removed
    exception_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (UniqueConstraint("feed_version_id", "trip_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_version_id: Mapped[int] = _feed_version_fk()
    trip_id: Mapped[str] = mapped_column(Text, nullable=False)
    route_pk: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    service_pk: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    headsign: Mapped[str | None] = mapped_column(Text)
    direction_id: Mapped[int | None] = mapped_column(SmallInteger)


class StopTime(Base):
    __tablename__ = "stop_times"

    trip_pk: Mapped[int] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True
    )
    stop_sequence: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    stop_pk: Mapped[int] = mapped_column(
        ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Seconds since the start of the service day; can exceed 86400 (e.g. 25:10).
    # Empty for non-timepoint stops, which GTFS allows (~25k rows per version).
    arrival_seconds: Mapped[int | None] = mapped_column(Integer)
    departure_seconds: Mapped[int | None] = mapped_column(Integer)
