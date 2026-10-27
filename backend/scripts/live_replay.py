#!/usr/bin/env python3
"""
Sentinel AI — Day-by-day Live Alert & Event Replay Script.

IMPORTANT / NOTICE:
This script is a REPLAY of precomputed risk scores, NOT live scoring.
It takes the simulated organisation's already-computed employee-day risk records
and replays them day-by-day (default: 3 seconds per day). Each day's records are
inserted into PostgreSQL, and any High or Critical risk records are published
to the Redis pub/sub channel ('sentinel:alerts') in real time. This allows the
SOC Dashboard to visibly update live via its Server-Sent Events (SSE) stream
without requiring a full page refresh.

Privacy Preserving:
Only metadata and precomputed statistical risk scores are processed.
File contents are never accessed or stored.
"""
import sys
import os
import time
import argparse
from datetime import datetime

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal, init_db
from app.models import RiskRecord, Employee
from app.queue import publish_alert
from app.notifiers import notify_alert
from app.pipeline import run_pipeline


REPLAY_BANNER = """
================================================================================
                      SENTINEL AI — LIVE REPLAY ENGINE
================================================================================
  [NOTICE: REPLAY OF PRECOMPUTED SCORES — NOT LIVE SCORING]
  This demonstration script replays precomputed risk records day by day.
  Each simulated day's records are inserted into Postgres, and High/Critical
  alerts are published to Redis channel 'sentinel:alerts'.

  Watch the SOC Dashboard (http://localhost:5173) update in real-time via SSE!
================================================================================
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="Replay precomputed Sentinel AI risk records day by day."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Seconds delay between simulated days (default: 3.0s)",
    )
    parser.add_argument(
        "--min-tier",
        type=str,
        default="High",
        choices=["High", "Critical"],
        help="Minimum tier to publish to alerts channel (default: High)",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="Bypass 24h deduplication for outbound Slack/Telegram/SMTP notifications",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously loop through days repeatedly",
    )
    return parser.parse_args()


def load_and_snapshot_records(db):
    """Load existing records or run pipeline once to generate them."""
    records = db.query(RiskRecord).order_by(RiskRecord.date).all()
    if not records:
        print("[*] No precomputed risk records found in Postgres. Running pipeline once...")
        run_pipeline()
        records = db.query(RiskRecord).order_by(RiskRecord.date).all()

    # Snapshot records into plain dicts
    snapshots = []
    for r in records:
        snapshots.append({
            "employee_id": r.employee_id,
            "date": str(r.date),
            "isolation_forest_score": r.isolation_forest_score,
            "autoencoder_score": r.autoencoder_score,
            "lstm_score": r.lstm_score,
            "xgboost_score": r.xgboost_score,
            "risk_score": r.risk_score,
            "risk_tier": r.risk_tier,
            "rule_flags": r.rule_flags or [],
            "explanation": r.explanation or "",
            "agent_source": r.agent_source or "template",
            "features": r.features or {},
            "is_ground_truth_anomaly": r.is_ground_truth_anomaly,
            "scenario": r.scenario,
        })
    return snapshots


def run_replay():
    args = parse_args()
    print(REPLAY_BANNER)
    init_db()

    db = SessionLocal()
    try:
        snapshots = load_and_snapshot_records(db)
        if not snapshots:
            print("[!] Failed to obtain precomputed risk records. Exiting.")
            return

        # Group by date
        dates_order = sorted(list({s["date"] for s in snapshots}))
        grouped = {d: [] for d in dates_order}
        for s in snapshots:
            grouped[s["date"]].append(s)

        print(f"Loaded {len(snapshots)} precomputed records across {len(dates_order)} days.")
        print(f"Replay configuration: {args.interval}s per day | Min tier: {args.min_tier}")
        print("Starting day-by-day replay. Press Ctrl+C at any time to stop.\n")

        iteration = 1
        while True:
            if iteration > 1:
                print(f"\n--- [Loop iteration {iteration}] Restarting replay sequence ---")

            # Wipe RiskRecord table for replay progression
            db.query(RiskRecord).delete()
            db.commit()

            for day_idx, current_date in enumerate(dates_order, 1):
                day_records = grouped[current_date]
                alerts_published = 0

                # Insert day records into Postgres
                for rec in day_records:
                    db.add(RiskRecord(
                        employee_id=rec["employee_id"],
                        date=rec["date"],
                        isolation_forest_score=rec["isolation_forest_score"],
                        autoencoder_score=rec["autoencoder_score"],
                        lstm_score=rec["lstm_score"],
                        xgboost_score=rec["xgboost_score"],
                        risk_score=rec["risk_score"],
                        risk_tier=rec["risk_tier"],
                        rule_flags=rec["rule_flags"],
                        explanation=rec["explanation"],
                        agent_source=rec["agent_source"],
                        features=rec["features"],
                        is_ground_truth_anomaly=rec["is_ground_truth_anomaly"],
                        scenario=rec["scenario"],
                    ))

                    # Publish High/Critical records
                    tier = rec["risk_tier"]
                    if (args.min_tier == "High" and tier in ("High", "Critical")) or (args.min_tier == "Critical" and tier == "Critical"):
                        alert_payload = {
                            "id": f"{rec['employee_id']}-{rec['date']}",
                            "employee_id": rec["employee_id"],
                            "date": rec["date"],
                            "risk_score": rec["risk_score"],
                            "risk_tier": tier,
                            "rule_flags": rec["rule_flags"],
                            "explanation": rec["explanation"],
                            "agent_source": rec["agent_source"],
                            "model_breakdown": {
                                "isolation_forest": rec["isolation_forest_score"],
                                "autoencoder": rec["autoencoder_score"],
                                "lstm": rec["lstm_score"],
                                "xgboost": rec["xgboost_score"],
                            },
                        }
                        publish_alert(alert_payload)
                        notify_alert(alert_payload, force=args.force_notify)
                        alerts_published += 1

                db.commit()

                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"Day {day_idx:02d}/{len(dates_order):02d} ({current_date}): "
                    f"Inserted {len(day_records):2d} records | "
                    f"Streamed {alerts_published} alerts"
                )

                if day_idx < len(dates_order) or args.loop:
                    time.sleep(args.interval)

            if not args.loop:
                print(f"\n[✓] Replay finished: all {len(dates_order)} simulated days streamed to dashboard.")
                break
            iteration += 1

    except KeyboardInterrupt:
        print("\n\n[!] Replay interrupted by analyst.")
    finally:
        db.close()


if __name__ == "__main__":
    run_replay()
