"""US-02a: detect arrivals from Vehicle Positions (issue #24).

Acceptance criteria:
  AC1  STOPPED_AT at a stop, or current_stop_sequence advancing, creates an
       arrival with method stopped_at / sequence_advance.
  AC2  Exactly one arrival per (service date, trip, stop sequence).
  AC3  Reprocessing the same snapshots gives the same arrivals.
  AC4  Positions older than the staleness threshold are ignored.
"""

from datetime import UTC, date, datetime, timedelta

from app.arrivals.detector import (
    ArrivalDetector,
    ArrivalMethod,
    VehicleObservation,
    VehicleStatus,
)

T0 = datetime(2026, 11, 16, 12, 0, 0, tzinfo=UTC)
DAY = date(2026, 11, 16)
STOPPED = VehicleStatus.STOPPED_AT
IN_TRANSIT = VehicleStatus.IN_TRANSIT_TO


def at(poll: int, delay: int = 0) -> datetime:
    """Time of the n-th poll (every 15 s), minus `delay` seconds."""
    return T0 + timedelta(seconds=15 * poll - delay)


def obs(seq: int, status: VehicleStatus, time: datetime, trip: str = "T41", vehicle: str = "V1") -> VehicleObservation:
    return VehicleObservation(
        vehicle_id=vehicle,
        trip_id=trip,
        route_id="41",
        service_date=DAY,
        stop_id=f"S{seq}",
        stop_sequence=seq,
        status=status,
        timestamp=time,
    )


def run(detector: ArrivalDetector, snapshots: list[list[VehicleObservation]]):
    """Feed snapshots in order (poll n at T0 + 15n s); return all arrivals."""
    arrivals = []
    for poll, observations in enumerate(snapshots):
        arrivals += detector.process(at(poll), observations)
    return arrivals


def keys(arrivals) -> list[tuple[str, int, ArrivalMethod]]:
    return [(a.trip_id, a.stop_sequence, a.method) for a in arrivals]


# --- AC1: stopped_at ----------------------------------------------------------


def test_vehicle_stopped_at_a_stop_is_an_arrival():
    arrivals = run(ArrivalDetector(), [[obs(5, STOPPED, at(0, delay=3))]])

    assert len(arrivals) == 1
    arrival = arrivals[0]
    assert arrival.method is ArrivalMethod.STOPPED_AT
    assert (arrival.service_date, arrival.trip_id, arrival.route_id) == (DAY, "T41", "41")
    assert (arrival.stop_id, arrival.stop_sequence) == ("S5", 5)
    assert arrival.vehicle_id == "V1"
    # the vehicle's own timestamp, not the poll time
    assert arrival.observed_at == at(0, delay=3)


def test_first_sighting_in_transit_is_not_an_arrival():
    assert run(ArrivalDetector(), [[obs(5, IN_TRANSIT, at(0))]]) == []


# --- AC1: sequence_advance ------------------------------------------------------


def test_sequence_advance_means_the_previous_stop_was_reached():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, IN_TRANSIT, at(0))],
            [obs(6, IN_TRANSIT, at(1, delay=2))],
        ],
    )

    assert keys(arrivals) == [("T41", 5, ArrivalMethod.SEQUENCE_ADVANCE)]
    # stop of the earlier observation; time of the first sighting past it
    assert arrivals[0].stop_id == "S5"
    assert arrivals[0].observed_at == at(1, delay=2)


def test_advance_straight_into_stopped_at_gives_both_stops():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, IN_TRANSIT, at(0))],
            [obs(6, STOPPED, at(1))],
        ],
    )

    assert keys(arrivals) == [
        ("T41", 5, ArrivalMethod.SEQUENCE_ADVANCE),
        ("T41", 6, ArrivalMethod.STOPPED_AT),
    ]


def test_no_movement_is_not_an_arrival():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, IN_TRANSIT, at(0))],
            [obs(5, IN_TRANSIT, at(1))],
            [obs(5, IN_TRANSIT, at(2))],
        ],
    )

    assert arrivals == []


def test_skipped_stops_are_left_for_trip_updates():
    # 34 -> 37 in one poll (seen in the real feed): 35 and 36 are US-02b
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(34, IN_TRANSIT, at(0))],
            [obs(37, IN_TRANSIT, at(1))],
        ],
    )

    assert keys(arrivals) == [("T41", 34, ArrivalMethod.SEQUENCE_ADVANCE)]


