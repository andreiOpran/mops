"""Delay of every recorded arrival against its scheduled time (US-03)."""

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DelayStats:
    updated: int  # arrivals that got their delay in this run
    unmatched: int  # arrivals still without delay (trip or stop not in the schedule)


def compute_delays(session: Session) -> DelayStats:
    """Fill feed_version_id, scheduled_at and delay_seconds for the arrivals
    that don't have them yet. Arrivals already computed are not touched, so
    a later schedule version never changes a delay recorded earlier."""
    raise NotImplementedError
