import statistics
from collections import Counter, defaultdict

import pytest

from conftest import A, B, C, trip, write_csv
from world import STATIONS, flow_oracle, random_world
from cabi import analysis, load


@pytest.fixture
def world(db, tmp_path):
    rows, truth = random_world(seed=1, n=1500)
    load.load_file(db, write_csv(tmp_path / "202602-capitalbikeshare-tripdata.csv", rows))
    load.build_stations(db)
    return db, truth


def test_station_flow_matches_an_independent_python_calculation(world):
    db, truth = world
    expected = flow_oracle(truth)
    df = analysis.station_flow(db).set_index("station_id")
    assert set(df.index) == set(expected)
    for station, want in expected.items():
        for column, value in want.items():
            assert df.loc[station, column] == pytest.approx(value), (station, column)


def test_station_flow_windows_and_gap_are_parameters(world):
    db, truth = world
    expected = flow_oracle(truth, am=(7, 9), pm=(17, 19), gap=3)
    df = analysis.station_flow(db, am=(7, 9), pm=(17, 19), gap=3).set_index("station_id")
    for station, want in expected.items():
        assert df.loc[station, "am_drain_share"] == pytest.approx(want["am_drain_share"])
        assert df.loc[station, "pm_net_per_day"] == pytest.approx(want["pm_net_per_day"])


def test_hourly_profile_matches_python(world):
    db, truth = world
    df = analysis.hourly(db)
    counts, dates = Counter(), defaultdict(set)
    for t in truth:
        kind = "weekend" if t["start"].weekday() >= 5 else "weekday"
        counts[(kind, t["member"], t["start"].hour)] += 1
        dates[kind].add(t["start"].date())
    assert len(df) == 2 * 2 * 24                                          # every hour present, even empty ones
    for r in df.itertuples():
        assert r.trips == counts[(r.day_type, r.member_type, r.hour)]
        assert r.trips_per_day == pytest.approx(r.trips / len(dates[r.day_type]))


def test_medians_match_python_including_even_and_odd_group_sizes(world):
    db, truth = world
    by_member = analysis.median_duration(db, ("member_type",)).set_index("member_type")
    for member in ("member", "casual"):
        want = statistics.median(t["seconds"] for t in truth if t["member"] == member) / 60
        assert by_member.loc[member, "median_minutes"] == pytest.approx(want, abs=1e-6)
    both = analysis.median_duration(db, ("member_type", "rideable_type"))
    for r in both.itertuples():
        group = [t["seconds"] for t in truth if t["member"] == r.member_type and t["rideable"] == r.rideable_type]
        assert r.trips == len(group) and r.median_minutes == pytest.approx(statistics.median(group) / 60, abs=1e-6)


def test_median_helper_rejects_unknown_columns(world):
    db, _ = world
    with pytest.raises(ValueError):
        analysis.median_duration(db, ("member_type; DROP TABLE trips",))


def test_monthly_daily_and_coverage_counts(world):
    db, truth = world
    m = analysis.monthly(db).iloc[0]
    assert m.trips == len(truth) and m.ebike_trips == sum(t["rideable"] == "electric_bike" for t in truth)
    assert m.dockless_starts == sum(t["frm"] is None for t in truth)
    assert m.ebike_share == pytest.approx(m.ebike_trips / m.trips)
    d = analysis.daily(db)
    assert d.trips.sum() == len(truth) and set(d.day_name) <= set(analysis.DAY_NAMES)
    assert (d.is_weekend == (d.dow >= 5)).all()
    cov = analysis.coverage(db)
    assert cov["trips"] == len(truth) and cov["stations"] == len(STATIONS) and cov["files"] == 1


def test_top_routes_round_trips_docking_and_dockless_cells(world):
    db, truth = world
    pairs = Counter((t["frm"], t["to"]) for t in truth if t["frm"] and t["to"] and t["frm"] != t["to"])
    routes = analysis.top_routes(db, n=5)
    assert list(routes.trips) == sorted(pairs.values(), reverse=True)[:5]
    docked = [t for t in truth if t["frm"] and t["to"]]
    rt = analysis.round_trips(db).set_index("member_type")
    for member in ("member", "casual"):
        group = [t for t in docked if t["member"] == member]
        assert rt.loc[member, "docked_trips"] == len(group)
        assert rt.loc[member, "round_trips"] == sum(t["frm"] == t["to"] for t in group)
    dk = analysis.docking(db)
    assert dk.loc[dk.rideable_type == "classic_bike", "trips"].sum() == dk.loc[dk.rideable_type == "classic_bike", "both_docked"].sum()
    cells = analysis.dockless_cells(db)
    starts = cells[cells.end_kind == "start"]
    assert starts.trips.sum() == sum(t["frm"] is None for t in truth)
    assert Counter(t["start_cell"] for t in truth if t["frm"] is None) == Counter(
        {(r.lat, r.lng): r.trips for r in starts.itertuples()})


def test_quality_table_lists_rejections(db, tmp_path):
    rows = [trip("A1"), trip("A2", seconds=10), trip("A3", seconds=20), trip("A4", seconds=90000)]
    load.load_file(db, write_csv(tmp_path / "202602-x.csv", rows))
    load.build_stations(db)
    q = analysis.quality(db)
    assert dict(zip(q.reason, q.rows)) == {"under_60_seconds": 2, "over_24_hours": 1}
    assert list(q.reason)[0] == "under_60_seconds"                         # biggest first


def test_hand_checked_flow_example(db, tmp_path):
    """Small enough to verify by eye: A empties on Mon and Tue mornings, B fills."""
    rows = []
    for k, day in enumerate(["2026-02-09", "2026-02-10"]):
        for j in range(6):
            rows.append(trip("M%d%d" % (k, j), start="%s 08:%02d:00.000" % (day, j), frm=A, to=B))
    for day in ["2026-02-09", "2026-02-10", "2026-02-11", "2026-02-12", "2026-02-13"]:
        rows.append(trip("N" + day, start=day + " 12:00:00.000", frm=B, to=C, member="casual"))      # noon: outside both peaks
    for j in range(3):
        rows.append(trip("P%d" % j, start="2026-02-11 17:%02d:00.000" % (30 + j), frm=C, to=A))
    load.load_file(db, write_csv(tmp_path / "202602-x.csv", rows))
    load.build_stations(db)
    df = analysis.station_flow(db).set_index("station_id")
    a, b, c = df.loc["31001"], df.loc["31002"], df.loc["31003"]
    assert a.weekdays == 5
    assert (a.am_out_per_day, a.am_net_per_day, a.am_drain_share) == (pytest.approx(12 / 5), pytest.approx(-12 / 5), pytest.approx(2 / 5))
    assert (b.am_in_per_day, b.am_fill_share) == (pytest.approx(12 / 5), pytest.approx(2 / 5))
    assert (c.pm_net_per_day, a.pm_net_per_day) == (pytest.approx(-3 / 5), pytest.approx(3 / 5))
    assert b.events_per_day == pytest.approx((12 + 5) / 5)        # 12 morning arrivals plus 5 noon departures
