from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RiskRecord

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    tier: str | None = Query(None, description="Filter by risk_tier, e.g. 'High'"),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    """The Incident Timeline / SOC alert queue: High and Critical days,
    most recent and highest-risk first, each with the AI Investigation
    Agent's explanation attached."""
    q = db.query(RiskRecord)
    if tier:
        q = q.filter(RiskRecord.risk_tier == tier)
    else:
        q = q.filter(RiskRecord.risk_tier.in_(["High", "Critical"]))

    records = q.order_by(RiskRecord.risk_score.desc(), RiskRecord.date.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "employee_id": r.employee_id,
            "date": r.date.isoformat(),
            "risk_score": r.risk_score,
            "risk_tier": r.risk_tier,
            "rule_flags": r.rule_flags,
            "explanation": r.explanation,
            "agent_source": r.agent_source,
            "model_breakdown": {
                "isolation_forest": round(r.isolation_forest_score, 3),
                "autoencoder": round(r.autoencoder_score, 3),
                "lstm": round(r.lstm_score, 3),
                "xgboost": round(r.xgboost_score, 3),
            },
        }
        for r in records
    ]
