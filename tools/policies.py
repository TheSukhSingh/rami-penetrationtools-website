# tools/policies.py
from __future__ import annotations
from functools import lru_cache
from typing import Dict, Any, Optional
from extensions import db
from tools.models import Tool, ToolConfigField, ToolConfigFieldType

DEFAULT_INPUT   = {"accepts": [], "max_targets": 50, "file_max_bytes": 100_000}
DEFAULT_IO      = {"consumes": [], "emits": []}
DEFAULT_BIN     = {"names": []}

def _field_map(tool: Tool) -> Dict[str, ToolConfigField]:
    return {f.name: f for f in (tool.config_fields or [])}

@lru_cache(maxsize=256)
def get_effective_policy(tool_slug: str) -> Dict[str, Any]:
    tool: Tool = Tool.query.filter_by(slug=tool_slug, enabled=True).first()
    if not tool:
        return {
            "input_policy": DEFAULT_INPUT,
            "io_policy": DEFAULT_IO,
            "binaries": DEFAULT_BIN,
            "runtime_constraints": {},
            "schema_fields": [],
        }

    fm = _field_map(tool)

    # Visible schema fields for FE forms
    schema_fields = [f.to_dict() for f in fm.values() if f.visible]

    # Runtime constraints (per-field), derived from visible fields
    runtime_constraints: Dict[str, Dict[str, Any]] = {}
    for f in fm.values():
        if not f.visible:
            continue
        if f.type in (ToolConfigFieldType.INTEGER, ToolConfigFieldType.FLOAT):
            runtime_constraints[f.name] = (f.constraints or {})

    # Hidden policy blobs
    def j(name: str, default: dict) -> dict:
        fld = fm.get(name)
        if not fld or not isinstance(fld.default, dict):
            return default
        return {**default, **fld.default}

    input_policy = j("__policy.input", DEFAULT_INPUT)
    io_policy    = j("__policy.io",    DEFAULT_IO)
    binaries     = j("__policy.binaries", DEFAULT_BIN)

    return {
        "input_policy": input_policy,
        "io_policy": io_policy,
        "binaries": binaries,
        "runtime_constraints": runtime_constraints,
        "schema_fields": schema_fields,
    }

def clamp_from_constraints(options: dict, name: str, constraints: Optional[dict], default: Any=None, *, kind="int"):
    from tools.alltools.tools._common import ValidationError
    raw = options.get(name, default)
    if raw is None:
        return default
    try:
        val = int(raw) if kind == "int" else float(raw)
    except Exception:
        raise ValidationError(f"{name} must be a {kind}", "INVALID_PARAMS", f"got {raw!r}")
    if constraints:
        mn = constraints.get("min"); mx = constraints.get("max")
        if mn is not None and val < mn:
            raise ValidationError(f"{name} must be ≥ {mn}", "INVALID_PARAMS", f"got {val}")
        if mx is not None and val > mx:
            raise ValidationError(f"{name} must be ≤ {mx}", "INVALID_PARAMS", f"got {val}")
    return val
