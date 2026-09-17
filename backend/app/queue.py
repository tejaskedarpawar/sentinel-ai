"""
A deliberately simple Redis-backed queue standing in for Kafka/RabbitMQ
at this scale. The metadata collector(s) push raw events; the event
processing stage drains them in batches before handing off to the
behaviour-profiling engine. Using a plain Redis list keeps this legible
for a semester project while still being a real, independently-running
message broker (not an in-process Python list).
"""
import json
from datetime import datetime, date
import redis

from app.config import settings

_client = redis.from_url(settings.redis_url, decode_responses=True)


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    raise TypeError(f"Not JSON serialisable: {o!r}")


def push_event(event: dict, key: str = None) -> None:
    """Collector-side: enqueue one raw metadata event."""
    key = key or settings.redis_stream_key
    _client.rpush(key, json.dumps(event, default=_json_default))


def push_events(events: list[dict], key: str = None) -> int:
    """Collector-side: enqueue many events in one round trip."""
    key = key or settings.redis_stream_key
    if not events:
        return 0
    pipe = _client.pipeline()
    for e in events:
        pipe.rpush(key, json.dumps(e, default=_json_default))
    pipe.execute()
    return len(events)


def drain_events(key: str = None, batch_size: int = 5000) -> list[dict]:
    """Event-processing side: pop up to `batch_size` events currently
    queued and return them as dicts. Non-blocking — returns [] if the
    queue is empty."""
    key = key or settings.redis_stream_key
    pipe = _client.pipeline()
    pipe.lrange(key, 0, batch_size - 1)
    pipe.ltrim(key, batch_size, -1)
    raw, _ = pipe.execute()
    return [json.loads(r) for r in raw]


def queue_depth(key: str = None) -> int:
    key = key or settings.redis_stream_key
    return _client.llen(key)


def ping() -> bool:
    try:
        return _client.ping()
    except Exception:
        return False
