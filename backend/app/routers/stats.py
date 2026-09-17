from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import RiskRecord, Employee

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(RiskRecord.id)).scalar() or 0
    employees = db.query(func.count(Employee.id)).scalar() or 0

    tier_counts = dict(
        db.query(RiskRecord.risk_tier, func.count(RiskRecord.id))
        .group_by(RiskRecord.risk_tier)
        .all()
    )

    return {
        "total_employee_days": total,
        "employees_monitored": employees,
        "by_tier": {t: tier_counts.get(t, 0) for t in ["Low", "Medium", "High", "Critical"]},
    }
