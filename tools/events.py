from __future__ import annotations
import json, time
import redis
from flask import current_app

def _redis():
    url = current_app.config.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
    return redis.Redis.from_url(url, decode_responses=True)

def _chan(run_id: int) -> str:
    return f"wf:run:{int(run_id)}"

def publish_run_event(run_id: int, event_type: str, payload: dict):
    r = _redis()
    data = {
        "type": event_type,
        "run_id": int(run_id),
        "ts": int(time.time() * 1000),
        **(payload or {}),
    }
    r.publish(_chan(run_id), json.dumps(data))
