from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


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
