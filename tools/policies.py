from __future__ import annotations
from functools import lru_cache
from typing import Dict, Any, Optional
from extensions import db
from tools.models import Tool, ToolConfigField, ToolConfigFieldType, ToolConfigFieldOverlay
from copy import deepcopy
from sqlalchemy.orm import selectinload

DEFAULT_INPUT   = {"accepts": [], "max_targets": 50, "file_max_bytes": 100_000}
DEFAULT_IO      = {"consumes": [], "emits": []}
DEFAULT_BIN     = {"names": []}

BASELINE = {
    "subfinder": {
        "input_policy": {"accepts": ["domains"], "max_targets": 50, "file_max_bytes": 200_000},
        "binaries": {"names": ["subfinder", "subfinder.exe"]},
        "runtime_constraints": {
            "threads":   {"type": "integer", "min": 1, "max": 100, "default": 10},
            "timeout_s": {"type": "integer", "min": 5, "max": 300, "default": 60},
            "all_sources": {"type": "boolean", "default": False},
            "silent":      {"type": "boolean", "default": True},
        },
        "schema_fields": [
            {"name":"threads","label":"Threads","type":"integer","required":False,"order_index":10,"visible":True,"help_text":"Worker threads"},
            {"name":"timeout_s","label":"Timeout (s)","type":"integer","required":False,"order_index":20,"visible":True},
            {"name":"all_sources","label":"Use all sources","type":"boolean","required":False,"order_index":30,"visible":True},
            {"name":"silent","label":"Silent output","type":"boolean","required":False,"order_index":40,"visible":True, "default": True},
        ],
    },
    # add other tools here similarly…
}

def _clamp_num(v, lo, hi):
    try:
        fv = float(v)
    except Exception:
        return None
    if lo is not None and fv < lo: fv = lo
    if hi is not None and fv > hi: fv = hi
    return int(fv) if isinstance(v, int) or (isinstance(lo, int) and isinstance(hi, int)) else fv

def _merge_constraints(base_c, ov_c):
    if not ov_c: return base_c or {}
    base_c = base_c or {}
    eff = dict(base_c)
    if "min" in ov_c and ov_c["min"] is not None:
        eff["min"] = max(base_c.get("min", ov_c["min"]), ov_c["min"])
    if "max" in ov_c and ov_c["max"] is not None:
        eff["max"] = min(base_c.get("max", ov_c["max"]), ov_c["max"])
    # allow other keys like regex/max_length to override only if present
    for k in ("regex","max_length"):
        if k in ov_c and ov_c[k] is not None:
            eff[k] = ov_c[k]
    # keep sanity: min <= max
    if "min" in eff and "max" in eff and eff["min"] is not None and eff["max"] is not None:
        eff["min"] = min(eff["min"], eff["max"])
    return eff

def _subset_choices(base_choices, ov_choices):
    if not ov_choices: return base_choices
    if not base_choices: return ov_choices  # if baseline had none, we accept overlay as-is
    base_vals = { (c.get("value") if isinstance(c, dict) else c) for c in base_choices }
    out = []
    for c in ov_choices:
        v = c.get("value") if isinstance(c, dict) else c
        if v in base_vals:
            out.append(c)
    return out

def _field_map(tool: Tool) -> Dict[str, ToolConfigField]:
    return {f.name: f for f in (tool.config_fields or [])}

@lru_cache(maxsize=256)
def get_effective_policy(tool_slug: str) -> dict:
    base = deepcopy(BASELINE.get(tool_slug) or {})
    # load tool + fields + overlay
    tool = (Tool.query.options(
                selectinload(Tool.config_fields).selectinload(ToolConfigField.overlay)
            )
            .filter_by(slug=tool_slug, enabled=True)
            .first())
    if not tool:
        return base or {}

    # Start with baseline schema_fields; index by name for quick merge
    base_fields_by_name = {f["name"]: deepcopy(f) for f in (base.get("schema_fields") or [])}

    schema_fields = []
    runtime_constraints = deepcopy(base.get("runtime_constraints") or {})
    input_policy = deepcopy(base.get("input_policy") or {})
    binaries = deepcopy(base.get("binaries") or {})

    # Merge each DB field against baseline definition (if baseline absent, still expose DB field safely)
    for f in tool.config_fields:  # ToolConfigField rows
        eff = base_fields_by_name.get(f.name, {})
        # start from DB baseline row values
        eff.setdefault("name", f.name)
        eff.setdefault("label", f.label)
        eff.setdefault("type", f.type.value)
        eff.setdefault("required", f.required)
        eff.setdefault("help_text", f.help_text)
        eff.setdefault("placeholder", f.placeholder)
        eff.setdefault("default", f.default)
        eff.setdefault("choices", f.choices)
        eff.setdefault("order_index", f.order_index)
        eff.setdefault("advanced", f.advanced)
        eff.setdefault("visible", f.visible)
        eff.setdefault("group", f.group)
        eff.setdefault("constraints", f.constraints or {})

        # apply overlay (if present)
        ov = f.overlay
        if ov:
            if ov.visible is not None:       eff["visible"] = ov.visible
            if ov.required is not None:      eff["required"] = ov.required
            if ov.help_text is not None:     eff["help_text"] = ov.help_text
            if ov.placeholder is not None:   eff["placeholder"] = ov.placeholder
            if ov.order_index is not None:   eff["order_index"] = ov.order_index
            if ov.advanced is not None:      eff["advanced"]  = ov.advanced
            if ov.default is not None:       eff["default"] = ov.default
            if ov.choices is not None:       eff["choices"] = _subset_choices(eff.get("choices"), ov.choices)
            if ov.constraints is not None:   eff["constraints"] = _merge_constraints(eff.get("constraints"), ov.constraints)

        schema_fields.append(eff)

        # keep runtime constraints in sync for numeric/bounded fields
        rc = runtime_constraints.get(f.name) or {}
        if eff["type"] in ("integer","float"):
            c = eff.get("constraints") or {}
            lo, hi = c.get("min"), c.get("max")
            default = eff.get("default")
            if default is not None:
                default = _clamp_num(default, lo, hi)
            runtime_constraints[f.name] = {
                "type": eff["type"],
                "min": lo, "max": hi,
                "default": default if default is not None else rc.get("default"),
            }
        else:
            # booleans/strings/selects — carry default through
            runtime_constraints[f.name] = {
                "type": eff["type"],
                "default": eff.get("default", rc.get("default")),
                "choices": eff.get("choices"),
            }

    schema_fields.sort(key=lambda x: (x.get("group") or "", x.get("order_index") or 0, x["name"]))

    return {
        "input_policy": input_policy,
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
