# tools/alltools/tools/linkfinder.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlsplit, parse_qsl
from ._common import (
    resolve_bin, ensure_work_dir, read_targets,
    run_cmd, write_output_file, finalize, ValidationError, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 900  # seconds

def _derive_params_from_endpoints(eps: List[str]) -> List[str]:
    params: List[str] = []
    seen = set()
    for e in eps or []:
        # try to parse as URL to extract query keys
        try:
            sp = urlsplit(e)
            if sp.query:
                for k, _v in parse_qsl(sp.query, keep_blank_values=True):
                    if k not in seen:
                        seen.add(k); params.append(k)
        except Exception:
            # fallback: treat "?a=b&c=d" in raw strings
            if "?" in e:
                for kv in e.split("?", 1)[1].split("&"):
                    if "=" in kv:
                        k = kv.split("=",1)[0]
                        if k and k not in seen:
                            seen.add(k); params.append(k)
    return params

def _parse_linkfinder(text: str) -> Tuple[List[str], List[str]]:
    endpoints: List[str] = []
    urls: List[str] = []
    seen_e, seen_u = set(), set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        # LinkFinder -o cli prints endpoints one per line, usually full or relative paths/URLs
        # Heuristics: keep absolute http(s) in urls; keep everything in endpoints
        if s.startswith("http://") or s.startswith("https://"):
            if s not in seen_u:
                seen_u.add(s); urls.append(s)
        if s not in seen_e:
            seen_e.add(s); endpoints.append(s)
    return endpoints, urls

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "linkfinder")
    slug = options.get("tool_slug", "linkfinder")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("linkfinder", "linkfinder.exe")
    if not exe:
        # sometimes installed as python module only: python3 -m linkfinder
        exe = resolve_bin("python3", "python")
        if not exe:
            return finalize("error", "LinkFinder not installed", options, "linkfinder", t0, "", error_reason="NOT_INSTALLED")

    targets, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 1000)
    if not targets:
        raise ValidationError("Provide URLs to scan for endpoints (JS).", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    # LinkFinder accepts a single -i; run per target
    out_all = []
    used_cmd = ""
    for u in targets:
        if "linkfinder" in exe:
            args = [exe, "-i", u, "-o", "cli"]
        else:
            args = [exe, "-m", "linkfinder", "-i", u, "-o", "cli"]
        used_cmd = " ".join(args[:2] + ["..."])  # short echo
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 30), cwd=work_dir)
        if out:
            out_all.append(out)

    out = "\n".join(out_all)
    outfile = write_output_file(work_dir, "linkfinder_output.txt", out or "")

    endpoints, abs_urls = _parse_linkfinder(out)
    params = _derive_params_from_endpoints(endpoints)

    status = "ok"
    msg = f"{len(endpoints)} endpoints, {len(params)} params"
    return finalize(status, msg, options, used_cmd or "linkfinder", t0, out, output_file=outfile,
                    endpoints=endpoints, params=params, urls=abs_urls)
