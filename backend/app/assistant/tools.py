"""
Whitelisted, typed, read-only query tools for the Sentinel AI SOC Assistant.

SECURITY RULES:
1. Pure SQLAlchemy ORM queries only — NO raw SQL (no text(), execute(), or string-built queries).
2. Strict argument validation on every parameter.
3. Maximum query time window: 90 days.
4. Maximum rows returned: 50 rows per query.
5. All relative timeframes ("last week", "this month") are anchored to the
   latest date in the dataset, NOT the local system clock.
"""
from datetime import datetime, date, timedelta
from typing import Literal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Employee, RiskRecord, RawMetadataEvent, AlertCase

MAX_DAYS = 90
MAX_ROWS = 50

VALID_DEST_CATEGORIES = ("personal_cloud", "usb", "any")
VALID_TIERS = ("Low", "Medium", "High", "Critical")
VALID_CASE_STATUSES = ("open", "New", "Investigating", "Resolved", "Critical", "all")


def get_anchor_date(db: Session) -> date:
    """Return latest recorded date in the dataset to anchor relative time queries."""
    latest_risk = db.query(func.max(RiskRecord.date)).scalar()
    if latest_risk:
        return latest_risk
    latest_event = db.query(func.max(func.date(RawMetadataEvent.timestamp))).scalar()
    if latest_event:
        return latest_event
    return date.today()


def _clamp_days(days: int | None, default: int = 7) -> int:
    try:
        val = int(days) if days is not None else default
    except (ValueError, TypeError):
        val = default
    return max(1, min(val, MAX_DAYS))


def _clean_str(val: str | None) -> str:
    return str(val).strip() if val else ""


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------

def top_uploaders(
    db: Session,
    days: int = 7,
    destination_category: Literal["personal_cloud", "usb", "any"] = "any",
) -> list[dict]:
    """
    Get employees with the highest data upload volume in megabytes over the last N days.
    Filterable by destination category ('personal_cloud', 'usb', or 'any').
    """
    days = _clamp_days(days, default=7)
    cat = str(destination_category).lower().strip()
    if cat not in VALID_DEST_CATEGORIES:
        cat = "any"

    anchor = get_anchor_date(db)
    start_dt = datetime.combine(anchor - timedelta(days=days), datetime.min.time())

    events = db.query(RawMetadataEvent).filter(
        RawMetadataEvent.event_type == "upload",
        RawMetadataEvent.timestamp >= start_dt,
    ).all()

    # Aggregate by employee
    emp_stats: dict[str, dict] = {}
    for ev in events:
        emp_id = ev.employee_id
        payload = ev.payload or {}
        dest = str(payload.get("destination", "")).lower()
        size_mb = float(payload.get("size_mb", 0.0))

        # Check category filter
        if cat == "personal_cloud":
            if not ("personal" in dest or "dropbox" in dest or "gdrive" in dest or "unknown" in dest or "cloud" in dest):
                continue
        elif cat == "usb":
            if "usb" not in dest:
                continue

        if emp_id not in emp_stats:
            emp_stats[emp_id] = {
                "employee_id": emp_id,
                "total_upload_mb": 0.0,
                "upload_count": 0,
                "destinations": set(),
                "has_risky": False,
            }

        emp_stats[emp_id]["total_upload_mb"] += size_mb
        emp_stats[emp_id]["upload_count"] += 1
        emp_stats[emp_id]["destinations"].add(payload.get("destination", "unknown"))
        if payload.get("risky"):
            emp_stats[emp_id]["has_risky"] = True

    # Join employee names & departments
    emp_ids = list(emp_stats.keys())
    emp_meta = {
        e.id: (e.name, e.department)
        for e in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()
    }

    result = []
    for emp_id, stats in emp_stats.items():
        name, dept = emp_meta.get(emp_id, (emp_id, "Unknown"))
        result.append({
            "employee_id": emp_id,
            "name": name,
            "department": dept,
            "total_upload_mb": round(stats["total_upload_mb"], 1),
            "upload_count": stats["upload_count"],
            "destinations": sorted(list(stats["destinations"])),
            "risky_uploads": stats["has_risky"],
        })

    result.sort(key=lambda x: x["total_upload_mb"], reverse=True)
    return result[:MAX_ROWS]


