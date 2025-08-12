"""
Tiny validation helpers (dependency-free). For larger/complex inputs, swap to Marshmallow/Pydantic later.
"""
from typing import Any, Dict, Iterable
from admin.errors import Unprocessable

def require_fields(data: Dict[str, Any], required: Iterable[str]) -> None:
    missing = [k for k in required if k not in data or data[k] in (None, "")]
    if missing:
        raise Unprocessable("Missing required fields", details={"fields": missing})

def coerce_int(data: Dict[str, Any], key: str) -> int:
    try:
        return int(data[key])
    except Exception:
        raise Unprocessable(f"'{key}' must be an integer")

def coerce_bool(data: Dict[str, Any], key: str) -> bool:
    v = data.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        if v.lower() in ("true", "1", "yes"): return True
        if v.lower() in ("false", "0", "no"): return False
    raise Unprocessable(f"'{key}' must be boolean")

def coerce_str(data: Dict[str, Any], key: str, *, min_len: int = 0, max_len: int = 255) -> str:
    v = data.get(key, "")
    if not isinstance(v, str):
        raise Unprocessable(f"'{key}' must be string")
    if len(v) < min_len:
        raise Unprocessable(f"'{key}' must be at least {min_len} chars")
    if len(v) > max_len:
        raise Unprocessable(f"'{key}' must be at most {max_len} chars")
    return v.strip()
