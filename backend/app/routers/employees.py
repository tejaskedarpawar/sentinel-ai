from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, RiskRecord

router = APIRouter(prefix="/api/employees", tags=["employees"])

TIER_RANK = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


@router.get("")
def list_employees(db: Session = Depends(get_db)):
    """One row per employee: latest risk score/tier + a small peak
    summary, for the dashboard's main table."""
    employees = db.query(Employee).all()
    out = []
    for emp in employees:
        records = (
            db.query(RiskRecord)
            .filter(RiskRecord.employee_id == emp.id)
            .order_by(RiskRecord.date.asc())
            .all()
        )
        if not records:
            continue
        latest = records[-1]
        peak = max(records, key=lambda r: r.risk_score)
        out.append({
            "id": emp.id,
            "name": emp.name,
            "department": emp.department,
            "latest_risk_score": latest.risk_score,
            "latest_risk_tier": latest.risk_tier,
            "peak_risk_score": peak.risk_score,
            "peak_risk_tier": peak.risk_tier,
            "peak_date": peak.date.isoformat(),
            "days_tracked": len(records),
            "scenario": latest.scenario,  # demo-only ground-truth label
        })
    out.sort(key=lambda r: r["peak_risk_score"], reverse=True)
    return out


@router.get("/{employee_id}")
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"id": emp.id, "name": emp.name, "department": emp.department}


@router.get("/{employee_id}/timeline")
def get_employee_timeline(employee_id: str, db: Session = Depends(get_db)):
    """Full day-by-day risk history for one employee, for the
    dashboard's risk-trend chart and incident detail view."""
    records = (
        db.query(RiskRecord)
        .filter(RiskRecord.employee_id == employee_id)
        .order_by(RiskRecord.date.asc())
        .all()
    )
    if not records:
        raise HTTPException(status_code=404, detail="No records for this employee")

    return [
        {
            "date": r.date.isoformat(),
            "risk_score": r.risk_score,
            "risk_tier": r.risk_tier,
            "isolation_forest_score": round(r.isolation_forest_score, 3),
            "autoencoder_score": round(r.autoencoder_score, 3),
            "lstm_score": round(r.lstm_score, 3),
            "xgboost_score": round(r.xgboost_score, 3),
            "rule_flags": r.rule_flags,
            "explanation": r.explanation,
            "agent_source": r.agent_source,
        }
        for r in records
    ]
