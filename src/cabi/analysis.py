"""Run the SQL analyses and return pandas DataFrames.

All the counting happens in SQL (src/cabi/sql); pandas is used to shape, label and plot results.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Tuple

import pandas as pd

from .load import sql_text

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MEDIAN_KEYS = {"member_type", "rideable_type"}


def query(conn: sqlite3.Connection, name: str, params: dict = None) -> pd.DataFrame:
    return pd.read_sql_query(sql_text(name + ".sql"), conn, params=params or {})


def coverage(conn) -> dict:
    row = query(conn, "coverage").iloc[0]
    return {k: (row[k].item() if hasattr(row[k], "item") else row[k]) for k in row.index}


def monthly(conn) -> pd.DataFrame:
    df = query(conn, "monthly")
    df["ebike_share"] = df.ebike_trips / df.trips
    df["member_share"] = df.member_trips / df.trips
    df["trips_per_day"] = df.trips / df.days
    return df


def daily(conn) -> pd.DataFrame:
    df = query(conn, "daily")
    df["day_name"] = df.dow.map(lambda d: DAY_NAMES[int(d)])
    df["is_weekend"] = df.dow >= 5
    return df


def hourly(conn) -> pd.DataFrame:
    """Trips per day by hour, with hours that had no trips filled in as zero."""
    df = query(conn, "hourly")
    if df.empty:
        return df
    n_days = df.drop_duplicates("day_type").set_index("day_type").n_days
    full = pd.MultiIndex.from_product([sorted(df.day_type.unique()), sorted(df.member_type.unique()), range(24)],
                                      names=["day_type", "member_type", "hour"])
    df = df.set_index(["day_type", "member_type", "hour"]).reindex(full).reset_index()
    df["trips"] = df.trips.fillna(0).astype(int)
    df["n_days"] = df.day_type.map(n_days).astype(int)
    df["trips_per_day"] = df.trips / df.n_days
    return df


def median_duration(conn, by: Tuple[str, ...] = ("member_type",)) -> pd.DataFrame:
    """Median trip length in minutes, computed in SQL with window functions."""
    if not by or not set(by) <= MEDIAN_KEYS:
        raise ValueError("by must be a non-empty subset of %s" % sorted(MEDIAN_KEYS))
    keys = ", ".join(by)            # safe: checked against a fixed whitelist above
    sql = ("WITH ranked AS (SELECT %(k)s, duration_s, "
           "ROW_NUMBER() OVER (PARTITION BY %(k)s ORDER BY duration_s) AS rn, "
           "COUNT(*) OVER (PARTITION BY %(k)s) AS cnt FROM analysis_trips) "
           "SELECT %(k)s, MAX(cnt) AS trips, AVG(duration_s) / 60.0 AS median_minutes FROM ranked "
           "WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2) GROUP BY %(k)s ORDER BY %(k)s") % {"k": keys}
    return pd.read_sql_query(sql, conn)


def duration_hist(conn) -> pd.DataFrame:
    return query(conn, "duration_hist")


def station_flow(conn, am: Tuple[int, int] = (6, 10), pm: Tuple[int, int] = (16, 20), gap: int = 5) -> pd.DataFrame:
    return query(conn, "station_flow", {"am_start": am[0], "am_end": am[1], "pm_start": pm[0], "pm_end": pm[1], "gap": gap})


def top_routes(conn, n: int = 15) -> pd.DataFrame:
    return query(conn, "top_routes", {"n": n})


def round_trips(conn) -> pd.DataFrame:
    return query(conn, "round_trips")


def docking(conn) -> pd.DataFrame:
    return query(conn, "docking")


def dockless_cells(conn) -> pd.DataFrame:
    return query(conn, "dockless_cells")


def quality(conn) -> pd.DataFrame:
    return query(conn, "quality")


def everything(conn) -> Dict[str, pd.DataFrame]:
    return {
        "monthly": monthly(conn), "daily": daily(conn), "hourly": hourly(conn),
        "median_duration_by_member": median_duration(conn, ("member_type",)),
        "median_duration_by_type": median_duration(conn, ("member_type", "rideable_type")),
        "duration_hist": duration_hist(conn), "station_flow": station_flow(conn),
        "top_routes": top_routes(conn), "round_trips": round_trips(conn), "docking": docking(conn),
        "dockless_cells": dockless_cells(conn), "quality": quality(conn),
    }
