"""Static figures (matplotlib, Agg backend).

Colour rules, following the dataviz method:
  * member / casual are two categorical hues (blue, orange), validated
    all-pairs for colour-vision deficiency in both themes;
  * net station flow is a diverging scale (red = drains, blue = fills) with a
    neutral grey midpoint pinned to zero;
  * text uses ink tokens, never the series colour; grid lines are hairlines.
Every figure takes theme="light" or "dark" and is built from the DataFrames in
cabi.analysis, so the numbers on the page are the numbers in the tables.
"""
from __future__ import annotations

import os
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402

THEMES: Dict[str, Dict[str, str]] = {
    "light": dict(
        surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
        grid="#e1e0d9", axis="#c3c2b7", member="#2a78d6", casual="#eb6834",
        pos="#2a78d6", neg="#e34948", mid="#f0efec",
    ),
    "dark": dict(
        surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781",
        grid="#2c2c2a", axis="#383835", member="#3987e5", casual="#d95926",
        pos="#3987e5", neg="#e66767", mid="#383835",
    ),
}
LABELS = {"member": "Member", "casual": "Casual"}


def _theme(name: str) -> Dict[str, str]:
    if name not in THEMES:
        raise ValueError("theme must be one of %s" % sorted(THEMES))
    return THEMES[name]


def _style(ax, t, grid_axis="y"):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["axis"])
        ax.spines[side].set_linewidth(1)
    ax.tick_params(colors=t["muted"], labelsize=9, length=0)
    ax.grid(axis=grid_axis, color=t["grid"], linewidth=1, linestyle="-")
    ax.set_axisbelow(True)


def _fig(t, w, h):
    fig = plt.figure(figsize=(w, h), dpi=160, facecolor=t["surface"])
    return fig


def _title(fig, t, title, subtitle=None):
    fig.text(0.02, 0.965, title, color=t["ink"], fontsize=13, fontweight="bold", va="top")
    if subtitle:
        fig.text(0.02, 0.915, subtitle, color=t["ink2"], fontsize=9.5, va="top")


def _legend(fig, ax, t, loc="upper right"):
    leg = ax.legend(loc=loc, frameon=False, fontsize=9, handlelength=1.6)
    for text in leg.get_texts():
        text.set_color(t["ink2"])
    return leg


def _compact(v, _pos=None):
    v = float(v)
    if abs(v) >= 1000:
        s = "%.1fK" % (v / 1000.0)
        return s.replace(".0K", "K")
    return "%g" % v


def hourly_profile(hourly: pd.DataFrame, theme="light"):
    """Trips per day by hour, weekday vs weekend panels, member vs casual."""
    t = _theme(theme)
    fig = _fig(t, 9, 4.2)
    _title(fig, t, "When people ride",
           "Average trips per day by start hour, split by rider type")
    axes = fig.subplots(1, 2, sharey=True, gridspec_kw=dict(top=0.78, bottom=0.14, left=0.08, right=0.98, wspace=0.08))
    for ax, day_type, name in zip(axes, ("weekday", "weekend"), ("Weekdays", "Weekends")):
        _style(ax, t)
        sub = hourly[hourly["day_type"] == day_type]
        for kind in ("member", "casual"):
            s = sub[sub["member_type"] == kind].sort_values("hour")
            ax.plot(s["hour"], s["trips_per_day"], color=t[kind], linewidth=2,
                    solid_capstyle="round", label=LABELS[kind])
            if len(s):
                i = int(s["trips_per_day"].values.argmax())
                ax.scatter([s["hour"].values[i]], [s["trips_per_day"].values[i]], s=44,
                           color=t[kind], edgecolor=t["surface"], linewidth=2, zorder=3)
        ax.set_title(name, color=t["ink2"], fontsize=10, loc="left", pad=8)
        ax.set_xticks([0, 6, 12, 18])
        ax.set_xticklabels(["12am", "6am", "12pm", "6pm"])
        ax.set_xlim(0, 23)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(_compact))
    _legend(fig, axes[0], t, "upper left")
    axes[0].set_ylabel("trips per day", color=t["muted"], fontsize=9)
    return fig


