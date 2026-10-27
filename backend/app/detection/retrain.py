import os
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sqlalchemy import and_
from sqlalchemy.orm import Session
import xgboost as xgb

from app.detection.engine import MODEL_FEATURE_COLUMNS
from app.models import RiskRecord, AnalystFeedback
from app.risk_engine import compute_risk
from app.agent import explain

ARTIFACTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "artifacts")
)
ARTIFACT_FILE = "xgb_supervised.joblib"


def get_artifact_path() -> str:
    return os.path.join(ARTIFACTS_DIR, ARTIFACT_FILE)


def load_supervised_model() -> dict | None:
    path = get_artifact_path()
    if os.path.exists(path):
        try:
            data = joblib.load(path)
            if isinstance(data, dict) and "model" in data:
                return data
        except Exception as e:
            print(f"[retrain] Warning: Failed to load artifact from {path}: {e}")
    return None


def get_model_status(db: Session) -> dict:
    """Return current model mode and training metadata."""
    artifact = load_supervised_model()
    labeled_count = db.query(AnalystFeedback).count()

    if artifact:
        return {
            "mode": "supervised",
            "n_labels": artifact.get("n_labels", labeled_count),
            "trained_at": artifact.get("trained_at"),
            "cv_metrics": artifact.get("cv_metrics"),
        }
    return {
        "mode": "pseudo",
        "n_labels": labeled_count,
        "trained_at": None,
        "cv_metrics": None,
    }


def retrain_model(db: Session) -> dict:
    """
    Retrain XGBoost using analyst feedback joined with risk_records.features.
    Requires at least 20 labels with at least 5 of each class.
    Labeled rows get sample_weight 1.0; unlabeled rows keep pseudo-labels at sample_weight 0.2.
    Computes 5-fold CV precision, recall, and ROC-AUC on labeled rows.
    Saves model + metadata to backend/artifacts/ with joblib.
    """
    rows = (
        db.query(RiskRecord, AnalystFeedback)
        .outerjoin(
            AnalystFeedback,
            and_(
                RiskRecord.employee_id == AnalystFeedback.employee_id,
                RiskRecord.date == AnalystFeedback.date,
            ),
        )
        .all()
    )

    if not rows:
        return {"success": False, "reason": "No risk records found in database."}

    labeled_data = []
    unlabeled_data = []

    for r, fb in rows:
        feat = r.features or {}
        feat_vec = [float(feat.get(c, 0.0) or 0.0) for c in MODEL_FEATURE_COLUMNS]

        if fb is not None and fb.label in ("threat", "false_positive"):
            y_val = 1 if fb.label == "threat" else 0
            labeled_data.append((feat_vec, y_val, r))
        else:
            iso_score = float(r.isolation_forest_score or 0.0)
            unlabeled_data.append((feat_vec, iso_score, r))

    n_labeled = len(labeled_data)
    threat_count = sum(1 for _, y, _ in labeled_data if y == 1)
    fp_count = sum(1 for _, y, _ in labeled_data if y == 0)

    if n_labeled < 20:
        return {
            "success": False,
            "reason": f"Need at least 20 labels to retrain (currently have {n_labeled}).",
            "n_labels": n_labeled,
            "counts": {"threat": threat_count, "false_positive": fp_count},
        }

    if threat_count < 5 or fp_count < 5:
        return {
            "success": False,
            "reason": (
                f"Need at least 5 of each class to retrain (currently have {threat_count} "
                f"threats and {fp_count} false positives)."
            ),
            "n_labels": n_labeled,
            "counts": {"threat": threat_count, "false_positive": fp_count},
        }

    X_labeled = np.array([item[0] for item in labeled_data], dtype=float)
    y_labeled = np.array([item[1] for item in labeled_data], dtype=int)

    # Process unlabeled data pseudo-labels
    if unlabeled_data:
        X_unlabeled = np.array([item[0] for item in unlabeled_data], dtype=float)
        unlabeled_iso = np.array([item[1] for item in unlabeled_data], dtype=float)
        cutoff = np.quantile(unlabeled_iso, 0.92) if len(unlabeled_iso) > 0 else 0.5
        y_unlabeled = (unlabeled_iso >= cutoff).astype(int)
        weights_unlabeled = np.full(len(unlabeled_data), 0.2, dtype=float)
    else:
        X_unlabeled = np.empty((0, len(MODEL_FEATURE_COLUMNS)), dtype=float)
        y_unlabeled = np.empty((0,), dtype=int)
        weights_unlabeled = np.empty((0,), dtype=float)

    # Stratified 5-Fold Cross-Validation on labeled rows only
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    precisions, recalls, roc_aucs = [], [], []

    for train_idx, val_idx in skf.split(X_labeled, y_labeled):
        X_tr = X_labeled[train_idx]
        y_tr = y_labeled[train_idx]
        w_tr = np.full(len(y_tr), 1.0, dtype=float)

        if len(X_unlabeled) > 0:
            X_fold_train = np.vstack([X_tr, X_unlabeled])
            y_fold_train = np.concatenate([y_tr, y_unlabeled])
            w_fold_train = np.concatenate([w_tr, weights_unlabeled])
        else:
            X_fold_train = X_tr
            y_fold_train = y_tr
            w_fold_train = w_tr

        fold_clf = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.1,
            eval_metric="logloss",
            random_state=42,
        )
        fold_clf.fit(X_fold_train, y_fold_train, sample_weight=w_fold_train)

        X_val = X_labeled[val_idx]
        y_val = y_labeled[val_idx]
        y_pred_proba = fold_clf.predict_proba(X_val)[:, 1]
        y_pred_class = (y_pred_proba >= 0.5).astype(int)

        precisions.append(precision_score(y_val, y_pred_class, zero_division=0))
        recalls.append(recall_score(y_val, y_pred_class, zero_division=0))
        if len(np.unique(y_val)) > 1:
            roc_aucs.append(roc_auc_score(y_val, y_pred_proba))
        else:
            roc_aucs.append(1.0)

    cv_metrics = {
        "precision": round(float(np.mean(precisions)), 4),
        "recall": round(float(np.mean(recalls)), 4),
        "roc_auc": round(float(np.mean(roc_aucs)), 4),
    }

    # Train final model on all data (labeled @ 1.0, unlabeled @ 0.2)
    weights_labeled = np.full(len(y_labeled), 1.0, dtype=float)
    if len(X_unlabeled) > 0:
        X_full = np.vstack([X_labeled, X_unlabeled])
        y_full = np.concatenate([y_labeled, y_unlabeled])
        w_full = np.concatenate([weights_labeled, weights_unlabeled])
    else:
        X_full = X_labeled
        y_full = y_labeled
        w_full = weights_labeled

    final_model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    final_model.fit(X_full, y_full, sample_weight=w_full)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    trained_at = datetime.utcnow().isoformat()
    artifact_payload = {
        "model": final_model,
        "trained_at": trained_at,
        "n_labels": n_labeled,
        "counts": {"threat": threat_count, "false_positive": fp_count},
        "cv_metrics": cv_metrics,
        "mode": "supervised",
        "feature_columns": MODEL_FEATURE_COLUMNS,
    }
    bg_indices = np.random.choice(len(X_full), size=min(50, len(X_full)), replace=False)
    artifact_payload["background_sample"] = X_full[bg_indices]
    joblib.dump(artifact_payload, get_artifact_path())
    joblib.dump(artifact_payload, os.path.join(ARTIFACTS_DIR, "xgb_explainer.joblib"))
    print(f"[retrain] Supervised XGBoost saved to {get_artifact_path()} (N={n_labeled}, CV AUC={cv_metrics['roc_auc']})")

    return {
        "success": True,
        "model": final_model,
        "metadata": {
            "mode": "supervised",
            "n_labels": n_labeled,
            "trained_at": trained_at,
            "cv_metrics": cv_metrics,
            "counts": {"threat": threat_count, "false_positive": fp_count},
        },
    }