def employee_summary(db: Session, employee_id: str, days: int = 30) -> list[dict]:
    """
    Get a comprehensive security and risk profile for a specific employee ID.
    Includes department, peak risk score, flagged incident count, and upload volumes.
    """
    emp_id = _clean_str(employee_id).upper()
    days = _clamp_days(days, default=30)
    anchor = get_anchor_date(db)
    start_date = anchor - timedelta(days=days)
    start_dt = datetime.combine(start_date, datetime.min.time())

    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        return []

    records = db.query(RiskRecord).filter(
        RiskRecord.employee_id == emp_id,
        RiskRecord.date >= start_date,
    ).order_by(RiskRecord.date.desc()).all()

    peak_score = max((r.risk_score for r in records), default=0.0)
    flagged_days = [r for r in records if r.risk_tier in ("High", "Critical")]
    latest_record = records[0] if records else None

    # Cases
    cases = db.query(AlertCase).filter(AlertCase.employee_id == emp_id).all()
    open_cases_count = sum(1 for c in cases if c.status in ("New", "Investigating"))

    # Uploads
    uploads = db.query(RawMetadataEvent).filter(
        RawMetadataEvent.employee_id == emp_id,
        RawMetadataEvent.event_type == "upload",
        RawMetadataEvent.timestamp >= start_dt,
    ).all()

    total_mb = sum(float(u.payload.get("size_mb", 0.0)) for u in uploads if u.payload)
    unique_dests = {u.payload.get("destination") for u in uploads if u.payload and u.payload.get("destination")}

    summary = {
        "employee_id": emp.id,
        "name": emp.name,
        "department": emp.department,
        "evaluation_days": len(records),
        "peak_risk_score": round(peak_score, 1),
        "latest_tier": latest_record.risk_tier if latest_record else "Low",
        "flagged_incident_days": len(flagged_days),
        "open_cases": open_cases_count,
        "total_upload_mb": round(total_mb, 1),
        "upload_count": len(uploads),
        "destinations": sorted(list(unique_dests)),
        "recent_flags": latest_record.rule_flags if latest_record else [],
    }
    return [summary]


def alerts_by_tier(
    db: Session,
    tier: Literal["Low", "Medium", "High", "Critical"] = "Critical",
    days: int = 30,
) -> list[dict]:
    """
    List incident alerts filtered by risk tier ('Critical', 'High', 'Medium', 'Low')
    within the last N days.
    """
    tier_clean = _clean_str(tier).capitalize()
    if tier_clean not in VALID_TIERS:
        tier_clean = "Critical"

    days = _clamp_days(days, default=30)
    anchor = get_anchor_date(db)
    start_date = anchor - timedelta(days=days)

    records = db.query(RiskRecord).filter(
        RiskRecord.risk_tier == tier_clean,
        RiskRecord.date >= start_date,
    ).order_by(RiskRecord.risk_score.desc(), RiskRecord.date.desc()).limit(MAX_ROWS).all()

    results = []
    for r in records:
        results.append({
            "employee_id": r.employee_id,
            "date": str(r.date),
            "risk_score": round(r.risk_score, 1),
            "risk_tier": r.risk_tier,
            "rule_flags": r.rule_flags or [],
            "explanation": (r.explanation[:140] + "...") if (r.explanation and len(r.explanation) > 140) else (r.explanation or ""),
        })
    return results


def risk_trend(db: Session, employee_id: str, days: int = 14) -> list[dict]:
    """
    Retrieve chronological risk scores and machine learning breakdown over time
    for a specific employee to analyze behavioral trajectories.
    """
    emp_id = _clean_str(employee_id).upper()
    days = _clamp_days(days, default=14)
    anchor = get_anchor_date(db)
    start_date = anchor - timedelta(days=days)

    records = db.query(RiskRecord).filter(
        RiskRecord.employee_id == emp_id,
        RiskRecord.date >= start_date,
    ).order_by(RiskRecord.date.asc()).limit(MAX_ROWS).all()

    results = []
    for r in records:
        results.append({
            "date": str(r.date),
            "risk_score": round(r.risk_score, 1),
            "risk_tier": r.risk_tier,
            "xgboost": round(r.xgboost_score, 3) if r.xgboost_score else 0.0,
            "isolation_forest": round(r.isolation_forest_score, 3) if r.isolation_forest_score else 0.0,
            "rule_flags": r.rule_flags or [],
        })
    return results


def destinations_for_employee(db: Session, employee_id: str, days: int = 30) -> list[dict]:
    """
    List all destinations an employee uploaded data to over the specified time window,
    with upload counts, total megabytes, and risky flags.
    """
    emp_id = _clean_str(employee_id).upper()
    days = _clamp_days(days, default=30)
    anchor = get_anchor_date(db)
    start_dt = datetime.combine(anchor - timedelta(days=days), datetime.min.time())

    events = db.query(RawMetadataEvent).filter(
        RawMetadataEvent.employee_id == emp_id,
        RawMetadataEvent.event_type == "upload",
        RawMetadataEvent.timestamp >= start_dt,
    ).all()

    dest_map: dict[str, dict] = {}
    for ev in events:
        p = ev.payload or {}
        dest = p.get("destination", "unknown")
        if dest not in dest_map:
            dest_map[dest] = {
                "destination": dest,
                "total_mb": 0.0,
                "upload_count": 0,
                "risky": bool(p.get("risky")),
            }
        dest_map[dest]["total_mb"] += float(p.get("size_mb", 0.0))
        dest_map[dest]["upload_count"] += 1
        if p.get("risky"):
            dest_map[dest]["risky"] = True

    results = list(dest_map.values())
    for r in results:
        r["total_mb"] = round(r["total_mb"], 1)
    results.sort(key=lambda x: x["total_mb"], reverse=True)
    return results[:MAX_ROWS]


