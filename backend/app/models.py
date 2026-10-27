from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text, ForeignKey, JSON, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class User(Base):
    """User accounts for SOC analysts and administrators."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=True)
    role = Column(String(30), default="analyst", nullable=False)  # "admin" | "analyst" | "viewer"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)



class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True)          # e.g. "EMP007"
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)

    risk_records = relationship("RiskRecord", back_populates="employee")


class RiskRecord(Base):
    """One row per employee per day — the output of the full detection
    pipeline (metadata -> profiling -> ensemble detection -> risk
    scoring -> explanation)."""
    __tablename__ = "risk_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # Individual model outputs (each roughly 0-1, higher = more anomalous)
    isolation_forest_score = Column(Float, default=0.0)
    autoencoder_score = Column(Float, default=0.0)
    lstm_score = Column(Float, default=0.0)
    xgboost_score = Column(Float, default=0.0)

    # Dynamic Risk Engine output
    risk_score = Column(Float, nullable=False)      # 0-100
    risk_tier = Column(String, nullable=False)       # Low/Medium/High/Critical
    rule_flags = Column(JSON, default=list)          # e.g. ["off_hours_upload", "split_transfer"]

    # AI Investigation Agent output
    explanation = Column(Text, nullable=True)
    agent_source = Column(String, default="template")  # "template" | "ollama"

    # Raw daily feature snapshot (kept for the dashboard's timeline/detail view)
    features = Column(JSON, default=dict)

    is_ground_truth_anomaly = Column(Integer, default=0)  # demo-only labelling
    scenario = Column(String, nullable=True)               # demo-only labelling

    employee = relationship("Employee", back_populates="risk_records")


class GraphEdge(Base):
    """Adjacency-list style storage for the threat graph (employee <->
    destination / device / geo relationships), rendered client-side
    with Cytoscape.js. Using a plain Postgres table instead of Neo4j
    keeps the stack simple at prototype scale."""
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    src = Column(String, nullable=False, index=True)   # node id, e.g. "EMP007"
    dst = Column(String, nullable=False, index=True)   # node id, e.g. "dest:personal-gdrive"
    src_type = Column(String, nullable=False)          # "employee" | "destination" | "device" | "geo"
    dst_type = Column(String, nullable=False)
    edge_type = Column(String, nullable=False)         # "uploaded_to" | "used_device" | "logged_in_from"
    weight = Column(Float, default=1.0)                # e.g. total MB, or event count
    risk_tier = Column(String, default="Low")          # highest tier seen on this edge
    last_seen = Column(DateTime, default=datetime.utcnow)


class RawMetadataEvent(Base):
    """Optional durable log of raw metadata events after they've been
    drained from the Redis queue — content-free by construction (no
    file contents or paths with identifying detail are ever stored,
    only counts/sizes/destinations/flags)."""
    __tablename__ = "raw_metadata_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)   # login, usb, file_copy, upload, process, network, privilege
    timestamp = Column(DateTime, nullable=False)
    payload = Column(JSON, default=dict)
    source = Column(String, default="simulator")  # "simulator" | "live"


class AnalystFeedback(Base):
    """Analyst review feedback for a given employee-day alert.
    Survives pipeline re-runs because it lives in its own table keyed
    by (employee_id, date) with no foreign key to risk_records."""
    __tablename__ = "analyst_feedback"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_analyst_feedback_emp_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    label = Column(String, nullable=False)  # "threat" | "false_positive"
    analyst = Column(String, default="analyst", nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlertCase(Base):
    """Case management for an employee-day alert.
    Survives pipeline re-runs because it lives in its own table keyed
    by (employee_id, date) with no foreign key to risk_records."""
    __tablename__ = "alert_cases"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_alert_cases_emp_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(String, default="New", nullable=False)  # "New" | "Investigating" | "Resolved"
    assignee = Column(String, nullable=True)
    priority = Column(String, nullable=True)  # "Critical" | "High" | "Medium" | "Low"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CaseNote(Base):
    """Analyst notes attached to an alert case (employee_id, date).
    Survives pipeline re-runs."""
    __tablename__ = "case_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    author = Column(String, default="analyst", nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AssistantAuditLog(Base):
    """Audit log of analyst chat interactions with the SOC Assistant.
    Tracks question asked, tools called, execution mode, and timestamp."""
    __tablename__ = "assistant_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    question = Column(Text, nullable=False)
    tools_called = Column(JSON, default=list, nullable=False)
    mode = Column(String, nullable=False)  # "ollama" | "fallback"


class EvaluationRun(Base):
    """Stores benchmark evaluation results on real/synthetic datasets (e.g. CERT r4.2)."""
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    dataset = Column(String, nullable=False)  # e.g. "CERT r4.2"
    n_users = Column(Integer, nullable=False)
    n_days = Column(Integer, nullable=False)
    config = Column(JSON, default=dict, nullable=False)
    metrics = Column(JSON, default=dict, nullable=False)
    curves = Column(JSON, default=dict, nullable=False)


