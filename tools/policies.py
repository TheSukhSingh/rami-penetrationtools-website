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

# ---- Global, source-of-truth specs (Task 1) ----
BUCKETS = (
    "domains", "hosts", "ips", "ports", "services",
    "urls", "endpoints", "params",
    "tech_stack", "vulns", "exploit_results", "screenshots",
)

EXECUTION_ORDER = [
    # discovery → validation → enrichment → prep → scanning → exploitation → reporting
    "discovery", "validation", "enrichment", "prep", "scanning", "exploitation", "reporting",
]

WORDLIST_TIERS = ["small", "medium", "large", "ultra"]

# Compatibility (consumes/emits) for each tool slug we ship
# NOTE: Keep slugs in sync with your Tool rows + adapter filenames.
IO_BASELINE = {
    # ---- Discovery / Recon ----
    "subfinder":         {"consumes": ["domains"],                      "emits": ["domains"]},
    "github-subdomains": {"consumes": ["domains"],                      "emits": ["domains"]},
    "crt.sh":            {"consumes": ["domains"],                      "emits": ["domains"]},
    "theharvester":      {"consumes": ["domains"],                      "emits": ["domains"]},

    # ---- Validation / Surface ----
    "dnsx":              {"consumes": ["domains","hosts"],              "emits": ["domains","ips"]},
    "naabu":             {"consumes": ["hosts","ips","domains"],        "emits": ["services","ports"]},
    "services-to-urls":  {"consumes": ["services"],                     "emits": ["urls"]},
    "httpx":             {"consumes": ["urls","hosts","domains"],       "emits": ["urls"]},

    # ---- Enrichment / Crawl / Params ----
    "katana":            {"consumes": ["urls","domains"],               "emits": ["urls","endpoints"]},
    "gospider":          {"consumes": ["urls","domains"],               "emits": ["urls"]},
    "hakrawler":         {"consumes": ["urls","domains"],               "emits": ["urls"]},
    "gau":               {"consumes": ["domains","hosts"],              "emits": ["urls"]},
    "linkfinder":        {"consumes": ["urls"],                         "emits": ["endpoints"]},
    "paramspider":       {"consumes": ["urls","domains"],               "emits": ["params"]},
    "arjun":             {"consumes": ["urls","endpoints"],             "emits": ["params"]},

    # ---- Tech / WAF / CMS ----
    "whatweb":           {"consumes": ["urls"],                         "emits": ["tech_stack"]},
    "wafw00f":           {"consumes": ["urls"],                         "emits": ["tech_stack"]},
    "retire-js":         {"consumes": ["urls"],                         "emits": ["tech_stack","vulns"]},
    "wpscan":            {"consumes": ["urls"],                         "emits": ["tech_stack","vulns"]},

    # ---- Scanners ----
    "nuclei":            {"consumes": ["urls"],                         "emits": ["vulns"]},
    "nikto":             {"consumes": ["urls"],                         "emits": ["vulns"]},
    "zap":               {"consumes": ["urls"],                         "emits": ["vulns","endpoints","params"]},
    "dalfox":            {"consumes": ["urls","params","endpoints"],    "emits": ["vulns"]},
    "xsstrike":          {"consumes": ["urls","params"],                "emits": ["vulns"]},
    "s3scanner":         {"consumes": ["urls","domains"],               "emits": ["vulns"]},

    # ---- Fuzz / Brute ----
    "ffuf":              {"consumes": ["urls","hosts","domains"],       "emits": ["endpoints","params"]},
    "gobuster":          {"consumes": ["urls","hosts","domains"],       "emits": ["endpoints"]},

    # ---- Exploitation / Creds ----
    "hydra":             {"consumes": ["services","urls"],              "emits": ["exploit_results"]},
    "sqlmap":            {"consumes": ["urls","params"],                "emits": ["exploit_results","vulns"]},
    "commix":            {"consumes": ["urls","params"],                "emits": ["exploit_results","vulns"]},
    "dotdotpwn":         {"consumes": ["urls","endpoints"],             "emits": ["exploit_results","vulns"]},
    "fuxploider":        {"consumes": ["urls","endpoints"],             "emits": ["exploit_results"]},
    "ssrfmap":           {"consumes": ["urls","params"],                "emits": ["exploit_results","domains","ips"]},

    # ---- Evidence / Reporting ----
    "gowitness":         {"consumes": ["urls"],                         "emits": ["screenshots"]},
    "jwt-crack":         {"consumes": ["endpoints","urls"],             "emits": ["exploit_results"]},
    "john":              {"consumes": ["endpoints","urls"],             "emits": ["exploit_results"]},
    "qlgraph":           {"consumes": ["urls","endpoints","vulns"],     "emits": []},
    "report-collate": {
        "consumes": ["domains","ips","urls","endpoints","params","services","tech_stack","vulns","exploit_results","screenshots"],
        "emits": []
    },
}

