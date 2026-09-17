"""
AI Investigation Agent.

Turns a flagged employee-day's risk score, model breakdown, and
rule_flags into a plain-language explanation a SOC analyst can act on
without having to interpret four raw model scores themselves.

Two modes, chosen via settings.agent_mode:
  * "template" (default) — deterministic, dependency-free, always
    available. Good enough to demo and to unit-test against.
  * "ollama"   — sends the same structured findings to a locally
    running Ollama model (e.g. llama3.1:8b or phi3) for more natural
    phrasing. Falls back to the template automatically if Ollama isn't
    reachable, so the pipeline never breaks because the LLM is down.
"""
import httpx

from app.config import settings

FLAG_DESCRIPTIONS = {
    "off_hours_upload": "an upload outside normal working hours",
    "risky_destination": "a transfer to a personal or unrecognised destination",
    "unusual_geo": "a login from a location this employee doesn't normally use",
    "privilege_escalation": "a privilege-escalation event",
    "split_transfer": "several separate uploads on the same day (possible fragmentation to avoid thresholds)",
    "usb_spike": "an unusually high number of USB events",
}

DOMINANT_MODEL_NAMES = {
    "isolation_forest_score": "unsupervised outlier detection",
    "autoencoder_score": "behavioural-reconstruction anomaly detection",
    "lstm_score": "sequence/trend analysis across recent days",
    "xgboost_score": "the supervised classifier",
}


def _dominant_model(row: dict) -> str:
    scores = {k: row.get(k, 0) for k in DOMINANT_MODEL_NAMES}
    top = max(scores, key=scores.get)
    return DOMINANT_MODEL_NAMES[top]


def _template_explanation(row: dict) -> str:
    flags = row.get("rule_flags", [])
    tier = row.get("risk_tier", "Low")
    emp = row.get("employee_id", "this employee")
    score = row.get("risk_score", 0)

    if not flags:
        return (
            f"{emp} was flagged {tier} ({score}/100) primarily by {_dominant_model(row)}, "
            f"based on a deviation from their usual behavioural baseline rather than any single "
            f"rule-based signal. Recommend a manual review of the day's activity."
        )

    flag_text = "; ".join(FLAG_DESCRIPTIONS.get(f, f) for f in flags)
    return (
        f"{emp} was flagged {tier} ({score}/100). Detected: {flag_text}. "
        f"This was corroborated by {_dominant_model(row)}, which found the day's overall "
        f"behaviour pattern significantly deviated from this employee's own baseline. "
        f"Recommend SOC review, prioritising the flagged destination/device before end of shift."
    )


def _ollama_explanation(row: dict) -> str | None:
    flags = row.get("rule_flags", [])
    flag_text = ", ".join(FLAG_DESCRIPTIONS.get(f, f) for f in flags) or "no single rule triggered"
    prompt = (
        "You are a SOC investigation assistant. Write a 2-3 sentence plain-language "
        "explanation of why this employee-day was flagged, for a human analyst. "
        "Never speculate beyond the given facts.\n\n"
        f"Employee: {row.get('employee_id')}\n"
        f"Risk score: {row.get('risk_score')}/100 ({row.get('risk_tier')})\n"
        f"Rule signals: {flag_text}\n"
        f"Isolation Forest score: {row.get('isolation_forest_score'):.2f}\n"
        f"Autoencoder score: {row.get('autoencoder_score'):.2f}\n"
        f"LSTM trend score: {row.get('lstm_score'):.2f}\n"
        f"XGBoost score: {row.get('xgboost_score'):.2f}\n"
    )
    try:
        resp = httpx.post(
            f"{settings.ollama_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            timeout=15.0,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        return text or None
    except Exception:
        return None  # caller falls back to the template


def explain(row: dict) -> tuple[str, str]:
    """Returns (explanation_text, source) where source is 'ollama' or
    'template' (so the dashboard can show which one produced it)."""
    if settings.agent_mode == "ollama":
        text = _ollama_explanation(row)
        if text:
            return text, "ollama"
    return _template_explanation(row), "template"