def test_sequence_going_back_is_ignored():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(7, IN_TRANSIT, at(0))],
            [obs(6, IN_TRANSIT, at(1))],
        ],
    )

    assert arrivals == []


# --- AC2: one arrival per (service date, trip, stop sequence) --------------------


def test_staying_stopped_over_several_polls_is_one_arrival():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, STOPPED, at(0))],
            [obs(5, STOPPED, at(1))],
            [obs(5, STOPPED, at(2))],
        ],
    )

    assert keys(arrivals) == [("T41", 5, ArrivalMethod.STOPPED_AT)]
    assert arrivals[0].observed_at == at(0)  # the first time it was seen there


def test_leaving_a_stop_already_recorded_adds_nothing():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, STOPPED, at(0))],
            [obs(6, IN_TRANSIT, at(1))],
        ],
    )

    assert keys(arrivals) == [("T41", 5, ArrivalMethod.STOPPED_AT)]


def test_same_trip_reported_by_another_vehicle_id_is_not_duplicated():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, STOPPED, at(0), vehicle="V1")],
            [obs(5, STOPPED, at(1), vehicle="V1-new-id")],
        ],
    )

    assert len(arrivals) == 1


def test_vehicles_on_different_trips_are_independent():
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(5, IN_TRANSIT, at(0), trip="T41"), obs(2, STOPPED, at(0), trip="T112", vehicle="V2")],
            [obs(6, IN_TRANSIT, at(1), trip="T41"), obs(2, STOPPED, at(1), trip="T112", vehicle="V2")],
        ],
    )

    assert sorted(keys(arrivals)) == [
        ("T112", 2, ArrivalMethod.STOPPED_AT),
        ("T41", 5, ArrivalMethod.SEQUENCE_ADVANCE),
    ]


def test_vehicle_starting_a_new_trip_does_not_close_the_old_one():
    # we don't know whether it reached the last stop of T41
    arrivals = run(
        ArrivalDetector(),
        [
            [obs(20, IN_TRANSIT, at(0), trip="T41")],
            [obs(1, IN_TRANSIT, at(1), trip="T41-next")],
        ],
    )

    assert arrivals == []


# --- AC3: reprocessing is deterministic -----------------------------------------


def test_reprocessing_the_same_snapshots_gives_the_same_arrivals():
    snapshots = [
        [obs(5, IN_TRANSIT, at(0)), obs(1, STOPPED, at(0), trip="T112", vehicle="V2")],
        [obs(6, STOPPED, at(1)), obs(2, IN_TRANSIT, at(1), trip="T112", vehicle="V2")],
        [obs(8, IN_TRANSIT, at(2)), obs(3, IN_TRANSIT, at(2), trip="T112", vehicle="V2")],
    ]

    first = run(ArrivalDetector(), snapshots)
    second = run(ArrivalDetector(), snapshots)

    assert first == second
    assert keys(first) == [
        ("T112", 1, ArrivalMethod.STOPPED_AT),
        ("T41", 5, ArrivalMethod.SEQUENCE_ADVANCE),
        ("T41", 6, ArrivalMethod.STOPPED_AT),
        ("T112", 2, ArrivalMethod.SEQUENCE_ADVANCE),
    ]


# --- AC4: stale positions are ignored --------------------------------------------


def test_stale_stopped_at_is_ignored():
    detector = ArrivalDetector(max_age=timedelta(minutes=2))

    arrivals = run(detector, [[obs(5, STOPPED, at(0, delay=180))]])

    assert arrivals == []


def test_stale_position_does_not_count_as_movement():
    detector = ArrivalDetector(max_age=timedelta(minutes=2))

    arrivals = run(
        detector,
        [
            [obs(5, IN_TRANSIT, at(0))],
            [obs(6, IN_TRANSIT, at(1, delay=600))],  # old report, must not move the vehicle
        ],
    )

    assert arrivals == []


def test_position_just_inside_the_threshold_is_used():
    detector = ArrivalDetector(max_age=timedelta(minutes=2))

    arrivals = run(detector, [[obs(5, STOPPED, at(0, delay=120))]])

    assert len(arrivals) == 1
