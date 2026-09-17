from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GraphEdge
from app.graph import graph_to_cytoscape

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
def get_graph(db: Session = Depends(get_db)):
    """Employee <-> destination relationships shaped for Cytoscape.js
    (elements list of {data: {...}} node/edge objects)."""
    edges = db.query(GraphEdge).all()
    return graph_to_cytoscape(edges)
