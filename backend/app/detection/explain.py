import os
from datetime import datetime, timedelta, date as date_type
import joblib
import numpy as np
from sqlalchemy.orm import Session
import xgboost as xgb

from app.detection.engine import MODEL_FEATURE_COLUMNS
from app.models import RiskRecord

ARTIFACTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")
)
EXPLAINER_FILE = "xgb_explainer.joblib"
SUPERVISED_FILE = "xgb_supervised.joblib"

HUMAN_FEATURE_LABELS = {
    "upload_mb_total": "Total Upload Volume (MB)",
    "upload_count": "Daily Upload Count",
    "risky_destination_count": "Transfers to Risky Destinations",
    "usb_events": "USB / Removable Media Events",
    "new_process_count": "New Process Execution Count",
    "process_count": "Total Process Count",
    "network_mb": "Total Network Traffic (MB)",
    "session_minutes": "User Session Duration (Minutes)",
    "unusual_geo": "Unusual Geographic Location Flag",
    "off_hours_event": "Off-Hours Activity Flag",
    "privilege_escalation": "Privilege Escalation Flag",
    "risky_extension_count": "Risky File Extension Count",
    "upload_mb_total_deviation": "Upload Volume Baseline Deviation",
    "network_mb_deviation": "Network Traffic Baseline Deviation",
    "usb_events_deviation": "USB Activity Baseline Deviation",
}

BASELINE_KEY_FEATURES = [
    "upload_mb_total",
    "upload_count",
    "risky_destination_count",
    "usb_events",
    "network_mb",
    "new_process_count",
    "session_minutes",
]

# In-memory cache for explainability results
_EXPLAIN_CACHE: dict[tuple[str, str, str], dict] = {}
_LAST_ARTIFACT_MTIME: float = 0.0


def get_explainer_artifact() -> dict | None:
    """Load model artifact for TreeSHAP explainability."""
    global _LAST_ARTIFACT_MTIME, _EXPLAIN_CACHE
    path = os.path.join(ARTIFACTS_DIR, EXPLAINER_FILE)
    if not os.path.exists(path):
        path = os.path.join(ARTIFACTS_DIR, SUPERVISED_FILE)

    if not os.path.exists(path):
        return None

    try:
        current_mtime = os.path.getmtime(path)
        if current_mtime != _LAST_ARTIFACT_MTIME:
            # Artifact changed (e.g. retrained or re-run), invalidate cache
            _EXPLAIN_CACHE.clear()
            _LAST_ARTIFACT_MTIME = current_mtime

        data = joblib.load(path)
        if isinstance(data, dict) and "model" in data:
            return data
    except Exception as e:
        print(f"[explain] Error loading explainer artifact from {path}: {e}")
    return None


def generate_plain_language_summary(
    shap_items: list[dict], baseline_items: list[dict], alert_features: dict
) -> str:
    """
    Synthesize 2-3 plain-language sentences from top SHAP features and baseline deviations.
    """
    sentences = []

    # 1. Check volume / upload deviation
    upload_mb = alert_features.get("upload_mb_total", 0.0)
    upload_base = next((b for b in baseline_items if b["feature"] == "upload_mb_total"), None)

    if upload_base and upload_base["today_value"] > 0:
        mean_val = upload_base["mean"]
        if mean_val > 0.5:
            ratio = upload_base["today_value"] / mean_val
            if ratio >= 1.5:
                sentences.append(
                    f"Data uploads reached {upload_base['today_value']:.1f} MB, which is {ratio:.1f}x higher than this employee's 7-day average ({mean_val:.1f} MB)."
                )
            else:
                sentences.append(
                    f"Daily data transfer volume was {upload_base['today_value']:.1f} MB (trailing 7-day mean: {mean_val:.1f} MB)."
                )
        else:
            sentences.append(
                f"Data uploads surged to {upload_base['today_value']:.1f} MB against a near-zero upload baseline over the trailing 7 days."
            )

    # 2. Check risky destinations, USB, off-hours, or geo
    risky_dest = alert_features.get("risky_destination_count", 0.0)
    usb_ev = alert_features.get("usb_events", 0.0)
    off_hours = alert_features.get("off_hours_event", 0.0)
    unusual_geo = alert_features.get("unusual_geo", 0.0)

    context_details = []
    if risky_dest > 0:
        context_details.append(f"transfers to personal or unapproved cloud destinations ({int(risky_dest)}x)")
    if usb_ev > 0:
        context_details.append(f"elevated removable media activity ({int(usb_ev)} USB events)")
    if off_hours:
        context_details.append("activity occurring outside normal working hours")
    if unusual_geo:
        context_details.append("authentication from an unrecognised geographic location")

    if context_details:
        joined = "; ".join(context_details)
        sentences.append(f"Notable risk factors observed include: {joined}.")

    # 3. Model driver explanation based on top SHAP
    risk_raising_shap = [s for s in shap_items if s["direction"] == "raises_risk"]
    if risk_raising_shap:
        top_feature = risk_raising_shap[0]
        sentences.append(
            f"The primary driver elevating AI risk was {top_feature['human_label'].lower()} (SHAP contribution: +{top_feature['contribution']:.3f})."
        )
    elif shap_items:
        sentences.append(
            f"Overall behavioural anomaly was driven primarily by {shap_items[0]['human_label'].lower()}."
        )

    if not sentences:
        sentences.append("Behavioural telemetry showed abnormal multi-vector deviations across standard workstation activity.")

    return " ".join(sentences[:3])


