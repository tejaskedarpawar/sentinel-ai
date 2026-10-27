"""
Notifications status and test router for Sentinel AI.
Endpoints:
  - GET /api/notifications/status
  - POST /api/notifications/test
"""
from fastapi import APIRouter
from app.notifiers import get_notification_channels_status, send_test_notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/status")
def notifications_status():
    """Return status of configured outbound notification channels (no credentials or secrets exposed)."""
    return get_notification_channels_status()


@router.post("/test")
def notifications_test():
    """Trigger a simulated test notification dispatch to all configured channels."""
    return send_test_notification()
