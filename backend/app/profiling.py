"""
Event Processing + User Behaviour Profiling Engine.

Consumes raw metadata events (drained from the Redis queue, regardless
of whether they came from the simulator or the live collector) and
turns them into one feature row per employee per day, plus a rolling
7-day behavioural baseline used to express each day as a deviation
from that employee's own normal pattern.
"""
from collections import defaultdict
from datetime import datetime
import pandas as pd
import numpy as np

FEATURE_COLUMNS = [
    "upload_mb_total", "upload_count", "risky_destination_count",
    "usb_events", "new_process_count", "process_count",
    "network_mb", "session_minutes", "unusual_geo", "off_hours_event",
    "privilege_escalation", "risky_extension_count",
]


def _is_off_hours(ts: datetime) -> bool:
    return ts.hour < 7 or ts.hour >= 20


def events_to_daily_rows(events: list[dict]) -> pd.DataFrame:
    """Raw events -> one row per (employee_id, date) with summed/derived
    counters. This is the 'Event Processing' stage."""
    buckets = defaultdict(lambda: defaultdict(float))

    for e in events:
        emp = e["employee_id"]
        ts = e["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        day = ts.date()
        key = (emp, day)
        payload = e.get("payload", {})
        etype = e["event_type"]

        if etype == "upload":
            buckets[key]["upload_mb_total"] += float(payload.get("size_mb", 0))
            buckets[key]["upload_count"] += 1
            if payload.get("destination") in ("personal-gdrive", "personal-dropbox", "unknown-cloud",
                                                "personal-email", "usb-mass-storage", "personal-cloud-sync"):
                buckets[key]["risky_destination_count"] += 1
            if payload.get("risky_extension"):
                buckets[key]["risky_extension_count"] += 1
        elif etype == "usb":
            buckets[key]["usb_events"] += float(payload.get("usb_events", 0))
        elif etype == "process":
            buckets[key]["new_process_count"] += float(payload.get("new_process_count", 0))
            buckets[key]["process_count"] = max(buckets[key]["process_count"], float(payload.get("process_count", 0)))
        elif etype == "network":
            buckets[key]["network_mb"] += float(payload.get("network_mb", 0))
            buckets[key]["session_minutes"] += float(payload.get("session_minutes", 0))
        elif etype == "login":
            if payload.get("geo_city") and payload.get("geo_city") not in ("Nagpur", "Mumbai", "Pune"):
                buckets[key]["unusual_geo"] = 1
            if _is_off_hours(ts):
                buckets[key]["off_hours_event"] = 1
        elif etype == "privilege":
            buckets[key]["privilege_escalation"] = 1

        if etype == "upload" and _is_off_hours(ts):
            buckets[key]["off_hours_event"] = 1

    rows = []
    for (emp, day), feats in buckets.items():
        row = {"employee_id": emp, "date": day}
        for col in FEATURE_COLUMNS:
            row[col] = feats.get(col, 0.0)
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["employee_id", "date"] + FEATURE_COLUMNS)
    return df.sort_values(["employee_id", "date"]).reset_index(drop=True)


def add_behavioural_baseline(df: pd.DataFrame, window_days: int = 7) -> pd.DataFrame:
    """Behaviour Profiling stage: for each employee, compute a rolling
    baseline (mean of the trailing `window_days`, excluding today) for
    the key volume features, then express today's value as a
    deviation ratio from that baseline. This is what lets the
    detection engine catch a *change* in behaviour rather than just an
    absolute large number."""
    df = df.copy()
    key_cols = ["upload_mb_total", "network_mb", "usb_events"]
    for col in key_cols:
        baseline_col = f"{col}_baseline"
        deviation_col = f"{col}_deviation"
        df[baseline_col] = (
            df.groupby("employee_id")[col]
            .transform(lambda s: s.shift(1).rolling(window_days, min_periods=1).mean())
            .fillna(0.0)
        )
        df[deviation_col] = np.where(
            df[baseline_col] > 0.01,
            (df[col] - df[baseline_col]) / df[baseline_col],
            np.where(df[col] > 0, 1.0, 0.0),
        )
    return df


def build_feature_matrix(events: list[dict], window_days: int = 7) -> pd.DataFrame:
    daily = events_to_daily_rows(events)
    return add_behavioural_baseline(daily, window_days=window_days)
