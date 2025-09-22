# validation.py
from tools.models import ToolConfigFieldType  # add this import

def validate_step_input(tool, manifest: dict) -> list[str]:
    errs = []
    mf = manifest or {}

    for f in (tool.config_fields or []):
        if not f.visible:
            continue

        val = mf.get(f.name, f.default)

        # required field
        if f.required and (val is None or (isinstance(val, str) and not val.strip())):
            errs.append(f"'{f.label}' is required")
            continue

        # numeric
        if f.type in (ToolConfigFieldType.integer, ToolConfigFieldType.float) and val is not None:
            try:
                # just validate; adapters can cast
                _ = float(val) if f.type is ToolConfigFieldType.float else int(str(val), 10)
            except Exception:
                kind = "float" if f.type is ToolConfigFieldType.float else "integer"
                errs.append(f"'{f.label}' must be a {kind}")

        # boolean
        if f.type is ToolConfigFieldType.boolean and val is not None:
            if isinstance(val, bool):
                pass
            elif isinstance(val, str) and val.lower() in ("true", "false", "1", "0", "yes", "no"):
                pass
            else:
                errs.append(f"'{f.label}' must be true/false")

        # select / multiselect choices
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

    # cross-field checks
    if mf.get("input_method") == "manual" and not (mf.get("value") or "").strip():
        errs.append("Provide a value or choose File input")
    if mf.get("input_method") == "file" and not (mf.get("file_path") or "").strip():
        errs.append("Select an input file when 'File' is chosen")

    return errs
