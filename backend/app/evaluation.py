"""
Evaluation Engine for Sentinel AI on the CERT Insider Threat Benchmark (r4.2).

Evaluation Rules:
1. Strict temporal split (train on earlier window, evaluate on later window).
   Zero data leakage: supervised XGBoost only trains on train-period data.
2. Metrics computed on test period:
   - ROC-AUC
   - PR-AUC (Average Precision)
   - Precision, Recall, F1 at production High-tier threshold
   - Precision@k (k=5, 10, 20)
   - Alerts per analyst-day
   - Mean days-to-detection per malicious user
3. Model comparison:
   - Isolation Forest
   - Autoencoder
   - LSTM Autoencoder
   - XGBoost
   - Full Sentinel AI Ensemble
   - Naive static-threshold baseline (flag upload_mb_total or usb_events > 95th percentile)
4. Stores result in PostgreSQL evaluation_runs table.
"""
import os
import sys
import argparse
import logging
from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_recall_curve,
    roc_curve,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.ensemble import IsolationForest
import xgboost as xgb
import torch

from app.database import SessionLocal, init_db
from app.models import EvaluationRun
from app.collectors.cert_loader import load_cert_dataset, label_ground_truth
from app.profiling import build_feature_matrix
from app.detection.autoencoder import AutoencoderDetector
from app.detection.lstm import LSTMSequenceDetector
from app.detection.engine import MODEL_FEATURE_COLUMNS, _robust_normalize
from app.risk_engine import compute_risk

logger = logging.getLogger(__name__)


