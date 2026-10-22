import sqlite3
from datetime import datetime

import pytest

from conftest import A, B, C, HEADER, csv_text, trip, write_csv, write_zip
from cabi import load


def rows_of(db, sql="SELECT * FROM trips ORDER BY ride_id"):
    return [dict(r) for r in db.execute(sql)]


def test_clean_row_is_kept_with_derived_fields(db, loaded):
    s = loaded([trip("R1", start="2026-02-09 08:15:30.250", seconds=600.5)])
    assert (s["read"], s["kept"], s["rejected"]) == (1, 1, {})
    r = rows_of(db)[0]
    assert (r["start_date"], r["start_hour"], r["end_date"], r["end_hour"]) == ("2026-02-09", 8, "2026-02-09", 8)
    assert r["start_dow"] == datetime(2026, 2, 9).weekday() == 0                      # Monday is 0
    assert r["duration_s"] == 600.5
    assert (r["start_station_id"], r["end_station_id"], r["member_type"]) == ("31001", "31002", "member")


def test_trip_crossing_midnight_and_sunday_numbering(db, loaded):
    loaded([trip("R1", start="2026-02-08 23:50:00.000", seconds=1200)])            # 2026-02-08 is a Sunday
    r = rows_of(db)[0]
    assert (r["start_date"], r["end_date"], r["start_dow"], r["end_dow"], r["end_hour"]) == (
        "2026-02-08", "2026-02-09", 6, 0, 0)


def test_dockless_ends_are_null_not_empty_strings(db, loaded):
    loaded([trip("R1", rideable="electric_bike", frm=None, to=B)])
    r = rows_of(db)[0]
    assert r["start_station_id"] is None and r["end_station_id"] == "31002"


def test_whitespace_is_stripped_and_iso_timestamps_normalised(db, loaded):
    loaded([trip("R1", member=" casual ", start_station_id=" 31001 ", started_at="2026-02-10T08:00:00.000Z",
                 ended_at="2026-02-10T08:10:00.000Z")])
    r = rows_of(db)[0]
    assert (r["member_type"], r["start_station_id"], r["started_at"]) == ("casual", "31001", "2026-02-10 08:00:00.000")


@pytest.mark.parametrize("seconds,expect", [(59.9, "under_60_seconds"), (60.0, None), (86400.0, None), (86400.5, "over_24_hours")])
def test_duration_boundaries(loaded, seconds, expect):
    s = loaded([trip("R1", seconds=seconds)])
    assert s["rejected"] == ({expect: 1} if expect else {})


@pytest.mark.parametrize("override,reason", [
    ({"ended_at": "2026-02-10 07:00:00.000"}, "ended_before_started"),
    ({"started_at": "not a time"}, "bad_timestamp"),
    ({"ended_at": ""}, "bad_timestamp"),
    ({"member_casual": "subscriber"}, "unknown_member_type"),
    ({"member_casual": ""}, "unknown_member_type"),
    ({"end_lat": ""}, "missing_coordinates"),
    ({"start_lng": ""}, "missing_coordinates"),
    ({"start_lat": 0.0, "start_lng": 0.0}, "outside_service_area"),
    ({"end_lng": -122.4}, "outside_service_area"),
    ({"ride_id": ""}, "missing_ride_id"),
])
def test_each_rejection_reason(db, loaded, override, reason):
    bad = trip("R1")
    bad.update(override)
    s = loaded([bad, trip("OK", start="2026-02-10 09:00:00.000")])
    assert s["rejected"] == {reason: 1} and s["kept"] == 1
    assert db.execute("SELECT reason FROM rejected_trips").fetchone()[0] == reason


def test_a_row_with_two_problems_is_counted_once_under_the_first_rule(loaded):
    s = loaded([trip("R1", seconds=30, end_lat="")])
    assert s["rejected"] == {"under_60_seconds": 1}


def test_duplicate_ride_ids_within_and_across_files(db, tmp_path):
    first = write_csv(tmp_path / "202601-x.csv", [trip("R1"), trip("R1", start="2026-02-11 08:00:00.000"), trip("R2")])
    second = write_csv(tmp_path / "202602-x.csv", [trip("R2"), trip("R3")])
    assert load.load_file(db, first)["rejected"] == {"duplicate_ride_id": 1}
    assert load.load_file(db, second)["rejected"] == {"duplicate_ride_id": 1}
    assert [r["ride_id"] for r in rows_of(db)] == ["R1", "R2", "R3"]
    assert db.execute("SELECT source_file FROM trips WHERE ride_id='R2'").fetchone()[0] == "202601-x.csv"


def test_loading_the_same_file_twice_changes_nothing(db, tmp_path):
    path = write_csv(tmp_path / "202602-x.csv", [trip("R1"), trip("R2", seconds=5), trip("R3")])
    for _ in range(3):
        load.load_file(db, path)
    assert db.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 2
    assert [tuple(r) for r in db.execute("SELECT reason, rows FROM cleaning_log")] == [("under_60_seconds", 1)]
    assert db.execute("SELECT COUNT(*) FROM rejected_trips").fetchone()[0] == 1
    assert [tuple(r) for r in db.execute("SELECT rows_read, rows_kept FROM loads")] == [(3, 2)]


