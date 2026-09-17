"""
Dynamic Risk Engine.

Blends the four detection-model scores with a small set of auditable
rule boosts (things a SOC analyst would immediately recognise, like an
off-hours upload to a personal destination) into one 0-100 risk score
per employee-day, plus a tier used for triage and a list of the
specific rule_flags that fired — the raw material the AI Investigation
Agent turns into a plain-language explanation.
"""
import pandas as pd

MODEL_WEIGHTS = {
    "isolation_forest_score": 0.25,
    "autoencoder_score": 0.25,
    "lstm_score": 0.25,
    "xgboost_score": 0.25,
}

RULE_BOOSTS = {
    "off_hours_upload": 12,
    "risky_destination": 10,
    "unusual_geo": 15,
    "privilege_escalation": 10,
    "split_transfer": 8,       # many small uploads same day = possible fragmentation
    "usb_spike": 10,
}

TIER_THRESHOLDS = [(85, "Critical"), (60, "High"), (35, "Medium"), (0, "Low")]


def _tier_for(score: float) -> str:
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "Low"


def compute_risk(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    model_cols = list(MODEL_WEIGHTS.keys())
    mean_score = out[model_cols].mean(axis=1)
    max_score = out[model_cols].max(axis=1)
    # Favour recall: if even one model is highly confident, don't let an
    # average with three lukewarm models bury it. 60% weight on the
    # strongest single signal, 40% on overall ensemble agreement.
    model_component = (0.6 * max_score + 0.4 * mean_score) * 70  # up to 70 pts

    rule_flags_col = []
    rule_points_col = []
    for _, row in out.iterrows():
        flags = []
        points = 0
        if row.get("off_hours_event", 0) and row.get("upload_count", 0) > 0:
            flags.append("off_hours_upload"); points += RULE_BOOSTS["off_hours_upload"]
        if row.get("risky_destination_count", 0) > 0:
            flags.append("risky_destination"); points += RULE_BOOSTS["risky_destination"]
        if row.get("unusual_geo", 0):
            flags.append("unusual_geo"); points += RULE_BOOSTS["unusual_geo"]
        if row.get("privilege_escalation", 0):
            flags.append("privilege_escalation"); points += RULE_BOOSTS["privilege_escalation"]
        if row.get("upload_count", 0) >= 3:
            flags.append("split_transfer"); points += RULE_BOOSTS["split_transfer"]
        if row.get("usb_events", 0) >= 4:
            flags.append("usb_spike"); points += RULE_BOOSTS["usb_spike"]
        rule_flags_col.append(flags)
        rule_points_col.append(points)

    out["rule_flags"] = rule_flags_col
    rule_component = pd.Series(rule_points_col, index=out.index).clip(upper=30)  # up to 30 pts

    out["risk_score"] = (model_component + rule_component).clip(0, 100).round(1)
    out["risk_tier"] = out["risk_score"].apply(_tier_for)
    return out
