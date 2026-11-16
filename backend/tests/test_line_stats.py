"""Line statistics (GET /api/lines/{route_id}/stats).

Expected values are computed by hand; percentiles use linear interpolation
(PostgreSQL percentile_cont): rank = p * (n - 1).
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from tests.factories import BUCHAREST, TRAM, Schedule


def today() -> date:
    return datetime.now(BUCHAREST).date()


def get_stats(client, route_id: str = "R41", **params) -> dict:
    response = client.get(f"/api/lines/{route_id}/stats", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def direction(body: dict, direction_id: int | None) -> dict:
    return next(d for d in body["directions"] if d["direction_id"] == direction_id)


@pytest.fixture
def schedule(db_session: Session) -> Schedule:
    return Schedule(db_session, "6.41.1")


@pytest.fixture
def line_41(schedule: Schedule):
    """Tram 41 with one trip per direction."""
    route = schedule.route("41", TRAM, color="BE1622")
    to_presei = schedule.trip(route, 0, "Piata Presei Libere")
    to_ghencea = schedule.trip(route, 1, "Ghencea")
    return route, to_presei, to_ghencea


@pytest.fixture
def two_directions(schedule: Schedule, line_41):
    """Direction 0: [-120, 0, 60, 90, 300] s; direction 1: [30, 150, 210] s, all today."""
    _, to_presei, to_ghencea = line_41
    for delay in (-120, 0, 60, 90, 300):
        schedule.arrival(to_presei, delay, today())
    for delay in (30, 150, 210):
        schedule.arrival(to_ghencea, delay, today())


# --- statistics per direction ---


def test_line_and_range_are_described(client, two_directions):
    body = get_stats(client)

    assert body["route_id"] == "R41"
    assert body["short_name"] == "41"
    assert body["vehicle_type"] == "tram"
    assert body["color"] == "BE1622"
    assert body["message"] is None


def test_one_entry_per_direction_in_direction_order(client, two_directions):
    body = get_stats(client)

    assert [(d["direction_id"], d["headsign"]) for d in body["directions"]] == [
        (0, "Piata Presei Libere"),
        (1, "Ghencea"),
    ]


def test_statistics_of_direction_0(client, two_directions):
    stats = direction(get_stats(client), 0)

    assert stats["observation_count"] == 5
    assert stats["mean_delay_seconds"] == pytest.approx(66.0, abs=0.1)  # 330 / 5
    assert stats["median_delay_seconds"] == pytest.approx(60.0, abs=0.1)
    assert stats["p90_delay_seconds"] == pytest.approx(216.0, abs=0.1)  # 90 + 0.6 * (300 - 90)
    assert stats["on_time_pct"] == pytest.approx(60.0, abs=0.1)  # 0, 60, 90


def test_statistics_of_direction_1(client, two_directions):
    stats = direction(get_stats(client), 1)

    assert stats["observation_count"] == 3
    assert stats["mean_delay_seconds"] == pytest.approx(130.0, abs=0.1)
    assert stats["median_delay_seconds"] == pytest.approx(150.0, abs=0.1)
    assert stats["p90_delay_seconds"] == pytest.approx(198.0, abs=0.1)  # 150 + 0.8 * (210 - 150)
    assert stats["on_time_pct"] == pytest.approx(66.7, abs=0.1)  # 30, 150


@pytest.mark.parametrize(
    ("delay", "on_time_pct"),
    [(-61, 0.0), (-60, 100.0), (180, 100.0), (181, 0.0)],
)
def test_on_time_limits_are_included(client, schedule, line_41, delay, on_time_pct):
    _, to_presei, _ = line_41
    schedule.arrival(to_presei, delay, today())

    assert direction(get_stats(client), 0)["on_time_pct"] == pytest.approx(on_time_pct)


def test_headsign_is_the_most_common_one_of_the_direction(client, schedule, line_41):
    route, to_presei, _ = line_41
    short_turn = schedule.trip(route, 0, "Depou Militari")
    schedule.arrival(to_presei, 0, today())
    schedule.arrival(to_presei, 0, today())
    schedule.arrival(short_turn, 0, today())

    body = get_stats(client)

    assert len(body["directions"]) == 1
    assert body["directions"][0]["headsign"] == "Piata Presei Libere"


def test_arrivals_without_a_calculated_delay_are_not_counted(client, schedule, line_41):
    _, to_presei, _ = line_41
    schedule.arrival(to_presei, 60, today())
    schedule.arrival(to_presei, None, today())

    body = get_stats(client)

    assert [(d["direction_id"], d["observation_count"]) for d in body["directions"]] == [(0, 1)]
    assert body["directions"][0]["on_time_pct"] == pytest.approx(100.0)


def test_only_arrivals_without_a_delay_gives_the_no_data_message(client, schedule, line_41):
    _, to_presei, _ = line_41
    schedule.arrival(to_presei, None, today())

    body = get_stats(client)

    assert body["directions"] == []
    assert body["message"] is not None


def test_other_lines_are_not_counted(client, schedule, two_directions):
    other = schedule.trip(schedule.route("410"), 0, "Bucur Obor")
    schedule.arrival(other, 999, today())

    body = get_stats(client)

    assert sum(d["observation_count"] for d in body["directions"]) == 8


def test_direction_comes_from_the_schedule_version_used_for_the_arrival(client, db_session):
    """Trip codes are only unique inside a version: T1 is direction 1 in the
    old version and direction 0 in the new one."""
    old = Schedule(db_session, "6.40.0")
    old_trip = old.trip(old.route("41", TRAM), 1, "Ghencea")
    old.arrival(old_trip, 60, today())

    new = Schedule(db_session, "6.41.1")
    new_route = new.route("41", TRAM)
    new.trip(new_route, 0, "Piata Presei Libere")

    body = get_stats(client)

    assert [(d["direction_id"], d["headsign"], d["observation_count"]) for d in body["directions"]] == [
        (1, "Ghencea", 1)
    ]


def test_arrivals_without_a_known_trip_are_grouped_apart(client, db_session, schedule, line_41):
    _, to_presei, _ = line_41
    schedule.arrival(to_presei, 0, today())
    orphan = schedule.arrival(to_presei, 0, today())
    orphan.feed_version_id = None  # its schedule version was deleted
    db_session.flush()

    body = get_stats(client)

    assert [(d["direction_id"], d["observation_count"]) for d in body["directions"]] == [
        (0, 1),
        (None, 1),
    ]


# --- date range ---


def test_default_range_is_the_last_7_days(client, line_41):
    body = get_stats(client)

    assert body["date_from"] == (today() - timedelta(days=6)).isoformat()
    assert body["date_to"] == today().isoformat()


def test_default_range_includes_6_days_ago_but_not_7(client, schedule, line_41):
    _, to_presei, _ = line_41
    schedule.arrival(to_presei, 10, today() - timedelta(days=6))
    schedule.arrival(to_presei, 999, today() - timedelta(days=7))

    stats = direction(get_stats(client), 0)

    assert stats["observation_count"] == 1
    assert stats["mean_delay_seconds"] == pytest.approx(10.0)


def test_chosen_range_filters_by_service_date(client, schedule, line_41):
    _, to_presei, _ = line_41
    for days_ago, delay in [(0, 1), (10, 20), (11, 30), (12, 40)]:
        schedule.arrival(to_presei, delay, today() - timedelta(days=days_ago))

    body = get_stats(
        client,
        date_from=(today() - timedelta(days=11)).isoformat(),
        date_to=(today() - timedelta(days=10)).isoformat(),
    )

    stats = direction(body, 0)
    assert stats["observation_count"] == 2
    assert stats["mean_delay_seconds"] == pytest.approx(25.0)


def test_only_date_from_given_ends_today(client, line_41):
    start = (today() - timedelta(days=30)).isoformat()

    body = get_stats(client, date_from=start)

    assert (body["date_from"], body["date_to"]) == (start, today().isoformat())


def test_only_date_to_given_covers_the_7_days_before_it(client, line_41):
    body = get_stats(client, date_to="2026-11-10")

    assert (body["date_from"], body["date_to"]) == ("2026-11-04", "2026-11-10")


def test_single_day_range_is_accepted(client, line_41):
    body = get_stats(client, date_from=today().isoformat(), date_to=today().isoformat())

    assert body["date_from"] == body["date_to"]


def test_date_from_after_date_to_is_rejected(client, line_41):
    response = client.get(
        "/api/lines/R41/stats",
        params={"date_from": today().isoformat(), "date_to": (today() - timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 422


def test_range_of_366_days_is_accepted(client, line_41):
    body = get_stats(client, date_from="2026-01-01", date_to="2027-01-01")

    assert (body["date_from"], body["date_to"]) == ("2026-01-01", "2027-01-01")


def test_range_longer_than_366_days_is_rejected(client, line_41):
    response = client.get("/api/lines/R41/stats", params={"date_from": "2026-01-01", "date_to": "2027-01-02"})

    assert response.status_code == 422


def test_invalid_date_is_rejected(client, line_41):
    response = client.get("/api/lines/R41/stats", params={"date_from": "not-a-date"})

    assert response.status_code == 422


# --- no data ---


def test_no_data_in_range_gives_an_explicit_message(client, schedule, line_41):
    _, to_presei, _ = line_41
    schedule.arrival(to_presei, 60, today() - timedelta(days=30))

    body = get_stats(client)

    assert body["directions"] == []
    assert body["message"] == "Nu există date pentru intervalul selectat."
    assert body["short_name"] == "41"


def test_unknown_line_is_not_found(client, line_41):
    response = client.get("/api/lines/NOPE/stats")

    assert response.status_code == 404
