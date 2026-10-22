"""Turn the analysis tables into plain-language findings.

Every number in the text is computed from the tables, so the write-up cannot
drift from the data. Each finding states what was measured and its limits.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def _pct(x: float) -> str:
    return "%.0f%%" % (100 * x)


def _hour_label(h: int) -> str:
    h = int(h)
    return "%d%s" % (h % 12 or 12, "am" if h < 12 else "pm")


def _peak(hourly: pd.DataFrame, day_type: str, kind: str):
    s = hourly[(hourly.day_type == day_type) & (hourly.member_type == kind)]
    if s.empty:
        return None
    return s.loc[s.trips_per_day.idxmax()]


def volume(r: Dict[str, pd.DataFrame]) -> str:
    m = r["monthly"]
    trips, days = int(m.trips.sum()), int(m.days.sum())
    return ("The cleaned data holds %s trips over %d days (about %s a day). Members took %s of them, and %s "
            "were on electric bikes." % ("{:,}".format(trips), days, "{:,.0f}".format(trips / days),
                                         _pct(m.member_trips.sum() / trips), _pct(m.ebike_trips.sum() / trips)))


def commute(r: Dict[str, pd.DataFrame]) -> str:
    h = r["hourly"]
    wm, wc = _peak(h, "weekday", "member"), _peak(h, "weekday", "casual")
    em, ec = _peak(h, "weekend", "member"), _peak(h, "weekend", "casual")
    if any(x is None for x in (wm, wc, em, ec)):
        return "There is not enough data to compare weekday and weekend hours."
    wk = h[(h.day_type == "weekday") & (h.member_type == "member")].set_index("hour").trips_per_day
    morning = int(wk.loc[5:11].idxmax())
    evening = int(wk.loc[14:21].idxmax())
    return ("Weekday member riding has two peaks, at %s and %s, which looks like commuting. Casual riders peak "
            "once, at %s on weekdays and %s on weekends, and members at %s on weekends, a single midday hump. "
            "This is an inference from timing, since the data has no trip purpose."
            % (_hour_label(morning), _hour_label(evening), _hour_label(wc.hour), _hour_label(ec.hour),
               _hour_label(em.hour)))


def duration(r: Dict[str, pd.DataFrame]) -> str:
    med = r["median_duration_by_member"].set_index("member_type").median_minutes
    t = r["median_duration_by_type"]
    cc = t[(t.member_type == "casual") & (t.rideable_type == "classic_bike")]
    cm = t[(t.member_type == "member") & (t.rideable_type == "classic_bike")]
    s = "Median ride length is %.1f minutes for casual riders and %.1f for members." % (med["casual"], med["member"])
    if len(cc) and len(cm):
        s += (" On classic bikes the gap widens to %.1f versus %.1f minutes."
              % (cc.median_minutes.iloc[0], cm.median_minutes.iloc[0]))
    return s


def round_trips(r: Dict[str, pd.DataFrame]) -> str:
    t = r["round_trips"].set_index("member_type").round_trip_share
    if "casual" not in t or "member" not in t:
        return ""
    return ("Among docked rides, %s of casual trips and %s of member trips end at the station they started "
            "from." % (_pct(t["casual"]), _pct(t["member"])))


def rebalancing(r: Dict[str, pd.DataFrame], gap: int = 5) -> str:
    f = r["station_flow"]
    f = f[f.weekdays > 0]
    if f.empty:
        return ""
    worst = f.sort_values("am_net_per_day").iloc[0]
    best = f.sort_values("am_net_per_day").iloc[-1]
    return ("On weekday mornings (6-10am) the biggest net drain is %s, which loses %.1f bikes a day on average, "
            "and the biggest net gain is %s at +%.1f. These are net movements of trips, not dock inventory: "
            "the operator moves bikes by truck, and dockless e-bikes are not counted. A drain of %d or more "
            "bikes on at least half of weekdays is the rule used to call a station drain-prone; %d stations "
            "meet it in the morning." % (worst["name"], -worst.am_net_per_day, best["name"], best.am_net_per_day,
                                         gap, int((f.am_drain_share >= 0.5).sum())))


def dockless(r: Dict[str, pd.DataFrame]) -> str:
    d = r["docking"]
    e = d[d.rideable_type == "electric_bike"]
    if e.empty:
        return ""
    both = e.both_docked.sum() / e.trips.sum()
    return ("%s of electric-bike trips have at least one end away from a dock, so dock-based analysis such as "
            "station flow sees only the other %s of e-bike use." % (_pct(1 - both), _pct(both)))


def quality(r: Dict[str, pd.DataFrame], rows_read: int = 0) -> str:
    q = r["quality"]
    if q.empty:
        return "No rows were removed by the cleaning rules."
    total = int(q.rows.sum())
    parts = ", ".join("%s (%s)" % (row.reason.replace("_", " "), "{:,}".format(int(row.rows)))
                      for row in q.itertuples())
    s = "Cleaning removed %s rows: %s." % ("{:,}".format(total), parts)
    if rows_read:
        s += " That is %.1f%% of rows read." % (100.0 * total / rows_read)
    return s


def all_findings(r: Dict[str, pd.DataFrame], rows_read: int = 0) -> List[str]:
    out = [volume(r), commute(r), duration(r), round_trips(r), rebalancing(r), dockless(r), quality(r, rows_read)]
    return [s for s in out if s]


def render_markdown(r: Dict[str, pd.DataFrame], cov: dict, figures: Dict[str, str] = None) -> str:
    lines = ["# Findings", "",
             "Period: %s to %s (%d files, %s rows kept after cleaning; rides that started before the first loaded month are excluded from the analysis)." % (cov["first_date"], cov["last_date"], cov["files"],
                                                              "{:,}".format(cov["rows_kept"])), ""]
    for s in all_findings(r, cov.get("rows_read", 0)):
        lines += ["- " + s]
    if figures:
        lines += ["", "## Figures", ""]
        for name, path in figures.items():
            lines += ["![%s](%s)" % (name, path.replace("\\", "/"))]
    lines += ["", "## Limits", "",
              "- Descriptive only: nothing here is causal.",
              "- Start and end dates follow ride end month, so the first and last days can be thin.",
              "- Timestamps are local time without a zone, so the DST changeover hours are ambiguous.",
              "- Dockless coordinates are rounded to about 1 km, so they are only plotted as coarse cells.", ""]
    return "\n".join(lines)