def get_global_specs() -> dict:
    """Expose global specs to FE (buckets, exec order, wordlists)."""
    return {
        "buckets": BUCKETS,
        "execution_order": EXECUTION_ORDER,
        "wordlist_tiers": WORDLIST_TIERS,
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
    """
    Build the effective policy for a tool by layering, in order:
      1) Code BASELINE (defaults)
      2) DB ToolConfigField rows (+ per-field overlay)
      3) DB meta_info.policy_overrides (input_policy, binaries, runtime_constraints, io_policy, wordlist_default)

    Returns a dict with: input_policy, binaries, runtime_constraints, schema_fields, io_policy
    """
    base = deepcopy(BASELINE.get(tool_slug) or {})

    # If tool is disabled or absent, fall back to baseline + ensure io_policy is present
    tool = (
        Tool.query.options(
            selectinload(Tool.config_fields).selectinload(ToolConfigField.overlay)
        )
        .filter_by(slug=tool_slug, enabled=True)
        .first()
    )
    if not tool:
        # Guarantee io_policy exists for FE even without a DB row
        if "io_policy" not in base:
            base["io_policy"] = deepcopy(IO_BASELINE.get(tool_slug) or DEFAULT_IO)
        return base

    # ---- Start with baseline fields, indexed by name for merging ----
    base_fields_by_name = {f["name"]: deepcopy(f) for f in (base.get("schema_fields") or [])}

    schema_fields: list[dict] = []
    runtime_constraints: dict = deepcopy(base.get("runtime_constraints") or {})
    input_policy: dict = deepcopy(base.get("input_policy") or DEFAULT_INPUT)
    binaries: dict = deepcopy(base.get("binaries") or DEFAULT_BIN)

    # ---- Merge DB ToolConfigField rows onto baseline field defs ----
    for f in (tool.config_fields or []):
        eff = deepcopy(base_fields_by_name.get(f.name, {}))

        # seed with DB row values (acts as a local baseline for this field)
        eff.setdefault("name", f.name)
        eff.setdefault("label", f.label)
        eff.setdefault("type", f.type.value)                  # "integer" | "float" | "boolean" | "string" | "select" ...
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

        # apply per-field overlay (if present)
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
        if eff["type"] in ("integer", "float"):
            c  = eff.get("constraints") or {}
            lo = c.get("min"); hi = c.get("max")
            default = eff.get("default")
            if default is not None:
                default = _clamp_num(default, lo, hi)
            runtime_constraints[f.name] = {
                "type": eff["type"],
                "min": lo, "max": hi,
                "default": default if default is not None else rc.get("default"),
            }
        else:
            # booleans/strings/selects — carry default/choices through
            runtime_constraints[f.name] = {
                "type": eff["type"],
                "default": eff.get("default", rc.get("default")),
                "choices": eff.get("choices"),
            }

    # ---- Add any baseline-only fields that DB doesn't define ----
    existing = {sf["name"] for sf in schema_fields}
    for name, bf in base_fields_by_name.items():
        if name in existing:
            continue
        eff = deepcopy(bf)
        schema_fields.append(eff)

        # keep runtime constraints consistent for baseline-only fields too
        t  = eff.get("type")
        rc = runtime_constraints.get(name) or {}
        if t in ("integer", "float"):
            c  = eff.get("constraints") or {}
            lo = c.get("min"); hi = c.get("max")
            default = eff.get("default")
            if default is not None:
                default = _clamp_num(default, lo, hi)
            runtime_constraints[name] = {
                "type": t,
                "min": lo, "max": hi,
                "default": default if default is not None else rc.get("default"),
            }
        else:
            runtime_constraints[name] = {
                "type": t,
                "default": eff.get("default", rc.get("default")),
                "choices": eff.get("choices"),
            }

    # stable/grouped ordering for FE
    schema_fields.sort(key=lambda x: (x.get("group") or "", x.get("order_index") or 0, x["name"]))

    # ---- Admin-level policy overrides from DB meta_info ----
    meta = tool.meta_info or {}
    ov   = meta.get("policy_overrides") or {}

    # input_policy overlay (accepts / max_targets / file_max_bytes)
    if isinstance(ov.get("input_policy"), dict):
        input_policy.update({k: v for k, v in ov["input_policy"].items() if v is not None})

    # binaries overlay (names, custom paths, etc.)
    if isinstance(ov.get("binaries"), dict):
        b = ov["binaries"]
        if isinstance(b.get("names"), list):
            # union-safe merge of binary names
            names = list({*binaries.get("names", []), *b["names"]})
            binaries["names"] = names
        for k, v in b.items():
            if k == "names":
                continue
            binaries[k] = v

    # runtime_constraints overlay per field (min/max/regex/max_length)
    if isinstance(ov.get("runtime_constraints"), dict):
        for fname, c in ov["runtime_constraints"].items():
            base_c = runtime_constraints.get(fname) or {}
            if isinstance(c, dict):
                runtime_constraints[fname] = _merge_constraints(base_c, c)

    # ---- Compute IO policy + apply admin overlay ----
    io_policy = deepcopy(base.get("io_policy") or IO_BASELINE.get(tool_slug) or DEFAULT_IO)

    # io_policy overlay (typed buckets: consumes/emits)
    io_ov = ov.get("io_policy") or {}
    if isinstance(io_ov.get("consumes"), list):
        io_policy["consumes"] = [b for b in io_ov["consumes"] if b in BUCKETS]
    if isinstance(io_ov.get("emits"), list):
        io_policy["emits"] = [b for b in io_ov["emits"] if b in BUCKETS]

    # Optional: default wordlist tier hint per tool (FE can use it)
    wl = ov.get("wordlist_default")
    if wl in WORDLIST_TIERS:
        runtime_constraints.setdefault("_hints", {})["wordlist_default"] = wl

    return {
        "input_policy": input_policy,
        "binaries": binaries,
        "runtime_constraints": runtime_constraints,
        "schema_fields": schema_fields,
        "io_policy": io_policy,
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
