"""Observed arrivals (US-02, US-03). See docs/model-date.md, section 2.2.

GTFS codes are stored as text, not as keys into the schedule tables, so the
statistics of a line or stop stay continuous across schedule versions.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ARRIVAL_METHODS = ("stopped_at", "sequence_advance", "trip_update_estimate")


class Arrival(Base):
    __tablename__ = "arrivals"
    __table_args__ = (
        # one arrival per (service day, trip, stop): reprocessing adds nothing
        UniqueConstraint("service_date", "trip_id", "stop_sequence"),
        Index("ix_arrivals_route_day", "route_id", "service_date"),
        Index("ix_arrivals_stop_day", "stop_id", "service_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    trip_id: Mapped[str] = mapped_column(Text, nullable=False)
    route_id: Mapped[str] = mapped_column(Text, nullable=False)
    stop_id: Mapped[str] = mapped_column(Text, nullable=False)
    stop_sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[str] = mapped_column(Enum(*ARRIVAL_METHODS, name="arrival_method"), nullable=False)
    vehicle_id: Mapped[str | None] = mapped_column(Text)

    # Filled by the delay calculation (US-03); empty right after detection.
    feed_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("feed_versions.id", ondelete="SET NULL")
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delay_seconds: Mapped[int | None] = mapped_column(Integer)
