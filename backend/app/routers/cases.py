from datetime import datetime, date as date_type
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, RiskRecord, AlertCase, CaseNote, AnalystFeedback
from app.reporting import generate_incident_pdf

router = APIRouter(prefix="/api/cases", tags=["cases"])


class CaseUpdateRequest(BaseModel):
    status: Literal["New", "Investigating", "Resolved"] | None = None
    assignee: str | None = None


class CaseNoteCreateRequest(BaseModel):
    author: str = Field(default="analyst")
    text: str = Field(..., min_length=1)


def get_or_create_case(db: Session, employee_id: str, case_date: date_type) -> AlertCase:
    """
    Retrieves the case for (employee_id, case_date), or lazily creates it with
    status 'New' the first time it is read or modified.
    """
    case = (
        db.query(AlertCase)
        .filter(AlertCase.employee_id == employee_id, AlertCase.date == case_date)
        .first()
    )
    if not case:
        record = (
            db.query(RiskRecord)
            .filter(RiskRecord.employee_id == employee_id, RiskRecord.date == case_date)
            .first()
        )
        priority = record.risk_tier if record else "Medium"
        case = AlertCase(
            employee_id=employee_id,
            date=case_date,
            status="New",
            priority=priority,
            assignee=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(case)
        db.commit()
        db.refresh(case)
    return case


def sync_case_from_feedback(db: Session, employee_id: str, case_date: date_type, label: str) -> AlertCase:
    """
    Link to feedback: marking 'false_positive' sets status to Resolved;
    marking 'threat' sets status to Investigating (only if currently New).
    """
    case = get_or_create_case(db, employee_id, case_date)
    if label == "false_positive":
        case.status = "Resolved"
        case.updated_at = datetime.utcnow()
        db.commit()
    elif label == "threat":
        if case.status == "New":
            case.status = "Investigating"
            case.updated_at = datetime.utcnow()
            db.commit()
    db.refresh(case)
    return case


@router.get("")
def list_cases(
    status: str | None = Query(None, description="Filter by case status: 'New', 'Investigating', 'Resolved'"),
    assignee: str | None = Query(None, description="Filter by investigator assignee"),
    tier: str | None = Query(None, description="Filter by risk_tier, e.g. 'Critical'"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List alert cases (lazily including all High/Critical alerts as 'New' cases if not yet modified).
    Paginated with status, assignee, and tier filters.
    """
    q = (
        db.query(RiskRecord, Employee, AlertCase, AnalystFeedback)
        .join(Employee, RiskRecord.employee_id == Employee.id)
        .outerjoin(
            AlertCase,
            and_(
                RiskRecord.employee_id == AlertCase.employee_id,
                RiskRecord.date == AlertCase.date,
            ),
        )
        .outerjoin(
            AnalystFeedback,
            and_(
                RiskRecord.employee_id == AnalystFeedback.employee_id,
                RiskRecord.date == AnalystFeedback.date,
            ),
        )
        .filter(
            or_(
                RiskRecord.risk_tier.in_(["High", "Critical"]),
                AlertCase.id.isnot(None),
            )
        )
    )

    if tier:
        q = q.filter(RiskRecord.risk_tier == tier)

    if status:
        if status == "New":
            q = q.filter(or_(AlertCase.status == "New", AlertCase.id.is_(None)))
        else:
            q = q.filter(AlertCase.status == status)

    if assignee:
        q = q.filter(AlertCase.assignee == assignee)

    rows = q.order_by(RiskRecord.risk_score.desc(), RiskRecord.date.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": c.id if c else None,
            "employee_id": r.employee_id,
            "employee_name": emp.name,
            "department": emp.department,
            "date": r.date.isoformat(),
            "status": c.status if c else "New",
            "assignee": c.assignee if c else None,
            "priority": c.priority if c else r.risk_tier,
            "risk_score": r.risk_score,
            "risk_tier": r.risk_tier,
            "rule_flags": r.rule_flags,
            "created_at": c.created_at.isoformat() if c else r.date.isoformat(),
            "updated_at": c.updated_at.isoformat() if c else r.date.isoformat(),
            "has_feedback": fb is not None,
            "feedback_label": fb.label if fb else None,
        }
        for r, emp, c, fb in rows
    ]


@router.get("/{employee_id}/{date}")
def get_case(
    employee_id: str,
    date: str,
    db: Session = Depends(get_db),
):
    """
    Get full case details: case status, notes list, risk score breakdown,
    plain-language explanation, and any analyst verdict.
    Creates case lazily with status 'New' if not already present.
    """
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    case = get_or_create_case(db, employee_id, parsed_date)
    record = (
        db.query(RiskRecord)
        .filter(RiskRecord.employee_id == employee_id, RiskRecord.date == parsed_date)
        .first()
    )
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    feedback = (
        db.query(AnalystFeedback)
        .filter(AnalystFeedback.employee_id == employee_id, AnalystFeedback.date == parsed_date)
        .first()
    )
    notes = (
        db.query(CaseNote)
        .filter(CaseNote.employee_id == employee_id, CaseNote.date == parsed_date)
        .order_by(CaseNote.created_at.asc())
        .all()
    )

    return {
        "case": {
            "id": case.id,
            "employee_id": case.employee_id,
            "date": case.date.isoformat(),
            "status": case.status,
            "assignee": case.assignee,
            "priority": case.priority,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
        "alert": (
            {
                "employee_id": record.employee_id,
                "employee_name": employee.name if employee else record.employee_id,
                "department": employee.department if employee else "Unassigned",
                "date": record.date.isoformat(),
                "risk_score": record.risk_score,
                "risk_tier": record.risk_tier,
                "rule_flags": record.rule_flags,
                "explanation": record.explanation,
                "agent_source": record.agent_source,
                "model_breakdown": {
                    "isolation_forest": round(record.isolation_forest_score, 3),
                    "autoencoder": round(record.autoencoder_score, 3),
                    "lstm": round(record.lstm_score, 3),
                    "xgboost": round(record.xgboost_score, 3),
                },
                "features": record.features,
            }
            if record
            else None
        ),
        "feedback": (
            {
                "label": feedback.label,
                "analyst": feedback.analyst,
                "note": feedback.note,
                "created_at": feedback.created_at.isoformat(),
            }
            if feedback
            else None
        ),
        "notes": [
            {
                "id": n.id,
                "employee_id": n.employee_id,
                "date": n.date.isoformat(),
                "author": n.author,
                "text": n.text,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ],
    }


@router.patch("/{employee_id}/{date}")
def update_case(
    employee_id: str,
    date: str,
    body: CaseUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update case status ('New' | 'Investigating' | 'Resolved') or assignee."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    case = get_or_create_case(db, employee_id, parsed_date)

    if body.status is not None:
        case.status = body.status
    if body.assignee is not None:
        case.assignee = body.assignee

    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)

    return {
        "status": "success",
        "case": {
            "id": case.id,
            "employee_id": case.employee_id,
            "date": case.date.isoformat(),
            "status": case.status,
            "assignee": case.assignee,
            "priority": case.priority,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
    }


@router.post("/{employee_id}/{date}/notes")
def add_case_note(
    employee_id: str,
    date: str,
    body: CaseNoteCreateRequest,
    db: Session = Depends(get_db),
):
    """Add an analyst note to the case."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    case = get_or_create_case(db, employee_id, parsed_date)

    note = CaseNote(
        employee_id=employee_id,
        date=parsed_date,
        author=body.author or "analyst",
        text=body.text,
        created_at=datetime.utcnow(),
    )
    case.updated_at = datetime.utcnow()
    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "id": note.id,
        "employee_id": note.employee_id,
        "date": note.date.isoformat(),
        "author": note.author,
        "text": note.text,
        "created_at": note.created_at.isoformat(),
    }


@router.get("/{employee_id}/{date}/report.pdf")
def download_incident_pdf(
    employee_id: str,
    date: str,
    db: Session = Depends(get_db),
):
    """Generates and serves the formal PDF Incident Report."""
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    pdf_bytes = generate_incident_pdf(db, employee_id, parsed_date)

    filename = f"incident_report_{employee_id}_{date}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
