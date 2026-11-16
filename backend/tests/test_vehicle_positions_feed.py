"""US-02a: reading archived Vehicle Positions snapshots (*.pb.gz from the collector)."""

import gzip
from datetime import UTC, date, datetime

from google.transit import gtfs_realtime_pb2

from app.arrivals.detector import VehicleStatus
from app.arrivals.feed import parse_vehicle_positions, read_snapshot

HEADER_TIME = 1794831891  # 2026-11-16 12:24:51 UTC, from a real snapshot


def feed_message() -> gtfs_realtime_pb2.FeedMessage:
    """Same shape as the real TPBI feed, with one complete and two incomplete vehicles."""
    message = gtfs_realtime_pb2.FeedMessage()
    message.header.gtfs_realtime_version = "2.0"
    message.header.timestamp = HEADER_TIME

    complete = message.entity.add(id="2792").vehicle
    complete.trip.trip_id = "PV1_PV1_409_1_165387"
    complete.trip.route_id = "PV1_409"
    complete.trip.start_date = "20261116"
    complete.vehicle.id = "2792"
    complete.stop_id = "PV1_96"
    complete.current_stop_sequence = 34
    complete.current_status = gtfs_realtime_pb2.VehiclePosition.STOPPED_AT
    complete.timestamp = 1794831852

    no_trip = message.entity.add(id="no-trip").vehicle
    no_trip.vehicle.id = "9999"
    no_trip.timestamp = 1794831852

    no_sequence = message.entity.add(id="no-seq").vehicle
    no_sequence.trip.trip_id = "TRIP_LV_824_1_64"
    no_sequence.trip.start_date = "20261116"
    no_sequence.vehicle.id = "1460"
    no_sequence.timestamp = 1794831852
    return message


def test_parses_header_time_and_complete_vehicles():
    header_time, observations = parse_vehicle_positions(feed_message().SerializeToString())

    assert header_time == datetime(2026, 11, 16, 12, 24, 51, tzinfo=UTC)
    assert len(observations) == 1
    vehicle = observations[0]
    assert vehicle.vehicle_id == "2792"
    assert vehicle.trip_id == "PV1_PV1_409_1_165387"
    assert vehicle.route_id == "PV1_409"
    assert vehicle.service_date == date(2026, 11, 16)
    assert (vehicle.stop_id, vehicle.stop_sequence) == ("PV1_96", 34)
    assert vehicle.status is VehicleStatus.STOPPED_AT
    assert vehicle.timestamp == datetime.fromtimestamp(1794831852, UTC)


def test_in_transit_status_is_mapped():
    message = feed_message()
    message.entity[0].vehicle.current_status = gtfs_realtime_pb2.VehiclePosition.IN_TRANSIT_TO

    _, observations = parse_vehicle_positions(message.SerializeToString())

    assert observations[0].status is VehicleStatus.IN_TRANSIT_TO


def test_reads_a_gzipped_snapshot_file(tmp_path):
    path = tmp_path / "20261116T122451Z.pb.gz"
    path.write_bytes(gzip.compress(feed_message().SerializeToString()))

    header_time, observations = read_snapshot(path)

    assert header_time == datetime.fromtimestamp(HEADER_TIME, UTC)
    assert [o.vehicle_id for o in observations] == ["2792"]
