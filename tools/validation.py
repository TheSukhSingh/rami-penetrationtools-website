from tools.policies import get_effective_policy
from tools.models import ToolConfigFieldType 
from tools.policies import get_effective_policy

class ValidationError(Exception):
    pass

def validate_tool_config(tool_slug: str, config: dict):
    pol = get_effective_policy(tool_slug)
    fields = {f["name"]: f for f in pol.get("schema_fields", [])}
    for name, fld in fields.items():
        if not fld.get("visible", True):
            continue
        required = fld.get("required", False)
        v = config.get(name, fld.get("default"))
        if required and (v is None or v == ""):
            raise ValidationError(f"'{name}' is required.")

        ftype = fld.get("type")
        cons  = fld.get("constraints", {}) or {}
        if v is None:
            continue

        if ftype == "integer":
            try: v = int(v)
            except Exception: raise ValidationError(f"'{name}' must be an integer.")
            lo, hi = cons.get("min"), cons.get("max")
            if lo is not None and v < lo: raise ValidationError(f"'{name}' must be ≥ {lo}.")
            if hi is not None and v > hi: raise ValidationError(f"'{name}' must be ≤ {hi}.")
            config[name] = v

        elif ftype == "float":
            try: v = float(v)
            except Exception: raise ValidationError(f"'{name}' must be a number.")
            lo, hi = cons.get("min"), cons.get("max")
            if lo is not None and v < lo: raise ValidationError(f"'{name}' must be ≥ {lo}.")
            if hi is not None and v > hi: raise ValidationError(f"'{name}' must be ≤ {hi}.")
            config[name] = v

        elif ftype in ("select","multiselect"):
            choices = fld.get("choices") or []
            allowed = { (c["value"] if isinstance(c, dict) else c) for c in choices }
            if ftype == "select":
                if v not in allowed:
                    raise ValidationError(f"'{name}' must be one of: {sorted(allowed)}.")
            else:
                vals = v if isinstance(v, list) else [v]
                bad = [x for x in vals if x not in allowed]
                if bad:
                    raise ValidationError(f"'{name}' has invalid values: {bad}.")
                config[name] = vals
    return config

def validate_step_input(tool, manifest: dict) -> list[str]:
    errs = []
    mf = manifest or {}

    for f in (tool.config_fields or []):
        if not f.visible:
            continue

        val = mf.get(f.name, f.default)

        if f.required and (val is None or (isinstance(val, str) and not val.strip())):
            errs.append(f"'{f.label}' is required")
            continue

        if f.type in (ToolConfigFieldType.integer, ToolConfigFieldType.float) and val is not None:
            try:
                _ = float(val) if f.type is ToolConfigFieldType.float else int(str(val), 10)
            except Exception:
                kind = "float" if f.type is ToolConfigFieldType.float else "integer"
                errs.append(f"'{f.label}' must be a {kind}")

        if f.type is ToolConfigFieldType.boolean and val is not None:
            if isinstance(val, bool):
                pass
            elif isinstance(val, str) and val.lower() in ("true", "false", "1", "0", "yes", "no"):
                pass
            else:
                errs.append(f"'{f.label}' must be true/false")

        if f.type in (ToolConfigFieldType.select, ToolConfigFieldType.multiselect) and f.choices:
            allowed = {c["value"] for c in (f.choices or [])}
            if f.type is ToolConfigFieldType.select:
                if val is not None and val not in allowed:
                    errs.append(f"'{f.label}' must be one of {sorted(allowed)}")
            else:
                vals = val if isinstance(val, list) else ([val] if val is not None else [])
                bad = [v for v in vals if v not in allowed]
                if bad:
                    errs.append(f"'{f.label}' has invalid values: {bad}")

    if mf.get("input_method") == "manual" and not (mf.get("value") or "").strip():
        errs.append("Provide a value or choose File input")
    if mf.get("input_method") == "file" and not (mf.get("file_path") or "").strip():
        errs.append("Select an input file when 'File' is chosen")

    return errs
