"""The dev-only fake arrivals script (scripts/dev_fake_arrivals.py)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Arrival
from app.transit import today
from scripts.dev_fake_arrivals import TAG, RealArrivalsPresent, generate
from tests.factories import TRAM, Schedule


@pytest.fixture
def schedule(db_session: Session) -> Schedule:
    s = Schedule(db_session, "6.41.1")
    route = s.route("41", TRAM)
    s.trip(route, 0, "Ghencea", [s.stop("A", "Stop A"), s.stop("B", "Stop B")])
    return s


def test_generates_tagged_arrivals_from_the_timetable(db_session, schedule):
    inserted = generate(db_session.connection(), days=7)

    # The fixture service runs Monday to Friday: 5 of any 7 days, 2 stops each.
    assert inserted == 10
    tags = db_session.scalars(select(Arrival.vehicle_id).distinct()).all()
    assert tags == [TAG]


def test_runs_again_on_top_of_fake_arrivals(db_session, schedule):
    generate(db_session.connection(), days=7)

    assert generate(db_session.connection(), days=14) == 10  # only the 7 older days are new


def test_refuses_when_real_arrivals_exist(db_session, schedule):
    trip = schedule.trip(schedule.route("178"), 0, "Complex Apusului")
    schedule.arrival(trip, 60, today() - timedelta(days=1))  # vehicle_id is not the fake tag

    with pytest.raises(RealArrivalsPresent):
        generate(db_session.connection(), days=7)

    assert db_session.scalar(select(func.count()).select_from(Arrival)) == 1
