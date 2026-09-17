"""
AI Threat Detection Engine — combines four models into one ensemble:

  * Isolation Forest (scikit-learn) — fast unsupervised outlier detection
    on each employee-day's raw feature vector.
  * Autoencoder (PyTorch)          — reconstruction-error anomaly score,
    same per-day feature vector, standardised.
  * LSTM sequence autoencoder (PyTorch) — reconstruction error across
    each employee's *day-by-day sequence*, catching slow-drip trends
    a single-day model would miss.
  * XGBoost (weakly supervised)    — trained on the Isolation Forest's
    own top-decile flags as pseudo-labels, giving a supervised-style
    score without hand-labelled data (this is a defensible bootstrap
    for a semester-project scale prototype — swap in real analyst
    feedback labels once the system is deployed and triaged alerts
    start accumulating).

All four scores feed the Dynamic Risk Engine, which is the layer that
actually turns them into the 0-100 risk score analysts see.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import xgboost as xgb

from app.detection.autoencoder import AutoencoderDetector
from app.detection.lstm import LSTMSequenceDetector
from app.profiling import FEATURE_COLUMNS

DEVIATION_COLUMNS = ["upload_mb_total_deviation", "network_mb_deviation", "usb_events_deviation"]
MODEL_FEATURE_COLUMNS = FEATURE_COLUMNS + DEVIATION_COLUMNS


def _robust_normalize(x: np.ndarray) -> np.ndarray:
    """Median/MAD-based normalisation to roughly [0, 1). Unlike min-max
    or percentile-rank scaling, this neither lets one extreme outlier
    compress every other score toward zero, nor forces a fixed
    percentage of days into the 'high' range regardless of whether
    they're actually anomalous — most in-baseline days genuinely land
    near 0, and only days meaningfully far (in MAD units) from the
    population's typical day get pushed up, saturating smoothly."""
    median = np.median(x)
    mad = np.median(np.abs(x - median))
    mad = mad if mad > 1e-6 else (x.std() + 1e-6)
    z = np.clip((x - median) / (1.4826 * mad), 0, None)
    return 1 - np.exp(-z / 3.0)


class DetectionEngine:
    def __init__(self):
        self.iso = IsolationForest(n_estimators=200, contamination=0.08, random_state=42)
        self.ae = AutoencoderDetector(epochs=200)
        self.lstm = LSTMSequenceDetector(epochs=150)
        self.xgb_model = None

    def fit_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fits all four models on `df` (one row per employee-day, as
        produced by profiling.build_feature_matrix) and returns df with
        four new score columns plus the blended notes needed downstream."""
        X = df[MODEL_FEATURE_COLUMNS].fillna(0.0).values.astype(float)

        # 1. Isolation Forest
        self.iso.fit(X)
        raw_iso = -self.iso.score_samples(X)  # higher = more anomalous
        iso_score = (raw_iso - raw_iso.min()) / (raw_iso.max() - raw_iso.min() + 1e-9)

        # 2. Autoencoder
        self.ae.fit(X)
        ae_score = np.clip(self.ae.score(X), 0, 2) / 2.0

        # 3. LSTM sequence autoencoder — needs per-employee ordered sequences
        sequences, order_index = [], []
        for emp_id, g in df.groupby("employee_id", sort=False):
            idx = g.sort_values("date").index.tolist()
            sequences.append(g.loc[idx, MODEL_FEATURE_COLUMNS].fillna(0.0).values.astype(float))
            order_index.append(idx)
        self.lstm.fit(sequences)
        lstm_scores_by_seq = self.lstm.score_all(sequences)
        lstm_score = np.zeros(len(df))
        for idx_list, seq_scores in zip(order_index, lstm_scores_by_seq):
            for pos, row_idx in enumerate(idx_list):
                lstm_score[df.index.get_loc(row_idx)] = min(seq_scores[pos], 2.0) / 2.0

        # 4. XGBoost — weakly supervised on Isolation Forest's top decile
        pseudo_labels = (raw_iso >= np.quantile(raw_iso, 0.92)).astype(int)
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.1,
            eval_metric="logloss", random_state=42,
        )
        self.xgb_model.fit(X, pseudo_labels)
        xgb_score = self.xgb_model.predict_proba(X)[:, 1]

        out = df.copy()
        # Robust-normalise each model's raw anomaly signal before
        # blending (see _robust_normalize) so typical days cluster near
        # 0 and only genuinely unusual days get pushed up — instead of
        # a fixed percentage always landing in the 'high' range.
        out["isolation_forest_score"] = _robust_normalize(raw_iso)
        out["autoencoder_score"] = _robust_normalize(self.ae.score(X))
        out["lstm_score"] = _robust_normalize(lstm_score * 2.0)  # undo the /2.0 clip-scale above
        out["xgboost_score"] = xgb_score  # already a calibrated 0-1 probability
        return out