def evaluate_cert_pipeline(
    data_path: str,
    num_users: int = 100,
    train_ratio: float = 0.6,
    epochs: int = 8,
    seed: int = 42,
) -> dict:
    print("=" * 80)
    print("SENTINEL AI — CERT INSIDER THREAT BENCHMARK EVALUATION")
    print("=" * 80)
    print(f"Dataset path: {data_path} | Users subset: {num_users} | Train ratio: {train_ratio} | Epochs: {epochs}")

    # 1. Load dataset with strict privacy filters
    events, insider_windows, selected_users = load_cert_dataset(
        data_dir=data_path,
        num_users=num_users,
        seed=seed,
    )
    if not events:
        raise ValueError(f"No events loaded from {data_path}")

    # 2. Extract feature matrix
    print("\n[Step 1/5] Building behavioural feature vectors and rolling baselines...")
    df = build_feature_matrix(events)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    dates = sorted(list(df["date"].unique()))
    print(f"Built {len(df)} user-day records across {len(dates)} unique dates.")

    # 3. Ground truth labeling
    y_all = label_ground_truth(df, insider_windows)
    positives_count = int(y_all.sum())
    print(f"Ground-truth malicious user-days: {positives_count} / {len(df)} ({positives_count / len(df) * 100:.1f}%)")

    # 4. Strict Temporal Split (No Leakage)
    print("\n[Step 2/5] Performing strict temporal split (Train on earlier dates, Test on later dates)...")
    split_idx = int(len(dates) * train_ratio)
    train_dates = set(dates[:split_idx])
    test_dates = set(dates[split_idx:])

    train_mask = df["date"].isin(train_dates)
    test_mask = df["date"].isin(test_dates)

    df_train = df[train_mask].copy().reset_index(drop=True)
    df_test = df[test_mask].copy().reset_index(drop=True)
    y_train = y_all[train_mask].reset_index(drop=True)
    y_test = y_all[test_mask].reset_index(drop=True)

    test_pos = int(y_test.sum())
    test_neg = len(y_test) - test_pos
    print(f"  Train Period: {min(train_dates)} to {max(train_dates)} ({len(train_dates)} days, {len(df_train)} records)")
    print(f"  Test Period:  {min(test_dates)} to {max(test_dates)} ({len(test_dates)} days, {len(df_test)} records, {test_pos} positive user-days)")

    if test_pos == 0:
        logger.warning("Zero positive user-days in test set. Adjusting train_ratio to ensure malicious events in test period.")
        split_idx = int(len(dates) * 0.45)
        train_dates = set(dates[:split_idx])
        test_dates = set(dates[split_idx:])
        train_mask = df["date"].isin(train_dates)
        test_mask = df["date"].isin(test_dates)
        df_train = df[train_mask].copy().reset_index(drop=True)
        df_test = df[test_mask].copy().reset_index(drop=True)
        y_train = y_all[train_mask].reset_index(drop=True)
        y_test = y_all[test_mask].reset_index(drop=True)
        test_pos = int(y_test.sum())
        test_neg = len(y_test) - test_pos

    # 5. Fit Individual Models on Train Set Only
    print("\n[Step 3/5] Fitting detection models on training period only (zero test leakage)...")
    feature_cols = [c for c in MODEL_FEATURE_COLUMNS if c in df_train.columns]

    # Model A: Isolation Forest
    print("  -> Fitting Isolation Forest...")
    iso = IsolationForest(n_estimators=100, contamination=0.1, random_state=seed)
    iso.fit(df_train[feature_cols].fillna(0))
    raw_iso = -iso.score_samples(df_test[feature_cols].fillna(0))
    iso_test_scores = _robust_normalize(raw_iso)

    # Model B: Autoencoder (PyTorch)
    print(f"  -> Fitting PyTorch Autoencoder ({epochs} epochs)...")
    ae = AutoencoderDetector(epochs=epochs, seed=seed)
    X_train_raw = df_train[feature_cols].fillna(0.0).values.astype(float)
    X_test_raw = df_test[feature_cols].fillna(0.0).values.astype(float)
    ae.fit(X_train_raw)
    raw_ae_test = ae.score(X_test_raw)
    ae_test_scores = _robust_normalize(raw_ae_test)

    # Model C: LSTM Autoencoder (PyTorch)
    print(f"  -> Fitting PyTorch LSTM Sequence Autoencoder ({epochs} epochs)...")
    train_seqs = []
    for emp_id, g in df_train.groupby("employee_id", sort=False):
        idx = g.sort_values("date").index.tolist()
        train_seqs.append(g.loc[idx, feature_cols].fillna(0.0).values.astype(float))
    lstm = LSTMSequenceDetector(epochs=epochs, seed=seed)
    lstm.fit(train_seqs)

    test_seqs, test_order = [], []
    for emp_id, g in df_test.groupby("employee_id", sort=False):
        idx = g.sort_values("date").index.tolist()
        test_seqs.append(g.loc[idx, feature_cols].fillna(0.0).values.astype(float))
        test_order.append(idx)

    lstm_scores_by_seq = lstm.score_all(test_seqs)
    lstm_test_raw = np.zeros(len(df_test))
    for idx_list, seq_scores in zip(test_order, lstm_scores_by_seq):
        for pos, row_idx in enumerate(idx_list):
            lstm_test_raw[df_test.index.get_loc(row_idx)] = seq_scores[pos]
    lstm_test_scores = _robust_normalize(lstm_test_raw)

    # Model D: Supervised XGBoost (trained ONLY on train period labels)
    print("  -> Fitting Supervised XGBoost on train-period labels...")
    if y_train.sum() > 0:
        xgb_clf = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.08,
            random_state=seed,
            eval_metric="logloss",
        )
        xgb_clf.fit(df_train[feature_cols].fillna(0), y_train)
        xgb_test_scores = xgb_clf.predict_proba(df_test[feature_cols].fillna(0))[:, 1]
    else:
        # Weakly supervised fallback on Isolation Forest decile if train set had 0 labels
        xgb_clf = xgb.XGBClassifier(n_estimators=50, max_depth=3, random_state=seed)
        pseudo_labels = (iso.score_samples(df_train[feature_cols].fillna(0)) < np.percentile(iso.score_samples(df_train[feature_cols].fillna(0)), 10)).astype(int)
        xgb_clf.fit(df_train[feature_cols].fillna(0), pseudo_labels)
        xgb_test_scores = xgb_clf.predict_proba(df_test[feature_cols].fillna(0))[:, 1]

    # Model E: Naive Static Threshold Baseline
    # Flag upload_mb_total > 95th percentile or usb_events > 95th percentile
    print("  -> Computing Naive Static Threshold Baseline...")
    upload_threshold = np.percentile(df_train["upload_mb_total"].fillna(0), 95)
    usb_threshold = np.percentile(df_train["usb_events"].fillna(0), 95)
    naive_test_scores = (
        (df_test["upload_mb_total"].fillna(0) > upload_threshold).astype(float) * 0.5 +
        (df_test["usb_events"].fillna(0) > usb_threshold).astype(float) * 0.5
    ).values

    # Model F: Full Sentinel AI Ensemble (Risk Engine Blending)
    print("  -> Running Dynamic Risk Engine ensemble blending...")
    df_test_scored = df_test.copy()
    df_test_scored["isolation_forest_score"] = iso_test_scores
    df_test_scored["autoencoder_score"] = ae_test_scores
    df_test_scored["lstm_score"] = lstm_test_scores
    df_test_scored["xgboost_score"] = xgb_test_scores

    risked_test = compute_risk(df_test_scored)
    ensemble_scores = risked_test["risk_score"].values
    ensemble_tiers = risked_test["risk_tier"].values

    # 6. Evaluation on Test Period
    print("\n[Step 4/5] Computing performance metrics, curves, and incident detection recall on test period...")
    models_dict = {
        "Isolation Forest": iso_test_scores,
        "Autoencoder": ae_test_scores,
        "LSTM Autoencoder": lstm_test_scores,
        "XGBoost": xgb_test_scores,
        "Naive Baseline": naive_test_scores,
        "Sentinel AI Ensemble": ensemble_scores / 100.0, # Scaled to 0-1 for AUC
    }

    # High tier threshold predictions for ensemble (risk_score >= 70.0)
    ensemble_high_pred = (ensemble_scores >= 70.0).astype(int)

    model_metrics = {}
    for name, raw_scores in models_dict.items():
        try:
            auc_val = float(roc_auc_score(y_test, raw_scores))
        except Exception:
            auc_val = 0.5

        try:
            pr_val = float(average_precision_score(y_test, raw_scores))
        except Exception:
            pr_val = 0.0

        # High tier threshold decision
        if name == "Sentinel AI Ensemble":
            preds = ensemble_high_pred
        elif name == "Naive Baseline":
            preds = (raw_scores >= 0.5).astype(int)
        else:
            # 85th percentile threshold
            thresh = np.percentile(raw_scores, 85)
            preds = (raw_scores >= thresh).astype(int)

        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))
        f1 = float(f1_score(y_test, preds, zero_division=0))

        # Precision@k
        ranked_indices = np.argsort(raw_scores)[::-1]
        p_at_5 = float(y_test.iloc[ranked_indices[:5]].mean()) if len(y_test) >= 5 else 0.0
        p_at_10 = float(y_test.iloc[ranked_indices[:10]].mean()) if len(y_test) >= 10 else 0.0
        p_at_20 = float(y_test.iloc[ranked_indices[:20]].mean()) if len(y_test) >= 20 else 0.0

        model_metrics[name] = {
            "roc_auc": round(auc_val, 4),
            "pr_auc": round(pr_val, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "precision_at_5": round(p_at_5, 4),
            "precision_at_10": round(p_at_10, 4),
            "precision_at_20": round(p_at_20, 4),
        }

    # Confusion Matrix for Sentinel AI Ensemble at High Tier (score >= 70)
    cm = confusion_matrix(y_test, ensemble_high_pred)
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
    confusion = {
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "threshold": 70.0,
    }

    # Alerts per analyst-day on test period
    num_test_days = max(1, len(test_dates))
    alerts_per_day = round(float(ensemble_high_pred.sum()) / num_test_days, 2)

    # Mean days-to-detection per malicious user in test period
    days_to_detection = []
    risked_test["is_threat"] = y_test.values
    risked_test["is_alert"] = ensemble_high_pred

    for user, windows in insider_windows.items():
        user_rows = risked_test[risked_test["employee_id"] == user].sort_values("date")
        if user_rows.empty:
            continue
        threat_days = user_rows[user_rows["is_threat"] == 1]
        if threat_days.empty:
            continue

        first_threat_date = threat_days["date"].iloc[0]
        alert_days = threat_days[threat_days["is_alert"] == 1]

        if not alert_days.empty:
            first_alert_date = alert_days["date"].iloc[0]
            delay = (first_alert_date - first_threat_date).days
            days_to_detection.append(max(0, delay))
        else:
            # Penalized by full window length
            days_to_detection.append(len(threat_days))

    mean_days_to_detection = round(float(np.mean(days_to_detection)), 1) if days_to_detection else 0.0

    # 7. Compute ROC and PR curve points for frontend Recharts
    fpr, tpr, _ = roc_curve(y_test, ensemble_scores / 100.0)
    pr_prec, pr_rec, _ = precision_recall_curve(y_test, ensemble_scores / 100.0)

    # Subsample to ~25 points for crisp chart plotting
    sub_indices_roc = np.linspace(0, len(fpr) - 1, min(25, len(fpr)), dtype=int)
    roc_points = [
        {"fpr": round(float(fpr[i]), 3), "tpr": round(float(tpr[i]), 3)}
        for i in sub_indices_roc
    ]

    sub_indices_pr = np.linspace(0, len(pr_rec) - 1, min(25, len(pr_rec)), dtype=int)
    pr_points = [
        {"recall": round(float(pr_rec[i]), 3), "precision": round(float(pr_prec[i]), 3)}
        for i in sub_indices_pr
    ]

    curves = {
        "roc": roc_points,
        "pr": pr_points,
    }

    full_metrics = {
        "models": model_metrics,
        "confusion_matrix": confusion,
        "alerts_per_analyst_day": alerts_per_day,
        "mean_days_to_detection": mean_days_to_detection,
        "test_records_count": len(df_test),
        "test_positives_count": test_pos,
        "test_negatives_count": test_neg,
    }

    config = {
        "data_path": data_path,
        "num_users": len(selected_users),
        "num_days": len(dates),
        "train_days": len(train_dates),
        "test_days": len(test_dates),
        "train_start": str(min(train_dates)),
        "train_end": str(max(train_dates)),
        "test_start": str(min(test_dates)),
        "test_end": str(max(test_dates)),
        "seed": seed,
        "epochs": epochs,
    }

    # 8. Store in Database
    print("\n[Step 5/5] Persisting evaluation results to PostgreSQL evaluation_runs table...")
    db = SessionLocal()
    try:
        run = EvaluationRun(
            dataset=f"CERT r4.2 ({len(selected_users)} users)",
            n_users=len(selected_users),
            n_days=len(dates),
            config=config,
            metrics=full_metrics,
            curves=curves,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        print(f"✓ Saved EvaluationRun #{run_id} to database.")
    finally:
        db.close()

    # 9. Print Formatted Comparison Table
    print("\n" + "=" * 90)
    print("BENCHMARK COMPARISON TABLE — TEST PERIOD (CHRONOLOGICAL SPLIT, ZERO LEAKAGE)")
    print("=" * 90)
    header = f"{'Model':<24} | {'ROC-AUC':<8} | {'PR-AUC':<8} | {'Precision':<10} | {'Recall':<8} | {'F1':<6} | {'P@10':<6}"
    print(header)
    print("-" * len(header))
    for m_name, m_val in model_metrics.items():
        star = " ★" if m_name == "Sentinel AI Ensemble" else ""
        print(
            f"{m_name + star:<24} | "
            f"{m_val['roc_auc']:<8.4f} | "
            f"{m_val['pr_auc']:<8.4f} | "
            f"{m_val['precision']:<10.4f} | "
            f"{m_val['recall']:<8.4f} | "
            f"{m_val['f1']:<6.4f} | "
            f"{m_val['precision_at_10']:<6.4f}"
        )
    print("=" * 90)
    print(f"Ensemble Operational Stats (High-Tier Risk Score >= 70):")
    print(f"  • Alerts/Analyst-Day:    {alerts_per_day}")
    print(f"  • Mean Days to Detect:   {mean_days_to_detection} days")
    print(f"  • Confusion Matrix:      TP={tp}, FP={fp}, FN={fn}, TN={tn}")
    print("=" * 90)

    return {
        "run_id": run_id,
        "config": config,
        "metrics": full_metrics,
        "curves": curves,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Sentinel AI on CERT Insider Threat r4.2 Benchmark.")
    parser.add_argument("--dataset", type=str, default="cert", help="Dataset name ('cert')")
    parser.add_argument("--path", type=str, default="data/cert_r4.2", help="Path to CERT dataset directory")
    parser.add_argument("--users", type=int, default=100, help="Number of users in subset (default: 100)")
    parser.add_argument("--train-ratio", type=float, default=0.6, help="Temporal train ratio (default: 0.6)")
    parser.add_argument("--epochs", type=int, default=8, help="PyTorch Autoencoder/LSTM training epochs (default: 8)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic sampling")
    args = parser.parse_args()

    # Resolve relative path if run from backend/ or root
    path = args.path
    if not os.path.isabs(path):
        if not os.path.exists(path):
            alt_path = os.path.join("..", path)
            if os.path.exists(alt_path):
                path = alt_path

    init_db()
    evaluate_cert_pipeline(
        data_path=path,
        num_users=args.users,
        train_ratio=args.train_ratio,
        epochs=args.epochs,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
