"""Search a line by number or a stop by name (GET /api/search)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import BUS, METRO, TRAM, Schedule


@pytest.fixture
def schedule(db_session: Session) -> Schedule:
    """Current version: tram 41, buses 141 / 410 / 112, metro M2 and stops around Piața Unirii."""
    s = Schedule(db_session, "6.41.1")

    unirii_bus = s.stop("3570", "Piata Unirii", "Bd. Regina Maria, Bucuresti")
    unirii_tram = s.stop("6551", "Piata Unirii", "Bd. Corneliu Coposu, Bucuresti")
    unirii_diacritics = s.stop("7428", "Piața Unirii 1", "Aleea III, Bucuresti")
    ghencea = s.stop("4001", "Ghencea", "Bd. Ghencea, Bucuresti")
    s.stop("9999", "Piata Unirii Veche")  # no trip stops here

    metro_station = s.stop("15100", "Piața Unirii")
    metro_platform = s.stop("14726R", "Piața Unirii 2 (M2)", parent=metro_station)

    tram_41 = s.route("41", TRAM, "Ghencea - Piata Presei Libere")
    s.trip(tram_41, 0, "Piata Presei Libere", [ghencea, unirii_tram])
    s.trip(tram_41, 0, "Piata Presei Libere", [ghencea, unirii_tram])
    s.trip(tram_41, 1, "Ghencea", [unirii_tram, ghencea])

    s.trip(s.route("410"), 0, "Bucur Obor", [unirii_bus])
    s.trip(s.route("141"), 0, "Romprim", [unirii_bus])
    s.trip(s.route("112", long_name="Piata Unirii - Baneasa"), 0, None, [unirii_diacritics])

    s.trip(s.route("M2", METRO), 0, "Pipera", [metro_platform])
    return s


def search(client: TestClient, q: str) -> dict:
    response = client.get("/api/search", params={"q": q})
    assert response.status_code == 200
    return response.json()


# --- lines ---


def test_line_number_shows_line_vehicle_type_and_route_ends(client, schedule):
    lines = search(client, "41")["lines"]

    assert lines[0] == {
        "route_id": "R41",
        "short_name": "41",
        "route_type": 0,
        "vehicle_type": "tram",
        "color": None,
        "termini": ["Piata Presei Libere", "Ghencea"],
    }


def test_exact_line_number_comes_before_longer_numbers(client, schedule):
    lines = search(client, "41")["lines"]

    assert [line["short_name"] for line in lines] == ["41", "410"]


def test_line_number_must_be_a_prefix(client, schedule):
    assert [line["short_name"] for line in search(client, "1")["lines"]] == ["112", "141"]


def test_route_ends_fall_back_to_long_name_without_headsigns(client, schedule):
    line = search(client, "112")["lines"][0]

    assert line["termini"] == ["Piata Unirii", "Baneasa"]


def test_metro_lines_are_not_returned(client, schedule):
    assert search(client, "M2")["lines"] == []
    assert search(client, "m")["lines"] == []


# --- stops ---


def test_partial_stop_name_without_diacritics_finds_stops_with_diacritics(client, schedule):
    names = {stop["name"] for stop in search(client, "piata unirii")["stops"]}

    assert "Piața Unirii 1" in names


def test_diacritics_and_case_in_the_query_are_ignored(client, schedule):
    assert search(client, "PIAȚA UNIRII")["stops"] == search(client, "piata unirii")["stops"]


def test_partial_name_matches_inside_the_name(client, schedule):
    stop_ids = {stop["stop_id"] for stop in search(client, "unir")["stops"]}

    assert stop_ids == {"3570", "6551", "7428"}


def test_each_stop_is_a_separate_result_with_its_street(client, schedule):
    stops = [s for s in search(client, "piata unirii")["stops"] if s["name"] == "Piata Unirii"]

    assert sorted((s["stop_id"], s["description"]) for s in stops) == [
        ("3570", "Bd. Regina Maria, Bucuresti"),
        ("6551", "Bd. Corneliu Coposu, Bucuresti"),
    ]


def test_metro_and_unserved_stops_are_not_returned(client, schedule):
    stop_ids = {stop["stop_id"] for stop in search(client, "unirii")["stops"]}

    assert "15100" not in stop_ids  # metro station (parent)
    assert "14726R" not in stop_ids  # metro platform
    assert "9999" not in stop_ids  # no trip stops here


def test_names_starting_with_the_query_come_first(client, schedule):
    stops = search(client, "ghen")["stops"]

    assert stops[0]["name"] == "Ghencea"


def test_like_wildcards_in_the_query_are_literal(client, schedule):
    assert search(client, "%")["stops"] == []
    assert search(client, "_")["stops"] == []


# --- versions, empty results and validation ---


def test_only_the_latest_schedule_version_is_searched(client, schedule, db_session):
    newer = Schedule(db_session, "6.42.0")
    newer.trip(newer.route("41", TRAM), 0, "Piata Presei Libere", [newer.stop("4001", "Ghencea")])

    assert len(search(client, "41")["lines"]) == 1
    assert len(search(client, "ghencea")["stops"]) == 1


def test_no_schedule_imported_returns_empty_results(client):
    assert search(client, "41") == {"query": "41", "lines": [], "stops": []}


def test_no_match_returns_empty_results(client, schedule):
    assert search(client, "zzz") == {"query": "zzz", "lines": [], "stops": []}


def test_query_is_trimmed(client, schedule):
    body = search(client, "  41 ")

    assert body["query"] == "41"
    assert body["lines"][0]["short_name"] == "41"


def test_blank_query_returns_empty_results(client, schedule):
    assert search(client, "   ") == {"query": "", "lines": [], "stops": []}


def test_missing_query_is_rejected(client):
    assert client.get("/api/search").status_code == 422
