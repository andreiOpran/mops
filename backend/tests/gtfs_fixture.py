"""Builds tiny GTFS archives for the importer tests.

The layout copies the real TPBI feed (same files and columns, UTF-8 with BOM,
times past 24:00, empty times at non-timepoint stops), but with only a few rows.
"""

import zipfile
from pathlib import Path

BOM = "﻿"

FEED_INFO = """feed_publisher_name,feed_publisher_url,feed_lang,feed_version
FlashWeb IT,https://flash-its.eu/,ro,{version}
"""

AGENCY = """agency_id,agency_name,agency_url,agency_timezone,agency_lang
1,STB SA,http://stbsa.ro/,Europe/Bucharest,ro
"""

ROUTES = """route_id,agency_id,route_short_name,route_type,route_color,route_text_color,route_long_name
R41,1,41,0,E30613,FFFFFF,Ghencea - Piata Presei Libere
R112,1,112,3,,,
"""

# P1 is a station (location_type 1) with two platforms; S3 has no parent.
STOPS = """stop_id,stop_name,stop_desc,stop_lat,stop_lon,location_type,platform_code,parent_station,level_id
P1,Piața Unirii,,44.42710,26.10260,1,,,
S1,Piața Unirii,,44.42700,26.10250,,,P1,
S2,Piața Unirii,,44.42720,26.10270,,,P1,
S3,Ghencea,,44.41100,26.04200,,,,
"""

CALENDAR = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
LV,1,1,1,1,1,0,0,20261007,20270105
D,0,0,0,0,0,0,1,20261011,20270103
"""

TRIPS = """route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible,bikes_allowed
R41,LV,T41_LV_1,Piata Presei Libere,,0,,,,
R41,D,T41_D_1,Ghencea,,1,,,,
R112,LV,T112_LV_1,,,0,,,,
"""

# T41_LV_1 runs past midnight (25:10:00); its middle stop has no time (non-timepoint).
STOP_TIMES = """trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled,timepoint
T41_LV_1,25:00:00,25:00:30,S3,0,,,,,
T41_LV_1,,,S1,1,,,,,
T41_LV_1,25:10:00,25:10:00,S2,2,,,,,
T41_D_1,08:05:00,08:05:00,S2,0,,,,,
T41_D_1,8:15:00,8:15:00,S3,1,,,,,
T112_LV_1,06:00:00,06:00:00,S1,0,,,,,
T112_LV_1,06:07:00,06:07:00,S3,1,,,,,
"""

# Counts of the base archive, used by the tests.
BASE_COUNTS = {
    "agencies": 1,
    "routes": 2,
    "stops": 4,
    "services": 2,
    "trips": 3,
    "stop_times": 7,
}


def build_gtfs_zip(path: Path, version: str = "6.41.1", extra_route: bool = False) -> Path:
    """Write a GTFS zip to `path`. `extra_route` adds line 133 (one trip, two stops)."""
    routes, trips, stop_times = ROUTES, TRIPS, STOP_TIMES
    if extra_route:
        routes += "R133,1,133,3,,,\n"
        trips += "R133,LV,T133_LV_1,,,0,,,,\n"
        stop_times += "T133_LV_1,07:00:00,07:00:00,S1,0,,,,,\nT133_LV_1,07:09:00,07:09:00,S3,1,,,,,\n"

    files = {
        "feed_info.txt": FEED_INFO.format(version=version),
        "agency.txt": AGENCY,
        "routes.txt": routes,
        "stops.txt": STOPS,
        "calendar.txt": CALENDAR,
        "trips.txt": trips,
        "stop_times.txt": stop_times,
        # Present in the real feed but not imported.
        "shapes.txt": "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, BOM + content)
    return path
