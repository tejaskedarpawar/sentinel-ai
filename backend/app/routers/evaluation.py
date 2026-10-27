from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import EvaluationRun

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/latest")
def get_latest_evaluation(db: Session = Depends(get_db)):
    """Fetch the most recent evaluation benchmark run."""
    run = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="No evaluation runs found")

    return {
        "id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "dataset": run.dataset,
        "n_users": run.n_users,
        "n_days": run.n_days,
        "config": run.config,
        "metrics": run.metrics,
        "curves": run.curves,
    }


@router.get("/runs")
def list_evaluation_runs(db: Session = Depends(get_db)):
    """List all historical evaluation runs."""
    runs = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).all()
    results = []
    for r in runs:
        models = r.metrics.get("models", {})
        ensemble_metrics = models.get("Sentinel AI Ensemble") or models.get("Ensemble", {})
        results.append({
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "dataset": r.dataset,
            "n_users": r.n_users,
            "n_days": r.n_days,
            "config": r.config,
            "metrics_summary": {
                "ensemble_roc_auc": ensemble_metrics.get("roc_auc"),
                "ensemble_pr_auc": ensemble_metrics.get("pr_auc"),
                "ensemble_f1": ensemble_metrics.get("f1"),
            },
        })
    return results
