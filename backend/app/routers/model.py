from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.detection.retrain import retrain_model, rescore_records, get_model_status

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/status")
def model_status(db: Session = Depends(get_db)):
    """Current model mode (pseudo|supervised), labels collected, last trained timestamp, and CV metrics."""
    return get_model_status(db)


@router.post("/retrain")
def retrain(db: Session = Depends(get_db)):
    """
    Retrains the XGBoost detector using analyst feedback, saves the model artifact,
    and re-scores all risk_records in place with updated risk scores, tiers, and rule flags.
    """
    retrain_res = retrain_model(db)
    if not retrain_res.get("success"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "reason": retrain_res.get("reason"),
                "n_labels": retrain_res.get("n_labels", 0),
                "counts": retrain_res.get("counts", {}),
            },
        )

    rescore_info = rescore_records(db, retrain_res["model"])

    return {
        "success": True,
        "message": "Model successfully retrained and risk records updated",
        "metadata": retrain_res["metadata"],
        "rescore": rescore_info,
    }
