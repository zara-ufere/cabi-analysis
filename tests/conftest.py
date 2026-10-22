import csv
import io
import os
import sys
import zipfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from cabi import load

HEADER = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name", "start_station_id",
          "end_station_name", "end_station_id", "start_lat", "start_lng", "end_lat", "end_lng", "member_casual"]

A = ("31001", "Alpha St", 38.90, -77.04)
B = ("31002", "Bravo St", 38.91, -77.02)
C = ("31003", "Charlie St", 38.92, -77.03)


def trip(ride_id="R1", rideable="classic_bike", start="2026-02-10 08:00:00.000", seconds=600.0, member="member",
         frm=A, to=B, **override):
    """One CSV row in the real file layout. frm/to are (id, name, lat, lng) or None for a dockless end."""
    began = datetime.strptime(start, "%Y-%m-%d %H:%M:%S.%f")
    finished = began + timedelta(seconds=seconds)
    row = {
        "ride_id": ride_id, "rideable_type": rideable,
        "started_at": began.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "ended_at": finished.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "start_station_name": frm[1] if frm and len(frm) == 4 else "", "start_station_id": frm[0] if frm and len(frm) == 4 else "",
        "end_station_name": to[1] if to and len(to) == 4 else "", "end_station_id": to[0] if to and len(to) == 4 else "",
        "start_lat": (frm or (0, 0, 38.95, -77.0))[2], "start_lng": (frm or (0, 0, 38.95, -77.0))[3],
        "end_lat": (to or (0, 0, 38.95, -77.0))[2], "end_lng": (to or (0, 0, 38.95, -77.0))[3],
        "member_casual": member}
    row.update(override)
    return row


def csv_text(rows, header=HEADER, bom=False):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header, quoting=csv.QUOTE_NONNUMERIC, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return ("﻿" if bom else "") + out.getvalue()


def write_csv(path, rows, **kw):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(csv_text(rows, **kw))
    return str(path)


def write_zip(path, rows, name="202602-capitalbikeshare-tripdata.csv"):
    """Zip laid out the way macOS zips it: the real CSV plus a __MACOSX resource-fork entry."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, csv_text(rows))
        archive.writestr("__MACOSX/._" + name, b"\x00\x05\x16\x07junk")
    return str(path)


@pytest.fixture
def db(tmp_path):
    conn = load.connect(str(tmp_path / "t.db"))
    yield conn
    conn.close()


@pytest.fixture
def loaded(db, tmp_path):
    """Helper: loaded(rows, name) writes a CSV and loads it, returning the summary."""
    def _load(rows, name="202602-capitalbikeshare-tripdata.csv"):
        path = tmp_path / name
        write_csv(path, rows)
        summary = load.load_file(db, str(path))
        load.build_stations(db)
        return summary
    return _load
