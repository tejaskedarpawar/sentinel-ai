#!/usr/bin/env python3
"""
Simulate analyst feedback for demo/testing purposes.
Labels alerts using the simulator's SEEDED_SCENARIOS ground truth:
  - Seeded employee alerts -> "threat"
  - Other flagged employee-days -> "false_positive"
"""
import sys
import os
from datetime import datetime

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal, init_db
from app.models import RiskRecord, AnalystFeedback
from app.collectors.simulator import SEEDED_SCENARIOS


def print_demo_banner():
    banner = """
##############################################################################
#                                                                            #
#                       *** DEMO ONLY NOTICE ***                             #
#                                                                            #
#  This script synthesizes analyst feedback labels by cross-referencing      #
#  simulated alerts with SEEDED_SCENARIOS ground-truth insider threats.      #
#                                                                            #
#  In production, labels are submitted by human SOC analysts triaging alerts #
#  via the dashboard interface. File contents are never accessed.            #
#                                                                            #
##############################################################################
"""
    print(banner)


def simulate_feedback(sample_ratio: float = 0.85):
    print_demo_banner()
    init_db()
    db = SessionLocal()

    try:
        flagged = (
            db.query(RiskRecord)
            .filter(RiskRecord.risk_tier.in_(["High", "Critical"]))
            .order_by(RiskRecord.risk_score.desc())
            .all()
        )

        if not flagged:
            print("No High/Critical risk records found in database. Run pipeline first.")
            return

        threats = [r for r in flagged if r.employee_id in SEEDED_SCENARIOS]
        fps = [r for r in flagged if r.employee_id not in SEEDED_SCENARIOS]

        print(f"Found {len(flagged)} total flagged alerts:")
        print(f"  - {len(threats)} from seeded threat employees ({', '.join(SEEDED_SCENARIOS.keys())})")
        print(f"  - {len(fps)} from non-seeded employees (baseline false positives)\n")

        # Pick a sample ensuring at least 10 threats and 10 false positives (>= 20 total)
        n_threat_sample = max(5, int(len(threats) * sample_ratio))
        n_fp_sample = max(5, int(len(fps) * sample_ratio))

        selected_threats = threats[:n_threat_sample]
        selected_fps = fps[:n_fp_sample]
        sample = selected_threats + selected_fps

        labeled_count = 0
        threat_count = 0
        fp_count = 0

        for r in sample:
            is_threat = r.employee_id in SEEDED_SCENARIOS
            label = "threat" if is_threat else "false_positive"
            scenario = SEEDED_SCENARIOS.get(r.employee_id, "baseline_noise")
            note = f"[DEMO] Ground truth: {scenario}"

            existing = (
                db.query(AnalystFeedback)
                .filter(
                    AnalystFeedback.employee_id == r.employee_id,
                    AnalystFeedback.date == r.date,
                )
                .first()
            )

            if existing:
                existing.label = label
                existing.analyst = "demo_ground_truth"
                existing.note = note
                existing.created_at = datetime.utcnow()
            else:
                fb = AnalystFeedback(
                    employee_id=r.employee_id,
                    date=r.date,
                    label=label,
                    analyst="demo_ground_truth",
                    note=note,
                    created_at=datetime.utcnow(),
                )
                db.add(fb)

            labeled_count += 1
            if is_threat:
                threat_count += 1
            else:
                fp_count += 1

            # Sync case status
            from app.routers.cases import sync_case_from_feedback
            sync_case_from_feedback(db, r.employee_id, r.date, label)

        db.commit()

        print(f"Successfully simulated {labeled_count} analyst feedback labels:")
        print(f"  - Confirmed threats: {threat_count}")
        print(f"  - False positives:   {fp_count}")
        print(f"Labels saved to analyst_feedback table. Ready for retraining!\n")

    finally:
        db.close()


if __name__ == "__main__":
    simulate_feedback()
