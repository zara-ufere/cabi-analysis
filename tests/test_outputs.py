"""Figures, findings and the command line, run against a small synthetic month."""
import os

import pytest

from cabi import analysis, cli, figures, findings, load
from conftest import write_zip
from world import random_world


@pytest.fixture
def results(db, loaded):
    rows, _ = random_world(seed=3, n=900)
    loaded(rows)
    return analysis.everything(db), analysis.coverage(db)


def test_save_all_writes_valid_pngs_in_both_themes(results, tmp_path):
    r, _ = results
    for theme in ("light", "dark"):
        paths = figures.save_all(r, str(tmp_path), theme)
        assert len(paths) == 6
        for p in paths.values():
            with open(p, "rb") as fh:
                assert fh.read(8) == b"\x89PNG\r\n\x1a\n"
    assert os.path.exists(tmp_path / "hourly.png") and os.path.exists(tmp_path / "hourly-dark.png")


def test_unknown_theme_and_window_are_rejected(results):
    r, _ = results
    with pytest.raises(ValueError):
        figures.hourly_profile(r["hourly"], theme="sepia")
    with pytest.raises(ValueError):
        figures.station_map(r["station_flow"], window="noon")


def test_categorical_colours_are_the_validated_palette():
    assert figures.THEMES["light"]["member"] == "#2a78d6" and figures.THEMES["light"]["casual"] == "#eb6834"
    assert figures.THEMES["dark"]["member"] == "#3987e5" and figures.THEMES["dark"]["casual"] == "#d95926"


def test_findings_quote_numbers_from_the_tables(results):
    r, cov = results
    text = "\n".join(findings.all_findings(r, cov["rows_read"]))
    assert "{:,}".format(int(r["monthly"].trips.sum())) in text
    med = r["median_duration_by_member"].set_index("member_type").median_minutes
    assert "%.1f" % med["member"] in text
    assert "—" not in text


def test_findings_commute_peaks_match_the_seeded_hours(results):
    r, _ = results
    h = r["hourly"]
    wk = h[(h.day_type == "weekday") & (h.member_type == "member")].set_index("hour").trips_per_day
    assert int(wk.loc[5:11].idxmax()) in (7, 8, 9) and int(wk.loc[14:21].idxmax()) in (16, 17, 18)
    assert "two peaks" in findings.commute(r)


def test_hour_label():
    assert [findings._hour_label(h) for h in (0, 8, 12, 17, 23)] == ["12am", "8am", "12pm", "5pm", "11pm"]


def test_cli_load_analyze_round_trip(tmp_path, capsys):
    rows, _ = random_world(seed=5, n=400)
    z = write_zip(tmp_path / "202602-capitalbikeshare-tripdata.zip", rows)
    db, out = str(tmp_path / "c.db"), str(tmp_path / "rep")
    assert cli.main(["load", "--db", db, z]) == 0
    assert cli.main(["analyze", "--db", db, "--out", out]) == 0
    md = open(os.path.join(out, "findings.md")).read()
    assert md.startswith("# Findings") and "figures/hourly.png" in md
    assert os.path.exists(os.path.join(out, "figures", "hourly.png"))
    assert os.path.exists(os.path.join(out, "station_flow.csv"))
    assert cli.main(["quality", "--db", db]) == 0


def test_cli_reports_missing_database_and_bad_input(tmp_path, capsys):
    assert cli.main(["analyze", "--db", str(tmp_path / "nope.db"), "--out", str(tmp_path / "o")]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    assert cli.main(["load", "--db", str(tmp_path / "x.db"), str(bad)]) == 1
    assert "error" in capsys.readouterr().err


def test_cli_analyze_empty_database(tmp_path, capsys):
    db = str(tmp_path / "empty.db")
    load.connect(db).close()
    assert cli.main(["analyze", "--db", db, "--out", str(tmp_path / "o")]) == 2


def test_dockless_finding_uses_share_with_an_undocked_end(results):
    r, _ = results
    e = r["docking"][r["docking"].rideable_type == "electric_bike"]
    expected = "%.0f%%" % (100 * (1 - e.both_docked.sum() / e.trips.sum()))
    assert findings.dockless(r).startswith(expected + " of electric-bike trips")


def test_seasonality_reports_busiest_and_quietest_month():
    import pandas as pd
    months = ["2025-%02d" % i for i in range(3, 9)]
    m = pd.DataFrame({"month": months, "trips": [100, 200, 300, 400, 300, 200], "days": [10] * 6,
                      "casual_trips": [10, 40, 90, 160, 90, 40]})
    m["trips_per_day"] = m.trips / m.days
    text = findings.seasonality({"monthly": m})
    assert "2025-06 is the busiest" in text and "2025-03 the quietest" in text and "4.0 to 1" in text
    assert "40% of trips in 2025-06" in text and "against 10% in 2025-03" in text
    assert findings.seasonality({"monthly": m.head(3)}) == ""