def daily_volume(daily: pd.DataFrame, theme="light"):
    """Daily trips over the loaded period, weekends marked."""
    t = _theme(theme)
    fig = _fig(t, 9, 3.8)
    _title(fig, t, "Daily trips", "Weekend days are shaded; one line per rider type")
    ax = fig.add_axes([0.08, 0.14, 0.9, 0.64])
    _style(ax, t)
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    for _, r in d[d["is_weekend"].astype(bool)].iterrows():
        ax.axvspan(r["date"] - pd.Timedelta(hours=12), r["date"] + pd.Timedelta(hours=12),
                   color=t["grid"], linewidth=0, alpha=0.8, zorder=0)
    for kind in ("member", "casual"):
        ax.plot(d["date"], d[kind + "_trips"], color=t[kind], linewidth=2,
                solid_capstyle="round", label=LABELS[kind])
        ax.scatter([d["date"].iloc[-1]], [d[kind + "_trips"].iloc[-1]], s=44, color=t[kind],
                   edgecolor=t["surface"], linewidth=2, zorder=3)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(_compact))
    ax.set_ylabel("trips", color=t["muted"], fontsize=9)
    locator = matplotlib.dates.AutoDateLocator(minticks=4, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(matplotlib.dates.ConciseDateFormatter(locator))
    _legend(fig, ax, t, "upper right")
    return fig


def duration_by_type(med: pd.DataFrame, theme="light"):
    """Median ride length for member / casual by bike type (horizontal bars)."""
    t = _theme(theme)
    fig = _fig(t, 8, 3.6)
    _title(fig, t, "How long rides last", "Median ride length in minutes")
    ax = fig.add_axes([0.2, 0.16, 0.74, 0.56])
    _style(ax, t, grid_axis="x")
    labels, ypos, k = [], [], 0
    bar_h = 0.28
    for rt, g in med.groupby("rideable_type", sort=True):
        for j, kind in enumerate(("member", "casual")):
            row = g[g["member_type"] == kind]
            if row.empty:
                continue
            v = float(row["median_minutes"].iloc[0])
            y = k + (j - 0.5) * (bar_h + 0.06)
            ax.barh(y, v, height=bar_h, edgecolor=t["surface"], linewidth=2, color=t[kind], label=LABELS[kind] if k == 0 else None)
            ax.text(v + 0.2, y, "%.1f" % v, va="center", color=t["ink2"], fontsize=9)
        labels.append(str(rt).replace("_", " "))
        ypos.append(k)
        k += 1
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, color=t["ink2"], fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(left=0)
    ax.set_xlabel("minutes", color=t["muted"], fontsize=9)
    handles = [plt.Line2D([0], [0], color=t[k], linewidth=6) for k in ("member", "casual")]
    leg = ax.legend(handles, [LABELS["member"], LABELS["casual"]], loc="lower right", frameon=False, fontsize=9)
    for text in leg.get_texts():
        text.set_color(t["ink2"])
    return fig


def station_map(flow: pd.DataFrame, window="am", theme="light"):
    """Docked stations coloured by weekday net bikes per day in a window.

    Negative (red) = more departures than arrivals, so the dock tends to empty.
    Positive (blue) = more arrivals, so it tends to fill.
    """
    if window not in ("am", "pm"):
        raise ValueError("window must be 'am' or 'pm'")
    t = _theme(theme)
    col = window + "_net_per_day"
    d = flow.dropna(subset=["lat", "lng", col]).copy()
    d = d.reindex(d[col].abs().sort_values().index)  # strongest on top
    cmap = LinearSegmentedColormap.from_list("div", [t["neg"], t["mid"], t["pos"]])
    cap = float(np.percentile(d[col].abs(), 97)) if len(d) else 1.0
    cap = max(cap, 1e-6)
    norm = TwoSlopeNorm(vmin=-cap, vcenter=0.0, vmax=cap)
    fig = _fig(t, 8, 6.4)
    when = "6-10am" if window == "am" else "4-8pm"
    _title(fig, t, "Where docks empty and fill (%s, weekdays)" % when,
           "Net bikes per weekday: arrivals minus departures at each station")
    ax = fig.add_axes([0.03, 0.07, 0.82, 0.75])
    ax.set_facecolor(t["surface"])
    lat0 = float(d["lat"].median()) if len(d) else 38.9
    ax.set_aspect(1.0 / np.cos(np.radians(lat0)))
    if len(d) >= 20:  # zoom to where the stations are; outliers stay in the data
        x0, x1 = np.percentile(d["lng"], [2, 98])
        y0, y1 = np.percentile(d["lat"], [2, 98])
        padx, pady = (x1 - x0) * 0.04, (y1 - y0) * 0.04
        ax.set_xlim(x0 - padx, x1 + padx)
        ax.set_ylim(y0 - pady, y1 + pady)
    size = 10 + 90 * np.clip(d["events_per_day"] / max(d["events_per_day"].max(), 1e-6), 0, 1)
    sc = ax.scatter(d["lng"], d["lat"], c=d[col], cmap=cmap, norm=norm, s=size,
                    edgecolor=t["surface"], linewidth=0.8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    cax = fig.add_axes([0.89, 0.25, 0.022, 0.4])
    cb = fig.colorbar(sc, cax=cax)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=t["muted"], labelsize=8, length=0)
    cb.set_label("net bikes/day (clipped at 97th pct)", color=t["muted"], fontsize=8)
    fig.text(0.89, 0.68, "fills", color=t["ink2"], fontsize=9)
    fig.text(0.89, 0.2, "drains", color=t["ink2"], fontsize=9)
    fig.text(0.03, 0.02, "Marker area scales with total weekday events. Net flow is not dock inventory.",
             color=t["muted"], fontsize=8)
    return fig


def quality_bars(quality: pd.DataFrame, theme="light"):
    """Rows removed by the cleaning rules, largest first."""
    t = _theme(theme)
    q = quality.sort_values("rows", ascending=False)
    fig = _fig(t, 8, 1.6 + 0.42 * max(len(q), 1))
    _title(fig, t, "Rows removed by cleaning", "One reason per row; first matching rule wins")
    ax = fig.add_axes([0.28, 0.14, 0.66, 0.6])
    _style(ax, t, grid_axis="x")
    if len(q):
        ax.barh(q["reason"].str.replace("_", " "), q["rows"], height=0.5, color=t["member"])
        for y, v in enumerate(q["rows"]):
            ax.text(v, y, "  {:,}".format(int(v)), va="center", color=t["ink2"], fontsize=9)
        ax.invert_yaxis()
    ax.set_xlim(left=0, right=max(float(q["rows"].max()) * 1.18, 1.0) if len(q) else 1)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(_compact))
    ax.tick_params(axis="y", labelcolor=t["ink2"], labelsize=10)
    return fig


def save_all(results: Dict[str, pd.DataFrame], out_dir: str, theme="light") -> Dict[str, str]:
    """Render every figure into out_dir; returns {name: path}."""
    os.makedirs(out_dir, exist_ok=True)
    suffix = "" if theme == "light" else "-" + theme
    jobs = {
        "hourly": lambda: hourly_profile(results["hourly"], theme),
        "daily": lambda: daily_volume(results["daily"], theme),
        "duration": lambda: duration_by_type(results["median_duration_by_type"], theme),
        "stations_am": lambda: station_map(results["station_flow"], "am", theme),
        "stations_pm": lambda: station_map(results["station_flow"], "pm", theme),
        "quality": lambda: quality_bars(results["quality"], theme),
    }
    paths = {}
    for name, make in jobs.items():
        fig = make()
        path = os.path.join(out_dir, name + suffix + ".png")
        fig.savefig(path, facecolor=fig.get_facecolor())
        plt.close(fig)
        paths[name] = path
    return paths