def test_reloading_a_corrected_file_replaces_its_rows(db, tmp_path):
    path = tmp_path / "202602-x.csv"
    write_csv(path, [trip("R1"), trip("R2")])
    load.load_file(db, str(path))
    write_csv(path, [trip("R9")])
    load.load_file(db, str(path))
    assert [r["ride_id"] for r in rows_of(db)] == ["R9"]


def test_zip_with_macos_junk_and_bom_csv_both_load(db, tmp_path):
    z = write_zip(tmp_path / "202602-capitalbikeshare-tripdata.zip", [trip("R1")])
    assert load.load_file(db, z)["kept"] == 1
    p = tmp_path / "202603-capitalbikeshare-tripdata.csv"
    p.write_text(csv_text([trip("R2")], bom=True), encoding="utf-8")
    assert load.load_file(db, str(p))["kept"] == 1


def test_old_layout_and_missing_columns_give_clear_errors(db, tmp_path):
    old = tmp_path / "old.csv"
    old.write_text("Duration,Start date,End date,Start station number,Start station,End station number,End station,Bike number,Member type\n")
    with pytest.raises(load.SchemaError, match="pre-2020"):
        load.load_file(db, str(old))
    short = write_csv(tmp_path / "short.csv", [trip("R1")], header=[h for h in HEADER if h != "member_casual"])
    with pytest.raises(load.SchemaError, match="member_casual"):
        load.load_file(db, short)


def test_failed_load_leaves_earlier_data_untouched(db, tmp_path):
    good = write_csv(tmp_path / "202602-x.csv", [trip("R1")])
    load.load_file(db, good)
    bad = tmp_path / "202603-x.csv"
    bad.write_text("ride_id,other\n1,2\n")
    with pytest.raises(load.SchemaError):
        load.load_file(db, str(bad))
    assert db.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 1


def test_database_constraints_back_up_the_cleaning_rules(db, loaded):
    loaded([trip("R1")])
    base = ("INSERT INTO trips (ride_id, rideable_type, member_type, started_at, ended_at, duration_s, start_date, start_hour,"
            " start_dow, end_date, end_hour, end_dow, start_lat, start_lng, end_lat, end_lng, source_file) "
            "VALUES (?, 'classic_bike', ?, 'a', 'b', ?, 'd', ?, 0, 'd', 0, 0, 1, 1, 1, 1, 'f')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(base, ("X1", "subscriber", 600, 8))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(base, ("X2", "member", 10, 8))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(base, ("X3", "member", 600, 24))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(base, ("R1", "member", 600, 8))          # duplicate primary key


def test_station_location_is_the_most_common_coordinate_not_a_noisy_gps_fix(db, loaded):
    noisy = (A[0], A[1], 38.95, -77.10)                    # an e-bike whose GPS drifted
    loaded([trip("R1", frm=A, to=B), trip("R2", frm=A, to=B), trip("R3", rideable="electric_bike", frm=noisy, to=B)])
    row = db.execute("SELECT lat, lng FROM stations WHERE station_id='31001'").fetchone()
    assert (row["lat"], row["lng"]) == (38.90, -77.04)


def test_station_name_is_the_latest_seen_and_event_counts_cover_both_ends(db, tmp_path):
    first = write_csv(tmp_path / "202601-x.csv", [trip("R1", start="2026-01-10 08:00:00.000", frm=A, to=B)])
    renamed = ("31001", "Alpha Street (renamed)", 38.90, -77.04)
    second = write_csv(tmp_path / "202602-x.csv", [trip("R2", start="2026-02-10 08:00:00.000", frm=renamed, to=C)])
    load.load_file(db, first)
    load.load_file(db, second)
    load.build_stations(db)
    assert db.execute("SELECT name FROM stations WHERE station_id='31001'").fetchone()[0] == "Alpha Street (renamed)"
    assert db.execute("SELECT n_events FROM stations WHERE station_id='31001'").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 3


def test_analysis_window_skips_rides_that_started_before_the_first_loaded_month(db, loaded):
    loaded([trip("EDGE", start="2026-01-31 23:50:00.000", seconds=1200),            # ended Feb 1, so it is in the Feb file
            trip("IN", start="2026-02-01 00:10:00.000")])
    assert db.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 2
    assert [r[0] for r in db.execute("SELECT ride_id FROM analysis_trips")] == ["IN"]


def test_station_events_has_one_departure_and_one_arrival_per_docked_trip(db, loaded):
    loaded([trip("R1", frm=A, to=B), trip("R2", rideable="electric_bike", frm=None, to=B)])
    events = [tuple(r) for r in db.execute("SELECT station_id, delta FROM station_events ORDER BY station_id, delta")]
    assert events == [("31001", -1), ("31002", 1), ("31002", 1)]


def test_large_file_is_loaded_in_batches(db, tmp_path):
    path = write_csv(tmp_path / "202602-x.csv", [trip("R%d" % i) for i in range(2500)])
    s = load.load_file(db, path, batch=400)
    assert (s["read"], s["kept"]) == (2500, 2500)
