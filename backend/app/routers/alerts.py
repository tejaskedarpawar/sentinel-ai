from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import RiskRecord, AnalystFeedback, AlertCase

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class FeedbackRequest(BaseModel):
    label: Literal["threat", "false_positive"]
    analyst: str = Field(default="analyst")
    note: str | None = None


@router.get("")
def list_alerts(
    tier: str | None = Query(None, description="Filter by risk_tier, e.g. 'High'"),
    reviewed: bool | None = Query(None, description="Filter by reviewed status (true/false)"),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    """The Incident Timeline / SOC alert queue: High and Critical days,
    most recent and highest-risk first, each with the AI Investigation
    Agent's explanation, case status, and any analyst feedback attached."""
    q = (
        db.query(RiskRecord, AnalystFeedback, AlertCase)
        .outerjoin(
            AnalystFeedback,
            and_(
                RiskRecord.employee_id == AnalystFeedback.employee_id,
                RiskRecord.date == AnalystFeedback.date,
            ),
        )
        .outerjoin(
            AlertCase,
            and_(
                RiskRecord.employee_id == AlertCase.employee_id,
                RiskRecord.date == AlertCase.date,
            ),
        )
    )

    if tier:
        q = q.filter(RiskRecord.risk_tier == tier)
    else:
        q = q.filter(RiskRecord.risk_tier.in_(["High", "Critical"]))

    if reviewed is True:
        q = q.filter(AnalystFeedback.id.isnot(None))
    elif reviewed is False:
        q = q.filter(AnalystFeedback.id.is_(None))

    rows = q.order_by(RiskRecord.risk_score.desc(), RiskRecord.date.desc()).limit(limit).all()

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
            "feedback": (
                {
                    "label": fb.label,
                    "analyst": fb.analyst,
                    "created_at": fb.created_at.isoformat(),
                }
                if fb is not None
                else None
            ),
            "case_status": case.status if case else "New",
            "assignee": case.assignee if case else None,
        }
        for r, fb, case in rows
    ]


@router.post("/{employee_id}/{date}/feedback")
def upsert_feedback(
    employee_id: str,
    date: str,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """Upsert analyst feedback (threat | false_positive) for an alert,
    and automatically update the associated case status."""
    from app.routers.cases import sync_case_from_feedback

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    fb = (
        db.query(AnalystFeedback)
        .filter(
            AnalystFeedback.employee_id == employee_id,
            AnalystFeedback.date == parsed_date,
        )
        .first()
    )

    if fb:
        fb.label = body.label
        fb.analyst = body.analyst or "analyst"
        fb.note = body.note
        fb.created_at = datetime.utcnow()
    else:
        fb = AnalystFeedback(
            employee_id=employee_id,
            date=parsed_date,
            label=body.label,
            analyst=body.analyst or "analyst",
            note=body.note,
            created_at=datetime.utcnow(),
        )
        db.add(fb)

    db.commit()
    db.refresh(fb)

    # Link feedback to case status: false_positive -> Resolved, threat -> Investigating
    sync_case_from_feedback(db, employee_id, parsed_date, body.label)

    return {
        "status": "success",
        "feedback": {
            "id": fb.id,
            "employee_id": fb.employee_id,
            "date": fb.date.isoformat(),
            "label": fb.label,
            "analyst": fb.analyst,
            "note": fb.note,
            "created_at": fb.created_at.isoformat(),
        },
    }


@router.delete("/{employee_id}/{date}/feedback")
def delete_feedback(
    employee_id: str,
    date: str,
    db: Session = Depends(get_db),
):
    """Remove analyst feedback for an alert."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    fb = (
        db.query(AnalystFeedback)
        .filter(
            AnalystFeedback.employee_id == employee_id,
            AnalystFeedback.date == parsed_date,
        )
        .first()
    )

    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")

    db.delete(fb)
    db.commit()
    return {"status": "deleted", "employee_id": employee_id, "date": date}


@router.get("/{employee_id}/{date}/explain")
def get_alert_explainability(
    employee_id: str,
    date: str,
    db: Session = Depends(get_db),
):
    """
    Per-alert explainability:
    - TreeSHAP contributions from XGBoost (top 8 features)
    - Trailing 7-day baseline deviation z-scores (top 5 key features)
    - Plain-language synthesis summary
    """
    from app.detection.explain import explain_alert

    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    result = explain_alert(db, employee_id, parsed_date)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