def usb_activity(db: Session, days: int = 30) -> list[dict]:
    """
    Retrieve anomalous USB storage device events, bulk mass-storage file transfers,
    and associated risk scores across all employees.
    """
    days = _clamp_days(days, default=30)
    anchor = get_anchor_date(db)
    start_date = anchor - timedelta(days=days)

    records = db.query(RiskRecord).filter(
        RiskRecord.date >= start_date,
    ).all()

    results = []
    for r in records:
        features = r.features or {}
        usb_count = float(features.get("usb_events", 0.0))
        if usb_count > 0:
            results.append({
                "employee_id": r.employee_id,
                "date": str(r.date),
                "usb_events": int(usb_count),
                "risk_score": round(r.risk_score, 1),
                "risk_tier": r.risk_tier,
                "rule_flags": r.rule_flags or [],
            })

    results.sort(key=lambda x: (x["usb_events"], x["risk_score"]), reverse=True)
    return results[:MAX_ROWS]


def open_cases(db: Session, status: Literal["open", "New", "Investigating", "Resolved", "Critical", "all"] = "open") -> list[dict]:
    """
    List SOC investigation cases filtered by status ('open', 'New', 'Investigating',
    'Resolved', 'Critical', or 'all').
    """
    st = str(status).strip()
    if st not in VALID_CASE_STATUSES:
        st = "open"

    q = db.query(AlertCase)
    if st == "open":
        q = q.filter(AlertCase.status.in_(["New", "Investigating"]))
    elif st == "Critical":
        q = q.filter(AlertCase.status.in_(["New", "Investigating"]), AlertCase.priority == "Critical")
    elif st != "all":
        q = q.filter(AlertCase.status.ilike(st))

    cases = q.order_by(AlertCase.updated_at.desc()).limit(MAX_ROWS).all()

    results = []
    for c in cases:
        results.append({
            "employee_id": c.employee_id,
            "date": str(c.date),
            "status": c.status,
            "priority": c.priority or "Unassigned",
            "assignee": c.assignee or "Unassigned",
            "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else "",
        })
    return results


# ---------------------------------------------------------------------------
# Whitelist Registry & Ollama Function Tool Definitions
# ---------------------------------------------------------------------------

WHITELISTED_TOOLS = {
    "top_uploaders": top_uploaders,
    "employee_summary": employee_summary,
    "alerts_by_tier": alerts_by_tier,
    "risk_trend": risk_trend,
    "destinations_for_employee": destinations_for_employee,
    "usb_activity": usb_activity,
    "open_cases": open_cases,
}

OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "top_uploaders",
            "description": "Get employees with the highest data upload volume in megabytes over the last N days. Filterable by destination category ('personal_cloud', 'usb', or 'any').",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback window in days (1 to 90, default: 7)"},
                    "destination_category": {
                        "type": "string",
                        "enum": ["personal_cloud", "usb", "any"],
                        "description": "Category of destination to filter ('personal_cloud', 'usb', or 'any')",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "employee_summary",
            "description": "Get a comprehensive security profile for a specific employee ID (department, peak risk score, flagged incident days, upload stats, open cases).",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "Employee ID (e.g. 'EMP003', 'EMP014')"},
                    "days": {"type": "integer", "description": "Lookback window in days (default: 30)"},
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "alerts_by_tier",
            "description": "List incident alerts filtered by risk tier ('Critical', 'High', 'Medium', 'Low') within the last N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tier": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"], "description": "Risk tier to filter"},
                    "days": {"type": "integer", "description": "Lookback window in days (default: 30)"},
                },
                "required": ["tier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "risk_trend",
            "description": "Retrieve daily risk score history and ML model breakdown for a specific employee over time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "Employee ID (e.g. 'EMP003')"},
                    "days": {"type": "integer", "description": "Lookback window in days (default: 14)"},
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "destinations_for_employee",
            "description": "List all destinations an employee uploaded data to over a time window, including upload counts, MB, and whether the destination is risky.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "description": "Employee ID (e.g. 'EMP014')"},
                    "days": {"type": "integer", "description": "Lookback window in days (default: 30)"},
                },
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "usb_activity",
            "description": "Retrieve anomalous USB storage device events, bulk mass-storage file transfers, and associated risk scores across all employees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback window in days (default: 30)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_cases",
            "description": "List SOC incident cases filtered by status ('open', 'New', 'Investigating', 'Resolved', 'Critical', or 'all').",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "New", "Investigating", "Resolved", "Critical", "all"],
                        "description": "Case status filter ('open' matches New or Investigating)",
                    },
                },
                "required": [],
            },
        },
    },
]
