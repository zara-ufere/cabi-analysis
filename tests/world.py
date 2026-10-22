"""A random but reproducible set of trips, plus plain-Python helpers that recompute results
independently of the SQL, so tests can compare the two."""
import random
from datetime import datetime, timedelta

from conftest import trip

STATIONS = [("31001", "Alpha St", 38.900, -77.040), ("31002", "Bravo St", 38.910, -77.020),
            ("31003", "Charlie St", 38.920, -77.030), ("31004", "Delta St", 38.930, -77.050),
            ("31005", "Echo St", 38.940, -77.010), ("31006", "Foxtrot St", 38.950, -77.060)]


def random_world(seed=1, n=1500, first="2026-02-02", days=21):
    """Rows for the CSV and a parallel list of dicts describing what each trip should look like when clean."""
    rng = random.Random(seed)
    base = datetime.strptime(first, "%Y-%m-%d")
    rows, truth = [], []
    for i in range(n):
        rideable = rng.choice(["classic_bike", "electric_bike", "electric_bike"])
        start = base + timedelta(days=rng.randrange(days), hours=rng.randrange(24), minutes=rng.randrange(60),
                                 seconds=rng.randrange(60))
        # commute-shaped demand: more trips at 8 and 17 so the flow tests have something to find
        if rng.random() < 0.4:
            start = start.replace(hour=rng.choice([7, 8, 8, 9, 16, 17, 17, 18]))
        seconds = round(rng.uniform(60, 3000), 3)
        frm, to = rng.choice(STATIONS), rng.choice(STATIONS)
        if rideable == "electric_bike":
            if rng.random() < 0.25:
                frm = None
            if rng.random() < 0.25:
                to = None
        member = rng.choice(["member", "member", "member", "casual"])
        row = trip("W%05d" % i, rideable=rideable, start=start.strftime("%Y-%m-%d %H:%M:%S.000"), seconds=seconds,
                   member=member, frm=frm, to=to)
        if frm is None:      # dockless coordinates are rounded to two decimals in the real data
            row["start_lat"], row["start_lng"] = round(rng.uniform(38.85, 38.98), 2), round(rng.uniform(-77.12, -76.95), 2)
        if to is None:
            row["end_lat"], row["end_lng"] = round(rng.uniform(38.85, 38.98), 2), round(rng.uniform(-77.12, -76.95), 2)
        rows.append(row)
        end = start + timedelta(seconds=seconds)
        truth.append({"id": row["ride_id"], "start": start, "end": end, "seconds": seconds, "member": member,
                      "rideable": rideable, "frm": frm[0] if frm else None, "to": to[0] if to else None,
                      "start_cell": (row["start_lat"], row["start_lng"]), "end_cell": (row["end_lat"], row["end_lng"])})
    return rows, truth


def flow_oracle(truth, am=(6, 10), pm=(16, 20), gap=5):
    """Per-station weekday flow, computed with plain loops."""
    events = []
    for t in truth:
        if t["frm"]:
            events.append((t["frm"], t["start"], -1))
        if t["to"]:
            events.append((t["to"], t["end"], 1))
    weekday_dates = {e[1].date() for e in events if e[1].weekday() < 5}
    n = len(weekday_dates)
    net = {}
    for station, when, delta in events:
        if when.weekday() >= 5:
            continue
        key = (station, when.date())
        d = net.setdefault(key, {"am": 0, "pm": 0, "am_out": 0, "am_in": 0, "events": 0})
        d["events"] += 1
        if am[0] <= when.hour < am[1]:
            d["am"] += delta
            d["am_out" if delta < 0 else "am_in"] += 1
        if pm[0] <= when.hour < pm[1]:
            d["pm"] += delta
    out = {}
    for station in {k[0] for k in net}:
        days = [v for k, v in net.items() if k[0] == station]
        out[station] = {
            "weekdays": n,
            "am_net_per_day": sum(d["am"] for d in days) / n,
            "am_out_per_day": sum(d["am_out"] for d in days) / n,
            "am_in_per_day": sum(d["am_in"] for d in days) / n,
            "pm_net_per_day": sum(d["pm"] for d in days) / n,
            "am_drain_share": sum(d["am"] <= -gap for d in days) / n,
            "am_fill_share": sum(d["am"] >= gap for d in days) / n,
            "pm_drain_share": sum(d["pm"] <= -gap for d in days) / n,
            "events_per_day": sum(d["events"] for d in days) / n,
        }
    return out
