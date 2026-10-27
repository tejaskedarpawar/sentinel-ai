"""
SSE (Server-Sent Events) streaming router for real-time alert delivery.
Endpoint: GET /api/stream/alerts
"""
import asyncio
import json
import logging
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from app.config import settings
from app.notifiers import TIER_RANKS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["stream"])


async def alert_event_generator(request: Request, min_tier: str | None = None):
    """
    Subscribes to Redis pub/sub channel 'sentinel:alerts' and yields SSE frames.
    Sends a 15-second heartbeat comment ': keepalive\\n\\n' when idle.
    Cleans up Redis pubsub connections on client disconnect.
    """
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis_conn.pubsub()
    await pubsub.subscribe(settings.alerts_channel)

    min_rank = TIER_RANKS.get(min_tier, 0) if min_tier else 0
    loop = asyncio.get_event_loop()
    last_heartbeat = loop.time()

    try:
        # Initial greeting / connection frame
        yield f"event: open\ndata: {json.dumps({'status': 'connected', 'channel': settings.alerts_channel})}\n\n"

        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break

            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except (asyncio.CancelledError, GeneratorExit):
                break
            except Exception as exc:
                logger.warning(f"Redis get_message error: {exc}")
                await asyncio.sleep(1.0)
                continue

            now = loop.time()

            if msg and msg.get("type") == "message":
                raw_data = msg.get("data")
                if raw_data:
                    try:
                        alert = json.loads(raw_data)
                        tier = alert.get("risk_tier", "High")
                        if not (min_rank and TIER_RANKS.get(tier, 0) < min_rank):
                            yield f"data: {json.dumps(alert)}\n\n"
                    except json.JSONDecodeError:
                        yield f"data: {raw_data}\n\n"
                    last_heartbeat = now

            if now - last_heartbeat >= 15.0:
                yield ": keepalive\n\n"
                last_heartbeat = now

    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        try:
            await pubsub.unsubscribe(settings.alerts_channel)
            await pubsub.close()
            await redis_conn.close()
        except Exception:
            pass


@router.get("/alerts")
async def stream_alerts(
    request: Request,
    min_tier: str | None = Query(None, description="Optional minimum tier: High or Critical"),
):
    """
    Real-time Server-Sent Events (SSE) alert stream.
    Streams High and Critical alerts as they are generated or replayed.
    Sends a ': keepalive\\n\\n' comment every 15 seconds when idle.
    """
    return StreamingResponse(
        alert_event_generator(request, min_tier=min_tier),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
