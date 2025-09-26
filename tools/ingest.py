# tools/ingest.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Iterable, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

from tools.policies import get_effective_policy
from tools.alltools.tools._common import (
    URL_RE, IPV4_RE, IPV6_RE, ValidationError
)

# ---------- small utilities ----------

def _stable_union(*iterables: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for it in iterables:
        for s in (it or []):
            s = (s or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
    return out

def _dedupe_stable(vals: List[str]) -> List[str]:
    return _stable_union(vals)

def _normalize_domain(d: str) -> str:
    s = (d or "").strip().lower()
    if s.startswith("*."):
        s = s[2:]
    # Trim leading/trailing dots/spaces
    return s.strip(" .")

def _normalize_host(h: str) -> str:
    # same as domain for now (you can evolve this later)
    return _normalize_domain(h)

def _normalize_url(u: str) -> str:
    s = (u or "").strip()
    if not s:
        return s
    try:
        sp = urlsplit(s)
        # lower netloc; drop fragment
        netloc = (sp.netloc or "").lower()
        return urlunsplit((sp.scheme, netloc, sp.path or "", sp.query or "", ""))
    except Exception:
        return s

def _categorize_lines_to_accepted(lines: List[str], accept_order: List[str]) -> Dict[str, List[str]]:
    """
    Heuristic: put each line into the first accepted bucket it clearly matches.
    Priority: urls -> domains -> hosts -> ips
    """
    buckets: Dict[str, List[str]] = {k: [] for k in accept_order}
    for raw in (lines or []):
        s = (raw or "").strip()
        if not s:
            continue
        # URL?
        if "urls" in accept_order and URL_RE.search(s):
            buckets["urls"].append(s); continue
        # IP?
        if "ips" in accept_order and (IPV4_RE.search(s) or IPV6_RE.search(s)):
            buckets["ips"].append(s); continue
        # Domain/host
        if "domains" in accept_order:
            buckets["domains"].append(s)
        elif "hosts" in accept_order:
            buckets["hosts"].append(s)
        else:
            # If none match, drop (or you could park in a 'raw' list)
            pass
    return buckets

def _apply_normalization(typed_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for k, vals in (typed_map or {}).items():
        if not vals:
            continue
        if k == "domains":
            out[k] = [_normalize_domain(v) for v in vals]
        elif k == "hosts":
            out[k] = [_normalize_host(v) for v in vals]
        elif k == "urls":
            out[k] = [_normalize_url(v) for v in vals]
        else:
            out[k] = [str(v).strip() for v in vals]
    return out

def _cap_map(typed_map: Dict[str, List[str]], cap: Optional[int]) -> Dict[str, List[str]]:
    if not cap or cap <= 0:
        return typed_map
    out: Dict[str, List[str]] = {}
    for k, vals in (typed_map or {}).items():
        if not vals:
            continue
        out[k] = vals[:cap]
    return out

# ---------- core ingest helpers ----------

def _get_policy_snapshot(step) -> dict:
    base_opts = ((step.input_manifest or {}).get("options") or {})
    snap = base_opts.get("_policy")
    return snap or {}

def get_policy_for_step(step, slug: str) -> dict:
    snap = _get_policy_snapshot(step)
    if snap:
        return snap
    # Fallback to DB if snapshot missing (rare)
    try:
        return get_effective_policy(slug)
    except Exception:
        # Minimal empty policy
        return {
            "input_policy": {"accepts": [], "max_targets": 50, "file_max_bytes": 100_000},
            "io_policy": {"consumes": [], "emits": []},
            "binaries": {"names": []},
            "runtime_constraints": {},
            "schema_fields": [],
        }

def determine_upstreams(run, step) -> List[int]:
    # If FE supplies explicit upstreams, honor them; else linear chain
    opts = ((step.input_manifest or {}).get("options") or {})
    explicit = opts.get("upstream")
    if isinstance(explicit, list) and all(isinstance(i, int) for i in explicit):
        return explicit
    if step.step_index > 0:
        return [step.step_index - 1]
    return []

def collect_upstream_typed(run, upstream_idxs: List[int], accept_keys: List[str]) -> Dict[str, List[str]]:
    store: Dict[str, List[str]] = {k: [] for k in accept_keys}
    for idx in upstream_idxs or []:
        prev = next((ps for ps in run.steps if ps.step_index == idx and ps.output_manifest), None)
        if not prev:
            continue
        outm = prev.output_manifest or {}
        for k in accept_keys:
            if isinstance(outm.get(k), list) and outm.get(k):
                store[k].extend([str(x).strip() for x in outm.get(k) if str(x).strip()])
    return store

def collect_local_inputs(step, accept_keys: List[str]) -> Dict[str, List[str]]:
    """
    Pulls manual 'value' and/or 'file_path' (server file) from the step's config,
    and drops them into accepted typed buckets heuristically.
    """
    cfg = step.input_manifest or {}
    node_opts = (cfg.get("options") or {})
    # manual
    manual_val = (cfg.get("value") or node_opts.get("value") or "").strip() if isinstance(cfg.get("value") or node_opts.get("value"), str) else ""
    manual_parts = []
    if manual_val:
        import re
        manual_parts = [p for p in re.split(r"[\s,]+", manual_val) if p]

    # file
    vals_from_file: List[str] = []
    im = (cfg.get("input_method") or node_opts.get("input_method") or "").lower()
    fpath = (cfg.get("file_path") or node_opts.get("file_path"))
    if im == "file" and fpath and os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                vals_from_file = [ln.strip() for ln in fh if ln.strip()]
        except Exception:
            vals_from_file = []

    # Heuristically bucketize into first matching accepted type
    local_map = {k: [] for k in accept_keys}
    local_detected = _categorize_lines_to_accepted(manual_parts, accept_keys)
    file_detected  = _categorize_lines_to_accepted(vals_from_file, accept_keys)

    for k in accept_keys:
        local_map[k].extend(local_detected.get(k, []))
        local_map[k].extend(file_detected.get(k, []))
    return local_map

def use_global_seed_if_empty(typed_map: Dict[str, List[str]], accept_keys: List[str], app_config: dict) -> Dict[str, List[str]]:
    if any(typed_map.get(k) for k in accept_keys):
        return typed_map
    seeds = (app_config or {}).get("GLOBAL_SEEDS") or {}
    if not isinstance(seeds, dict):
        return typed_map
    # prefer first accept key present in seeds
    for k in accept_keys:
        vals = seeds.get(k) or []
        if vals:
            typed_map[k] = [str(x).strip() for x in vals if str(x).strip()]
            break
    return typed_map

def _merge_maps(*maps: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    keys = set()
    for m in maps:
        keys.update((m or {}).keys())
    for k in keys:
        out[k] = _stable_union(*[(m or {}).get(k, []) for m in maps])
    return out

def materialize_inbox_if_needed(work_dir: Path, accept_order: List[str], typed_map: Dict[str, List[str]]) -> Tuple[Optional[str], Optional[str]]:
    """
    OPTIONAL: If you want adapters to read a file, write one list per first non-empty accepted key.
    Returns (input_method, file_path) or (None, None) if we skip file materialization.
    We keep this optional because your adapters can read injected typed lists directly.
    """
    for k in accept_order:
        vals = typed_map.get(k) or []
        if vals:
            inbox = work_dir / f"inbox_{k}.txt"
            lines = "\n".join(vals)
            inbox.write_text(lines, encoding="utf-8", errors="ignore")
            return "file", str(inbox)
    return None, None

# ---------- main entry point ----------

def build_inputs_for_step(run, step, step_dir: Path, app_config: dict, *, slug: str) -> dict:
    """
    Returns a ready 'options' dict for the adapter:
      - includes _policy snapshot, tool_slug, work_dir
      - injects typed arrays for accepted keys (normalized, deduped, capped)
      - OPTIONAL: set input_method/file_path if you want file-based ingestion
    """
    policy = get_policy_for_step(step, slug)
    ipol = (policy.get("input_policy") or {})
    accept_keys: List[str] = list(ipol.get("accepts") or [])
    # Sensible fallback if DB has not yet populated accepts for a tool
    if not accept_keys:
        accept_keys = ["domains", "hosts", "urls", "ips"]

    # 1) upstream typed
    ups = determine_upstreams(run, step)
    upstream_map = collect_upstream_typed(run, ups, accept_keys)

    # 2) local node inputs (manual/file)
    local_map = collect_local_inputs(step, accept_keys)

    # 3) merge upstream + local
    merged_map = _merge_maps(upstream_map, local_map)

    # 4) seeds if still empty
    merged_map = use_global_seed_if_empty(merged_map, accept_keys, app_config)

    # 5) normalize
    merged_map = _apply_normalization(merged_map)

    # 6) dedupe (stable)
    for k in list(merged_map.keys()):
        merged_map[k] = _dedupe_stable(merged_map[k])

    # 7) cap
    cap_n = ipol.get("max_targets", 50)
    merged_map = _cap_map(merged_map, cap_n)

    # 8) Assemble options for adapter (keep any explicit node fields)
    options: Dict[str, object] = {}
    # start with step.input_manifest and flatten "options" into top-level without overwriting explicit top-level
    if isinstance(step.input_manifest, dict):
        options.update(step.input_manifest)
        inner = step.input_manifest.get("options")
        if isinstance(inner, dict):
            for k, v in inner.items():
                options.setdefault(k, v)

    # Attach policy snapshot (prefer snapshot, else DB)
    options["_policy"] = policy
    options["tool_slug"] = slug
    options["work_dir"] = str(step_dir)

    # Inject typed arrays for accepted keys
    for k in accept_keys:
        vals = merged_map.get(k) or []
        if vals:
            options[k] = vals

    # OPTIONAL: Materialize a file if you want file-based ingestion:
    # (Adapters can also consume the injected typed arrays directly, so this is not mandatory.)
    im, fp = materialize_inbox_if_needed(step_dir, accept_keys, merged_map)
    if im and fp:
        options["input_method"] = im
        options["file_path"]   = fp
    else:
        # default to 'manual' only if there is an explicit 'value'; otherwise leave unset
        if options.get("value"):
            options.setdefault("input_method", "manual")

    return options
