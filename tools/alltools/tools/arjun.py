# tools/alltools/tools/arjun.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Dict, Any
import json
from urllib.parse import urlsplit, parse_qsl

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *
try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 1800

def _derive_endpoints(urls: List[str]) -> List[str]:
    eps, seen = [], set()
    for u in urls or []:
        try:
            p = urlsplit(u).path or "/"
            if p not in seen:
                seen.add(p); eps.append(p)
        except Exception:
            continue
    return eps

def _parse_arjun_json(blob: str) -> List[str]:
    """
    arjun -oJ prints JSON; formats vary:
      {"<url>": ["q","id",...]} OR {"<url>": {"parameters": ["q",...]}}
    This parser collects parameter names from both shapes across objects/lines.
    """
    params: List[str] = []
    seen = set()
    lines = [ln for ln in (blob or "").splitlines() if ln.strip()]
    for ln in lines:
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if isinstance(obj, dict):
            for _k, v in obj.items():
                arr = None
                if isinstance(v, dict) and "parameters" in v:
                    arr = v.get("parameters")
                elif isinstance(v, list):
                    arr = v
                if isinstance(arr, list):
                    for p in arr:
                        s = str(p).strip()
                        if s and s not in seen:
                            seen.add(s); params.append(s)
    return params

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "arjun")
    slug = options.get("tool_slug", "arjun")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("arjun", "arjun.exe")
    if not exe:
        return finalize("error", "arjun not installed", options, "arjun", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","endpoints"), cap=ipol.get("max_targets") or 5000)
    if not urls:
        raise ValidationError("Provide URL(s) or endpoints for arjun.", "INVALID_PARAMS", "no input")

    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=20, kind="int") or 20
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=20, kind="int") or 20
    method    = (options.get("method") or "GET").upper()

    # arjun runs per target; we ask for JSON on stdout
    all_out = []
    used_cmd = ""
    for u in urls:
        args = [exe, "-u", u, "-oJ", "-t", str(threads), "-m", method]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 120), cwd=work_dir)
        if out:
            all_out.append(out)

    raw = "\n".join(all_out)
    outfile = write_output_file(work_dir, "arjun_output.jsonl", raw or "")

    params = _parse_arjun_json(raw)
    endpoints = _derive_endpoints(urls)

    status = "ok"
    msg = f"{len(params)} params"
    return finalize(status, msg, options, used_cmd or "arjun", t0, raw, output_file=outfile,
                    params=params, endpoints=endpoints)
