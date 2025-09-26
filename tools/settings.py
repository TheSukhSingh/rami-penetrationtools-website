from __future__ import annotations
import time
from typing import Any, Callable
from .models import AppSetting
from extensions import db

_CACHE: dict[str, tuple[float, str | None]] = {}
_TTL = 60.0  # seconds

def _now() -> float:
    return time.time()

def get_setting(key: str, default: Any = None, cast: Callable | None = None, ttl: float = _TTL) -> Any:
    t, val = _CACHE.get(key, (0.0, None))
    if _now() - t < ttl:
        raw = val
    else:
        rec = db.session.get(AppSetting, key)
        raw = rec.value if rec else None
        _CACHE[key] = (_now(), raw)
    if raw is None:
        return default
    if cast:
        try: return cast(raw)
        except Exception: return default
    return raw

def set_setting(key: str, value: Any) -> None:
    rec = db.session.get(AppSetting, key)
    if rec: rec.value = str(value)
    else:
        rec = AppSetting(key=key, value=str(value))
        db.session.add(rec)
    db.session.commit()
    _CACHE.pop(key, None)

def get_rate_limit(key: str, default: str = "5/minute") -> str:
    return str(get_setting(key, default, cast=str))
