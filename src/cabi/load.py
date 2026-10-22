"""Load Capital Bikeshare monthly files into SQLite and clean them with SQL.

The CSV is streamed with the standard library so a year of data never has to fit in memory.
Rows go into a temporary staging table, a single SQL statement (sql/classify.sql) decides which
rows are clean, and clean and rejected rows are written to separate tables. Reloading a file
replaces its earlier rows, so the load is safe to repeat.
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import resources
from typing import Dict, Iterator, List, Optional, Tuple

REQUIRED = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name", "start_station_id",
            "end_station_name", "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng", "member_casual"]
OLD_FORMAT_MARKERS = {"Start date", "Duration", "Bike number", "Member type"}

# Generous box around the Washington, D.C. region. Anything outside it is a GPS error.
SERVICE_AREA = {"lat_min": 38.5, "lat_max": 39.5, "lng_min": -77.8, "lng_max": -76.5}

REASONS = ["missing_ride_id", "duplicate_ride_id", "bad_timestamp", "unknown_member_type", "ended_before_started",
           "under_60_seconds", "over_24_hours", "missing_coordinates", "outside_service_area"]


class SchemaError(ValueError):
    pass


def sql_text(name: str) -> str:
    return resources.files("cabi").joinpath("sql", name).read_text(encoding="utf-8")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(sql_text("schema.sql"))
    return conn


@contextmanager
def open_csv(path: str) -> Iterator[Tuple[str, io.TextIOBase]]:
    """Yield (file name, text stream) for a .csv or for the CSV inside a .zip."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            members = [n for n in archive.namelist()
                       if n.lower().endswith(".csv") and not n.startswith("__MACOSX") and not os.path.basename(n).startswith("._")]
            if len(members) != 1:
                raise SchemaError("%s: expected exactly one CSV inside the zip, found %d" % (path, len(members)))
            with archive.open(members[0]) as raw:
                yield os.path.basename(members[0]), io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
    else:
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            yield os.path.basename(path), handle


def check_header(header: List[str], where: str) -> None:
    if OLD_FORMAT_MARKERS & set(header):
        raise SchemaError("%s uses the pre-2020 Capital Bikeshare layout (Start date, Duration, ...). "
                          "Only the current layout (ride_id, started_at, ...) is supported." % where)
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise SchemaError("%s is missing expected columns: %s" % (where, ", ".join(missing)))


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _timestamp(value: Optional[str]) -> Optional[str]:
    value = _clean(value)
    return value.replace("T", " ").rstrip("Z") if value else None


def staged_rows(reader: csv.DictReader) -> Iterator[Tuple]:
    for row in reader:
        yield (_clean(row["ride_id"]), _clean(row["rideable_type"]), _clean(row["member_casual"]),
               _timestamp(row["started_at"]), _timestamp(row["ended_at"]),
               _clean(row["start_station_id"]), _clean(row["start_station_name"]),
               _clean(row["end_station_id"]), _clean(row["end_station_name"]),
               _clean(row["start_lat"]), _clean(row["start_lng"]), _clean(row["end_lat"]), _clean(row["end_lng"]))


STAGING = """
CREATE TEMP TABLE stg (
    ride_id TEXT, rideable_type TEXT, member_casual TEXT, started_at TEXT, ended_at TEXT,
    start_station_id TEXT, start_station_name TEXT, end_station_id TEXT, end_station_name TEXT,
    start_lat TEXT, start_lng TEXT, end_lat TEXT, end_lng TEXT
)"""


def load_file(conn: sqlite3.Connection, path: str, batch: int = 50_000) -> Dict[str, object]:
    """Load one monthly file. Returns a summary: rows read, kept, and rejected per reason."""
    with open_csv(path) as (name, stream):
        reader = csv.DictReader(stream)
        check_header(reader.fieldnames or [], name)
        with conn:   # one transaction: a failed load leaves the database as it was
            for table in ("trips", "rejected_trips", "cleaning_log", "loads"):
                conn.execute("DELETE FROM %s WHERE source_file = ?" % table, (name,))
            conn.execute("DROP TABLE IF EXISTS temp.stg")
            conn.execute("DROP TABLE IF EXISTS temp.classified")
            conn.execute(STAGING)
            rows = staged_rows(reader)
            read = 0
            while True:
                chunk = []
                for row in rows:
                    chunk.append(row)
                    if len(chunk) >= batch:
                        break
                if not chunk:
                    break
                conn.executemany("INSERT INTO stg VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", chunk)
                read += len(chunk)
            conn.execute(sql_text("classify.sql"), SERVICE_AREA)
            conn.execute(sql_text("insert_clean.sql"), {"source_file": name})
            conn.execute(
                "INSERT INTO rejected_trips (ride_id, reason, rideable_type, member_casual, started_at, ended_at, "
                "duration_s, start_station_id, end_station_id, source_file) "
                "SELECT ride_id, reason, rideable_type, member_casual, started_at, ended_at, duration_s, "
                "start_station_id, end_station_id, ? FROM classified WHERE reason IS NOT NULL", (name,))
            conn.execute("INSERT INTO cleaning_log (source_file, reason, rows) "
                         "SELECT ?, reason, COUNT(*) FROM classified WHERE reason IS NOT NULL GROUP BY reason", (name,))
            # Remember the latest name seen for every station, from clean rows only.
            conn.execute(
                "INSERT INTO station_names (station_id, name, last_seen) "
                "SELECT station_id, name, last_seen FROM ("
                "  SELECT s.start_station_id AS station_id, s.start_station_name AS name, s.started_at AS last_seen "
                "  FROM stg s JOIN classified c ON c.rid = s.rowid WHERE c.reason IS NULL "
                "        AND s.start_station_id IS NOT NULL AND s.start_station_name IS NOT NULL "
                "  UNION ALL "
                "  SELECT s.end_station_id, s.end_station_name, s.ended_at "
                "  FROM stg s JOIN classified c ON c.rid = s.rowid WHERE c.reason IS NULL "
                "        AND s.end_station_id IS NOT NULL AND s.end_station_name IS NOT NULL "
                ") WHERE true "
                "ON CONFLICT(station_id) DO UPDATE SET name = excluded.name, last_seen = excluded.last_seen "
                "WHERE excluded.last_seen > station_names.last_seen")
            kept = conn.execute("SELECT COUNT(*) FROM trips WHERE source_file = ?", (name,)).fetchone()[0]
            conn.execute("INSERT INTO loads (source_file, rows_read, rows_kept, loaded_at) VALUES (?,?,?,?)",
                         (name, read, kept, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))
            rejected = {r[0]: r[1] for r in conn.execute(
                "SELECT reason, rows FROM cleaning_log WHERE source_file = ?", (name,))}
            conn.execute("DROP TABLE temp.classified")
            conn.execute("DROP TABLE temp.stg")
    return {"file": name, "read": read, "kept": kept, "rejected": rejected}


def build_stations(conn: sqlite3.Connection) -> int:
    """(Re)build the stations table and the analysis views from whatever is loaded."""
    conn.executescript(sql_text("stations.sql"))
    return conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]


def load_files(db: str, paths: List[str]) -> List[Dict[str, object]]:
    conn = connect(db)
    summaries = [load_file(conn, p) for p in paths]
    build_stations(conn)
    conn.close()
    return summaries
