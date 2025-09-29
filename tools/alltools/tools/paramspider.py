# tools/alltools/tools/paramspider.py
from __future__ import annotations
from pathlib import Path
from typing import List
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

HARD_TIMEOUT = 3600

def _params_from_urls(urls: List[str]) -> List[str]:
    out, seen = [], set()
    for u in urls or []:
        try:
            qs = urlsplit(u).query
            if not qs: 
                continue
            for k, _ in parse_qsl(qs, keep_blank_values=True):
                if k not in seen:
                    seen.add(k); out.append(k)
        except Exception:
            continue
    return out

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "paramspider")
    slug = options.get("tool_slug", "paramspider")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("paramspider")
    py  = resolve_bin("python3", "python")
    if not exe and not py:
        return finalize("error", "paramspider not installed", options, "paramspider", t0, "", error_reason="NOT_INSTALLED")

    # It primarily accepts domains; URLs also work (treated as seeds)
    domains, _ = read_targets(options, accept_keys=("domains","hosts"), cap=ipol.get("max_targets") or 500)
    urls, _    = read_targets(options, accept_keys=("urls",),          cap=2000)
    targets = domains or urls
    if not targets:
        raise ValidationError("Provide domains or URLs for paramspider.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=60, kind="int") or 60
    level     = clamp_from_constraints(options, "level", policy.get("runtime_constraints", {}).get("level"), default=3, kind="int") or 3
    subs      = bool(options.get("include_subdomains", True))

    found_urls: List[str] = []
    all_raw = []
    used_cmd = ""

    for t in targets:
        if exe:
            args = [exe, "-d", t, "-l", str(level)]
            if subs: args += ["--subs"]
        else:
            args = [py, "-m", "paramspider", "-d", t, "-l", str(level)]
            if subs: args += ["--subs"]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)
        if out:
            all_raw.append(out)
            # ParamSpider prints URLs; capture http(s) lines
            for ln in out.splitlines():
                s = (ln or "").strip()
                if s.startswith("http://") or s.startswith("https://"):
                    found_urls.append(s)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "paramspider_output.txt", raw or "")

    params = _params_from_urls(found_urls)
    status = "ok"
    msg = f"{len(params)} params from {len(found_urls)} urls"
    return finalize(status, msg, options, used_cmd or "paramspider", t0, raw, output_file=outfile,
                    params=params, urls=found_urls)
