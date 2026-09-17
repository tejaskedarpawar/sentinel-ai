"""
Threat Graph.

Models employee <-> destination / device / geo relationships as a
graph so an analyst can spot, e.g., several employees quietly using
the same unfamiliar destination. Built in-memory with NetworkX from
the same events + risk records the rest of the pipeline already
computed, then persisted as plain rows in the graph_edges Postgres
table (a simple adjacency list) — this is the "model relationships in
Postgres instead of standing up Neo4j" trade-off appropriate at
prototype scale; swap in Neo4j later only if graph queries get complex
enough to need it.
"""
from collections import defaultdict
import networkx as nx
from sqlalchemy.orm import Session

from app.models import GraphEdge

TIER_RANK = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


def build_graph(events: list[dict], risk_by_employee_day: dict) -> nx.DiGraph:
    """`risk_by_employee_day` maps (employee_id, date) -> risk_tier, so
    edges created on a day an employee was flagged inherit that tier."""
    edge_weight = defaultdict(float)
    edge_tier = defaultdict(lambda: "Low")

    for e in events:
        if e["event_type"] != "upload":
            continue
        emp = e["employee_id"]
        payload = e.get("payload", {})
        dest = payload.get("destination")
        if not dest:
            continue
        ts = e["timestamp"]
        day = ts.date() if hasattr(ts, "date") else ts
        tier = risk_by_employee_day.get((emp, day), "Low")

        dst_node = f"dest:{dest}"
        key = (emp, dst_node)
        edge_weight[key] += float(payload.get("size_mb", 0))
        if TIER_RANK[tier] > TIER_RANK[edge_tier[key]]:
            edge_tier[key] = tier

    g = nx.DiGraph()
    for (emp, dst_node), weight in edge_weight.items():
        g.add_node(emp, node_type="employee")
        g.add_node(dst_node, node_type="destination")
        g.add_edge(emp, dst_node, edge_type="uploaded_to",
                   weight=weight, risk_tier=edge_tier[(emp, dst_node)])

    return g


def persist_graph(db: Session, g: nx.MultiDiGraph) -> int:
    db.query(GraphEdge).delete()
    count = 0
    for u, v, data in g.edges(data=True):
        db.add(GraphEdge(
            src=u, dst=v,
            src_type=g.nodes[u].get("node_type", "employee"),
            dst_type=g.nodes[v].get("node_type", "destination"),
            edge_type=data.get("edge_type", "uploaded_to"),
            weight=data.get("weight", 1.0),
            risk_tier=data.get("risk_tier", "Low"),
        ))
        count += 1
    db.commit()
    return count


def graph_to_cytoscape(edges: list[GraphEdge]) -> dict:
    """Shapes GraphEdge rows into the {nodes, edges} elements list
    Cytoscape.js expects on the frontend."""
    node_ids, node_types = {}, {}
    for e in edges:
        node_ids[e.src] = e.src
        node_types[e.src] = e.src_type
        node_ids[e.dst] = e.dst
        node_types[e.dst] = e.dst_type

    nodes = [
        {"data": {"id": nid, "label": nid.split(":")[-1], "type": node_types[nid]}}
        for nid in node_ids
    ]
    links = [
        {
            "data": {
                "id": f"e{i}", "source": e.src, "target": e.dst,
                "weight": round(e.weight, 1), "risk_tier": e.risk_tier,
            }
        }
        for i, e in enumerate(edges)
    ]
    return {"nodes": nodes, "edges": links}
