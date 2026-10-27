from fastapi import APIRouter, Depends
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RiskRecord, AnalystFeedback

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.get("/stats")
def feedback_stats(db: Session = Depends(get_db)):
    """Counts per label, total labeled, and share of High/Critical alerts reviewed."""
    threat_count = (
        db.query(AnalystFeedback)
        .filter(AnalystFeedback.label == "threat")
        .count()
    )
    fp_count = (
        db.query(AnalystFeedback)
        .filter(AnalystFeedback.label == "false_positive")
        .count()
    )
    total_labeled = threat_count + fp_count

    total_alerts = (
        db.query(RiskRecord)
        .filter(RiskRecord.risk_tier.in_(["High", "Critical"]))
        .count()
    )

    reviewed_alerts = (
        db.query(RiskRecord)
        .join(
            AnalystFeedback,
            and_(
                RiskRecord.employee_id == AnalystFeedback.employee_id,
                RiskRecord.date == AnalystFeedback.date,
            ),
        )
        .filter(RiskRecord.risk_tier.in_(["High", "Critical"]))
        .count()
    )

    share_reviewed = round(reviewed_alerts / total_alerts, 4) if total_alerts > 0 else 0.0

    return {
        "counts": {
            "threat": threat_count,
            "false_positive": fp_count,
        },
        "total_labeled": total_labeled,
        "total_alerts": total_alerts,
        "reviewed_alerts": reviewed_alerts,
        "reviewed_share": share_reviewed,
    }