def rescore_records(db: Session, model: xgb.XGBClassifier) -> dict:
    """
    Re-scores risk_records in place without wiping them, updating
    xgboost_score, risk_score, risk_tier, and rule_flags via risk_engine.
    """
    records = db.query(RiskRecord).order_by(RiskRecord.id).all()
    if not records:
        return {"updated": 0, "high_critical_before": 0, "high_critical_after": 0}

    high_crit_before = sum(1 for r in records if r.risk_tier in ("High", "Critical"))
    fp_before = sum(1 for r in records if r.risk_tier in ("High", "Critical") and not r.is_ground_truth_anomaly)

    # Build DataFrame from records
    feature_rows = []
    for r in records:
        row_dict = dict(r.features or {})
        row_dict["employee_id"] = r.employee_id
        row_dict["date"] = r.date
        row_dict["isolation_forest_score"] = float(r.isolation_forest_score or 0.0)
        row_dict["autoencoder_score"] = float(r.autoencoder_score or 0.0)
        row_dict["lstm_score"] = float(r.lstm_score or 0.0)
        feature_rows.append(row_dict)

    df = pd.DataFrame(feature_rows)
    X = df[MODEL_FEATURE_COLUMNS].fillna(0.0).values.astype(float)
    new_xgb = model.predict_proba(X)[:, 1]
    df["xgboost_score"] = new_xgb

    risked = compute_risk(df)

    for record, (_, row) in zip(records, risked.iterrows()):
        record.xgboost_score = float(row["xgboost_score"])
        record.risk_score = float(row["risk_score"])
        record.risk_tier = str(row["risk_tier"])
        record.rule_flags = list(row["rule_flags"])
        if record.risk_tier in ("High", "Critical") and not record.explanation:
            expl, src = explain(row.to_dict())
            record.explanation = expl
            record.agent_source = src

    db.commit()

    high_crit_after = sum(1 for r in records if r.risk_tier in ("High", "Critical"))
    fp_after = sum(1 for r in records if r.risk_tier in ("High", "Critical") and not r.is_ground_truth_anomaly)

    return {
        "updated": len(records),
        "high_critical_before": high_crit_before,
        "high_critical_after": high_crit_after,
        "false_positives_before": fp_before,
        "false_positives_after": fp_after,
    }
