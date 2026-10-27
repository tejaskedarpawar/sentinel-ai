"""
CERT Insider Threat Dataset r4.2 Streaming Loader.

PRIVACY RULES (strictly enforced at load time):
Every content-like column (file content, email body, URL paths, page text) is
dropped immediately at ingestion. Only privacy-preserving metadata is extracted:
timestamps, user ID, PC identifier, activity type, counts, sizes, attachment counts,
recipient domain category, and website domain category.

Converts streamed CSV records into Sentinel AI's standard event dict schema
(event_type: login, usb, upload, process, network, privilege) with identical
payload structure so that profiling.py processes CERT data completely unchanged.
"""
import os
import csv
import random
from datetime import datetime, date
from urllib.parse import urlparse
import pandas as pd

RISKY_HTTP_DOMAINS = {
    "dropbox.com": "personal-dropbox",
    "drive.google.com": "personal-gdrive",
    "mega.nz": "unknown-cloud",
    "pastebin.com": "unknown-cloud",
    "wikileaks.org": "unknown-cloud",
    "monster.com": "external-jobsite",
    "indeed.com": "external-jobsite",
}

EXTERNAL_EMAIL_PROVIDERS = (
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "protonmail.com", "aol.com", "mail.com",
)


def parse_cert_dt(dt_str: str) -> datetime | None:
    """Parse CERT timestamp format (MM/DD/YYYY HH:MM:SS or YYYY-MM-DD HH:MM:SS)."""
    s = str(dt_str).strip()
    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def load_insider_answers(data_dir: str) -> dict[str, list[dict]]:
    """
    Read ground truth from answers/insiders.csv (or answers directory).
    Returns dict mapping user_id -> list of {scenario, start_dt, end_dt, start_date, end_date}.
    """
    answers_file = os.path.join(data_dir, "answers", "insiders.csv")
    if not os.path.exists(answers_file):
        # Look in data_dir root or subdirectories
        for root, _, files in os.walk(data_dir):
            for f in files:
                if f.lower() in ("insiders.csv", "insider.csv"):
                    answers_file = os.path.join(root, f)
                    break

    if not os.path.exists(answers_file):
        return {}

    insiders = {}
    with open(answers_file, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user = row.get("user") or row.get("User")
            if not user:
                continue
            user = user.strip()
            start_dt = parse_cert_dt(row.get("start") or row.get("Start") or "")
            end_dt = parse_cert_dt(row.get("end") or row.get("End") or "")
            scenario = int(row.get("scenario") or row.get("Scenario") or 1)

            if start_dt and end_dt:
                if user not in insiders:
                    insiders[user] = []
                insiders[user].append({
                    "scenario": scenario,
                    "details": row.get("details", ""),
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "start_date": start_dt.date(),
                    "end_date": end_dt.date(),
                })
    return insiders


def select_user_subset(
    data_dir: str,
    target_count: int = 100,
    seed: int = 42,
    insider_users: set[str] | None = None,
) -> set[str]:
    """
    Scan logon.csv to discover available users.
    Always includes all malicious insider users, plus a deterministic random sample
    of benign users up to target_count.
    """
    insider_users = insider_users or set()
    all_users = set()

    logon_file = os.path.join(data_dir, "logon.csv")
    if os.path.exists(logon_file):
        with open(logon_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                u = row.get("user")
                if u:
                    all_users.add(u.strip())
                    if len(all_users) >= target_count * 5:
                        break

    benign_users = sorted(list(all_users - insider_users))
    needed_benign = max(0, target_count - len(insider_users))

    rng = random.Random(seed)
    if len(benign_users) > needed_benign:
        selected_benign = set(rng.sample(benign_users, needed_benign))
    else:
        selected_benign = set(benign_users)

    selected = set(insider_users) | selected_benign
    return selected


def load_cert_dataset(
    data_dir: str,
    num_users: int = 100,
    seed: int = 42,
    chunk_size: int = 50000,
) -> tuple[list[dict], dict[str, list[dict]], set[str]]:
    """
    Streams CERT CSVs in chunks, drops all content columns at read time for privacy,
    and converts records into Sentinel AI standard events.

    Returns:
        (events, insider_windows, selected_users)
    """
    insider_map = load_insider_answers(data_dir)
    malicious_users = set(insider_map.keys())

    selected_users = select_user_subset(
        data_dir=data_dir,
        target_count=num_users,
        seed=seed,
        insider_users=malicious_users,
    )

    print(f"[CERT Loader] Selected {len(selected_users)} users ({len(malicious_users & selected_users)} malicious insiders, {len(selected_users - malicious_users)} benign).")

    events = []
    known_user_pcs: dict[str, set[str]] = {u: set() for u in selected_users}

    # 1. LOGON.CSV -> login events
    logon_path = os.path.join(data_dir, "logon.csv")
    if os.path.exists(logon_path):
        print("  -> Ingesting logon.csv (logons & off-hours detection)...")
        for chunk in pd.read_csv(logon_path, chunksize=chunk_size, usecols=["date", "user", "pc", "activity"]):
            filtered = chunk[chunk["user"].isin(selected_users) & (chunk["activity"] == "Logon")]
            for _, row in filtered.iterrows():
                ts = parse_cert_dt(row["date"])
                if not ts:
                    continue
                user = row["user"]
                pc = str(row["pc"])
                is_known = pc in known_user_pcs[user]
                known_user_pcs[user].add(pc)

                events.append({
                    "employee_id": user,
                    "event_type": "login",
                    "timestamp": ts,
                    "payload": {
                        "device_known": is_known,
                        "geo_city": "Nagpur" if is_known else "Lagos",
                    },
                    "source": "cert",
                })

    # 2. DEVICE.CSV -> usb events (Connect)
    device_path = os.path.join(data_dir, "device.csv")
    if os.path.exists(device_path):
        print("  -> Ingesting device.csv (USB connects)...")
        for chunk in pd.read_csv(device_path, chunksize=chunk_size, usecols=["date", "user", "pc", "activity"]):
            filtered = chunk[chunk["user"].isin(selected_users) & (chunk["activity"] == "Connect")]
            for _, row in filtered.iterrows():
                ts = parse_cert_dt(row["date"])
                if not ts:
                    continue
                events.append({
                    "employee_id": row["user"],
                    "event_type": "usb",
                    "timestamp": ts,
                    "payload": {"usb_events": 1},
                    "source": "cert",
                })

    # 3. FILE.CSV -> upload events (removable media copies, content dropped)
    file_path = os.path.join(data_dir, "file.csv")
    if os.path.exists(file_path):
        print("  -> Ingesting file.csv (removable media copies; dropping content)...")
        # Explicitly only use date, user, pc, filename (DROP content!)
        for chunk in pd.read_csv(file_path, chunksize=chunk_size, usecols=["date", "user", "pc", "filename"]):
            filtered = chunk[chunk["user"].isin(selected_users)]
            for _, row in filtered.iterrows():
                fn = str(row.get("filename", "")).lower()
                # Check if written to removable drive letter or USB path
                is_removable = (
                    fn.startswith(("e:\\", "f:\\", "d:\\", "/media", "/mnt"))
                    or "usb" in fn
                    or "removable" in fn
                )
                if is_removable:
                    ts = parse_cert_dt(row["date"])
                    if not ts:
                        continue
                    events.append({
                        "employee_id": row["user"],
                        "event_type": "upload",
                        "timestamp": ts,
                        "payload": {
                            "size_mb": 25.0, # Standard file chunk transfer weight
                            "destination": "usb-mass-storage",
                            "file_count": 1,
                            "risky": True,
                        },
                        "source": "cert",
                    })

    # 4. HTTP.CSV -> upload events (risky domains; dropping content & URL paths)
    http_path = os.path.join(data_dir, "http.csv")
    if os.path.exists(http_path):
        print("  -> Ingesting http.csv (domain classification; dropping URL path & content)...")
        for chunk in pd.read_csv(http_path, chunksize=chunk_size, usecols=["date", "user", "pc", "url"]):
            filtered = chunk[chunk["user"].isin(selected_users)]
            for _, row in filtered.iterrows():
                url = str(row.get("url", ""))
                try:
                    netloc = urlparse(url).netloc.lower()
                    if ":" in netloc:
                        netloc = netloc.split(":")[0]
                except Exception:
                    continue

                dest_cat = None
                for risky_domain, cat in RISKY_HTTP_DOMAINS.items():
                    if risky_domain in netloc:
                        dest_cat = cat
                        break

                if dest_cat:
                    ts = parse_cert_dt(row["date"])
                    if not ts:
                        continue
                    events.append({
                        "employee_id": row["user"],
                        "event_type": "upload",
                        "timestamp": ts,
                        "payload": {
                            "size_mb": 35.0,
                            "destination": dest_cat,
                            "file_count": 1,
                            "risky": True,
                        },
                        "source": "cert",
                    })

    # 5. EMAIL.CSV -> upload events (external attachments; dropping email body/content)
    email_path = os.path.join(data_dir, "email.csv")
    if os.path.exists(email_path):
        print("  -> Ingesting email.csv (external attachments; dropping email body)...")
        cols = ["date", "user", "pc", "to", "size", "attachments"]
        for chunk in pd.read_csv(email_path, chunksize=chunk_size, usecols=cols):
            filtered = chunk[chunk["user"].isin(selected_users)]
            for _, row in filtered.iterrows():
                att_count = int(row.get("attachments", 0) or 0)
                if att_count <= 0:
                    continue

                to_field = str(row.get("to", "")).lower()
                is_external = any(p in to_field for p in EXTERNAL_EMAIL_PROVIDERS)
                if is_external:
                    ts = parse_cert_dt(row["date"])
                    if not ts:
                        continue
                    size_bytes = float(row.get("size", 1024 * 1024) or (1024 * 1024))
                    size_mb = round(size_bytes / (1024.0 * 1024.0), 2)
                    events.append({
                        "employee_id": row["user"],
                        "event_type": "upload",
                        "timestamp": ts,
                        "payload": {
                            "size_mb": max(size_mb, 1.0),
                            "destination": "personal-email",
                            "file_count": att_count,
                            "risky": True,
                        },
                        "source": "cert",
                    })

    print(f"[CERT Loader] Successfully streamed and converted {len(events)} privacy-preserving events.")
    return events, insider_map, selected_users


def label_ground_truth(df: pd.DataFrame, insider_windows: dict[str, list[dict]]) -> pd.Series:
    """
    Labels each (employee_id, date) user-day:
    1 (positive) if inside a malicious user's activity window, else 0 (negative).
    """
    labels = []
    for _, row in df.iterrows():
        emp = str(row["employee_id"])
        row_date = row["date"]
        if isinstance(row_date, str):
            row_date = datetime.strptime(row_date, "%Y-%m-%d").date()

        is_positive = 0
        if emp in insider_windows:
            for w in insider_windows[emp]:
                if w["start_date"] <= row_date <= w["end_date"]:
                    is_positive = 1
                    break
        labels.append(is_positive)
    return pd.Series(labels, index=df.index, name="is_insider_threat")