def explain_alert(db: Session, employee_id: str, target_date: date_type) -> dict:
    """
    Computes per-alert explainability:
      a) TreeSHAP top 8 features by |contribution|
      b) Trailing 7-day baseline comparison for key features sorted by |z|
      c) 2-3 plain-language sentences summary
    """
    artifact = get_explainer_artifact()
    artifact_mtime_str = str(_LAST_ARTIFACT_MTIME)
    cache_key = (employee_id, target_date.isoformat(), artifact_mtime_str)

    if cache_key in _EXPLAIN_CACHE:
        return _EXPLAIN_CACHE[cache_key]

    # Retrieve target risk record
    record = (
        db.query(RiskRecord)
        .filter(RiskRecord.employee_id == employee_id, RiskRecord.date == target_date)
        .first()
    )
    if not record:
        return {
            "error": "Risk record not found for specified employee and date",
            "shap": [],
            "baseline": [],
            "summary": "No telemetry data recorded for this day.",
        }

    alert_features = dict(record.features or {})

    # a) TreeSHAP computation
    shap_results = []
    if artifact and "model" in artifact:
        try:
            model = artifact["model"]
            booster = model.get_booster() if hasattr(model, "get_booster") else model
            feature_cols = artifact.get("feature_columns", MODEL_FEATURE_COLUMNS)

            feat_vector = np.array(
                [[float(alert_features.get(c, 0.0) or 0.0) for c in feature_cols]],
                dtype=float,
            )
            dmatrix = xgb.DMatrix(feat_vector, feature_names=feature_cols)
            # TreeSHAP via XGBoost booster
            contribs = booster.predict(dmatrix, pred_contribs=True)
            # contribs has shape (1, n_features + 1), where last column is bias
            feat_contribs = contribs[0, :-1]

            all_shap = []
            for col, val, c_val in zip(feature_cols, feat_vector[0], feat_contribs):
                all_shap.append({
                    "feature": col,
                    "human_label": HUMAN_FEATURE_LABELS.get(col, col.replace("_", " ").title()),
                    "value": round(float(val), 2),
                    "contribution": round(float(c_val), 4),
                    "direction": "raises_risk" if c_val > 0 else "lowers_risk",
                })

            # Sort by |contribution| descending and select top 8
            all_shap.sort(key=lambda x: abs(x["contribution"]), reverse=True)
            shap_results = all_shap[:8]
        except Exception as e:
            print(f"[explain] TreeSHAP prediction failed: {e}")

    # b) Baseline comparison (trailing 7 days)
    start_date = target_date - timedelta(days=7)
    trailing_records = (
        db.query(RiskRecord)
        .filter(
            RiskRecord.employee_id == employee_id,
            RiskRecord.date < target_date,
            RiskRecord.date >= start_date,
        )
        .all()
    )

    baseline_results = []
    for feat in BASELINE_KEY_FEATURES:
        today_val = float(alert_features.get(feat, 0.0) or 0.0)
        hist_vals = [float((r.features or {}).get(feat, 0.0) or 0.0) for r in trailing_records]

        if hist_vals:
            mean_val = float(np.mean(hist_vals))
            std_val = float(np.std(hist_vals))
        else:
            mean_val = 0.0
            std_val = 0.0

        # Safe z-score
        std_eff = std_val if std_val > 1e-4 else (0.2 * mean_val if mean_val > 0 else 1.0)
        z_score = (today_val - mean_val) / std_eff

        baseline_results.append({
            "feature": feat,
            "human_label": HUMAN_FEATURE_LABELS.get(feat, feat.replace("_", " ").title()),
            "today_value": round(today_val, 2),
            "mean": round(mean_val, 2),
            "std": round(std_val, 2),
            "z_score": round(float(z_score), 2),
        })

    # Sort baseline by |z_score| descending and select top 5
    baseline_results.sort(key=lambda x: abs(x["z_score"]), reverse=True)
    top_baseline = baseline_results[:5]

    # c) Plain-language summary
    summary_text = generate_plain_language_summary(shap_results, top_baseline, alert_features)

    result = {
        "employee_id": employee_id,
        "date": target_date.isoformat(),
        "shap": shap_results,
        "baseline": top_baseline,
        "summary": summary_text,
        "model_available": bool(artifact is not None),
    }

    _EXPLAIN_CACHE[cache_key] = result
    return result
