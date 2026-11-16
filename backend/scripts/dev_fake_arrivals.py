"""DEV ONLY: fill `arrivals` with fake observations to try the statistics by hand.

Until arrival detection fills the table with real data, this script
generates arrivals from the imported timetable (latest schedule
version): every scheduled stop of every trip that runs on each day, with a
random delay. Rows are tagged vehicle_id = 'DEV-FAKE' and can be removed
with --clear. Never run it against the production database.

    python -m scripts.dev_fake_arrivals --days 30 --lines 41,178,1
    python -m scripts.dev_fake_arrivals --days 7 --sample 0.1     (all lines, 10% of stops)
    python -m scripts.dev_fake_arrivals --clear
"""

import argparse
import sys
import time
from datetime import timedelta

from sqlalchemy import Connection, text

from app.db import engine
from app.transit import today

TAG = "DEV-FAKE"

# Delay: mostly a little late, sometimes early, a long tail of large delays.
GENERATE = text(
    """
    WITH latest AS (SELECT max(id) AS id FROM feed_versions),
    days AS (
        SELECT d::date AS day, extract(isodow FROM d)::int AS dow
        FROM generate_series(CAST(:date_from AS date), CAST(:date_to AS date), interval '1 day') d
    )
    INSERT INTO arrivals (service_date, feed_version_id, trip_id, route_id, stop_id, stop_sequence,
                          scheduled_at, observed_at, delay_seconds, method, vehicle_id)
    SELECT day, latest.id, t.trip_id, r.route_id, s.stop_id, st.stop_sequence,
           sched, sched + make_interval(secs => delay), delay, 'stopped_at', :tag
    FROM latest
    JOIN routes r ON r.feed_version_id = latest.id AND r.route_type <> 1
    JOIN trips t ON t.route_pk = r.id
    JOIN services sv ON sv.id = t.service_pk
    JOIN stop_times st ON st.trip_pk = t.id AND st.arrival_seconds IS NOT NULL
    JOIN stops s ON s.id = st.stop_pk
    JOIN days ON CASE dow WHEN 1 THEN sv.monday WHEN 2 THEN sv.tuesday WHEN 3 THEN sv.wednesday
                          WHEN 4 THEN sv.thursday WHEN 5 THEN sv.friday WHEN 6 THEN sv.saturday
                          ELSE sv.sunday END
    CROSS JOIN LATERAL (
        SELECT (day + time '12:00') AT TIME ZONE 'Europe/Bucharest' - interval '12 hours'
               + make_interval(secs => st.arrival_seconds) AS sched,
               round((random() + random() + random() - 1.2) * 150
                     + CASE WHEN random() < 0.1 THEN random() * 900 ELSE 0 END)::int AS delay
    ) x
    WHERE (CAST(:lines AS text[]) IS NULL OR r.short_name = ANY(CAST(:lines AS text[])))
      AND random() < :sample
    ON CONFLICT (service_date, trip_id, stop_sequence) DO NOTHING
    """
)


class RealArrivalsPresent(Exception):
    pass


def has_real_arrivals(connection: Connection) -> bool:
    return bool(
        connection.scalar(
            text("SELECT EXISTS (SELECT 1 FROM arrivals WHERE vehicle_id IS DISTINCT FROM :tag)"),
            {"tag": TAG},
        )
    )


def generate(connection: Connection, days: int, lines: list[str] | None = None, sample: float = 1.0) -> int:
    """Insert fake arrivals for the last `days` days; returns how many.

    Refuses when the table holds real arrivals: mixed in, fake rows would
    skew the statistics and block real arrivals for the same trip and stop.
    """
    if has_real_arrivals(connection):
        raise RealArrivalsPresent
    result = connection.execute(
        GENERATE,
        {
            "date_from": today() - timedelta(days=days - 1),
            "date_to": today(),
            "lines": lines,
            "sample": sample,
            "tag": TAG,
        },
    )
    return result.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=7, help="days back from today (default 7)")
    parser.add_argument("--lines", help="comma-separated line numbers (default: all lines)")
    parser.add_argument("--sample", type=float, default=1.0, help="share of scheduled stops to keep (0-1)")
    parser.add_argument("--clear", action="store_true", help=f"delete all {TAG} arrivals and exit")
    args = parser.parse_args()

    started = time.perf_counter()
    with engine.begin() as connection:
        if args.clear:
            deleted = connection.execute(text("DELETE FROM arrivals WHERE vehicle_id = :tag"), {"tag": TAG})
            print(f"deleted {deleted.rowcount} fake arrivals")
            return
        try:
            inserted = generate(connection, args.days, args.lines.split(",") if args.lines else None, args.sample)
        except RealArrivalsPresent:
            sys.exit("error: arrivals already holds real data; fake arrivals are only for an empty dev database")
        connection.execute(text("ANALYZE arrivals"))
    print(f"inserted {inserted} fake arrivals in {time.perf_counter() - started:.1f} s")


if __name__ == "__main__":
    main()
