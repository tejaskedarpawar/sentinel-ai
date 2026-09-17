"""
Sentinel AI — full pipeline orchestration.

    Metadata Collector -> Redis queue -> Event Processing ->
    Behaviour Profiling -> AI Detection Engine -> Dynamic Risk Engine ->
    AI Investigation Agent -> Threat Graph -> Postgres -> SOC Dashboard

Run directly to (re)seed the demo dataset:
    python -m app.pipeline
"""
import sys

from app.database import SessionLocal, init_db
from app.models import Employee, RiskRecord, RawMetadataEvent
from app.collectors.simulator import generate_dataset, SEEDED_SCENARIOS
from app.queue import push_events, drain_events, queue_depth
from app.profiling import build_feature_matrix
from app.detection.engine import DetectionEngine
from app.risk_engine import compute_risk
from app.agent import explain
from app.graph import build_graph, persist_graph


def run_pipeline(include_live: bool = False):
    print("[1/7] Metadata Collector: generating simulated activity...")
    employees, events = generate_dataset()
    push_events(events)

    if include_live:
        print("      + draining any live-collector events already queued...")

    print(f"[2/7] Event Processing: draining {queue_depth()} events from the Redis queue...")
    drained = drain_events(batch_size=100000)

    print("[3/7] Behaviour Profiling: building per-employee-day feature vectors...")
    df = build_feature_matrix(drained)
    if df.empty:
        print("No events to process — aborting.")
        return

    print("[4/7] AI Detection Engine: fitting ensemble (Isolation Forest + Autoencoder + LSTM + XGBoost)...")
    engine = DetectionEngine()
    scored = engine.fit_score(df)

    print("[5/7] Dynamic Risk Engine: computing adaptive risk scores...")
    risked = compute_risk(scored)

    print("[6/7] AI Investigation Agent: generating explanations for flagged days...")
    flagged_mask = risked["risk_tier"].isin(["High", "Critical"])
    explanations, sources = {}, {}
    for idx, row in risked[flagged_mask].iterrows():
        text, source = explain(row.to_dict())
        explanations[idx] = text
        sources[idx] = source

    print("[7/7] Persisting to Postgres + building Threat Graph...")
    db = SessionLocal()
    try:
        db.query(RiskRecord).delete()
        db.query(RawMetadataEvent).delete()
        db.query(Employee).delete()
        db.commit()

        for emp in employees:
            db.merge(Employee(id=emp["id"], name=emp["name"], department=emp["department"]))
        db.commit()

        feature_cols = [c for c in df.columns if c not in ("employee_id", "date")]
        for idx, row in risked.iterrows():
            db.add(RiskRecord(
                employee_id=row["employee_id"],
                date=row["date"],
                isolation_forest_score=float(row["isolation_forest_score"]),
                autoencoder_score=float(row["autoencoder_score"]),
                lstm_score=float(row["lstm_score"]),
                xgboost_score=float(row["xgboost_score"]),
                risk_score=float(row["risk_score"]),
                risk_tier=row["risk_tier"],
                rule_flags=row["rule_flags"],
                explanation=explanations.get(idx),
                agent_source=sources.get(idx, "template"),
                features={c: (float(row[c]) if isinstance(row[c], (int, float)) else row[c]) for c in feature_cols},
                is_ground_truth_anomaly=int(row["employee_id"] in SEEDED_SCENARIOS),
                scenario=SEEDED_SCENARIOS.get(row["employee_id"]),
            ))
        db.commit()

        risk_map = {(r.employee_id, r.date): r.risk_tier for r in risked.itertuples()}
        g = build_graph(drained, risk_map)
        n_edges = persist_graph(db, g)

    finally:
        db.close()

    print(f"      {len(risked)} employee-day records persisted, "
          f"{int(flagged_mask.sum())} High/Critical days flagged, {n_edges} graph edges built.")

    print("\nGround-truth scenario recall check:")
    for emp_id, scenario in SEEDED_SCENARIOS.items():
        peak = risked[risked.employee_id == emp_id]["risk_score"].max()
        print(f"  {emp_id} ({scenario}): peak risk score = {peak:.1f}")


if __name__ == "__main__":
    init_db()
    run_pipeline()
