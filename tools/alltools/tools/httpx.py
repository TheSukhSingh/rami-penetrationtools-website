# tools/alltools/tools/httpx.py
from __future__ import annotations
from pathlib import Path
from typing import List
import json

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

def _parse_httpx_jsonl(blob: str) -> List[str]:
    out, seen = [], set()
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s: continue
        try:
            obj = json.loads(s)
        except Exception:
            # fallback: plain URL per line
            if (s.startswith("http://") or s.startswith("https://")) and s not in seen:
                seen.add(s); out.append(s); 
            continue
        url = obj.get("url") or obj.get("input") or obj.get("host")
        if url and (str(url).startswith("http://") or str(url).startswith("https://")):
            if url not in seen:
                seen.add(url); out.append(url)
    return out

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work = ensure_work_dir(options, "httpx")
    slug = options.get("tool_slug", "httpx")
    pol  = options.get("_policy") or get_effective_policy(slug)
    ipol = pol.get("input_policy", {}) or {}

    exe = resolve_bin("httpx", "httpx.exe")
    if not exe:
        return finalize("error", "httpx not installed", options, "httpx", t0, "", error_reason="NOT_INSTALLED")

    # Accept urls/hosts/domains, httpx will normalize
    seeds, _ = read_targets(options, accept_keys=("urls","hosts","domains"), cap=ipol.get("max_targets") or 100000)
    if not seeds:
        raise ValidationError("Provide urls/hosts/domains for httpx.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", pol.get("runtime_constraints",{}).get("timeout_s"), default=10, kind="int") or 10
    rate      = clamp_from_constraints(options, "rate",      pol.get("runtime_constraints",{}).get("rate"),      default=150, kind="int") or 150

    fp = Path(work) / "targets.txt"
    fp.write_text("\n".join(seeds), encoding="utf-8")

    args = [exe, "-l", str(fp), "-json", "-no-color", "-silent",
            "-follow-redirects", "-timeout", str(timeout_s), "-rate-limit", str(rate)]
    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 120), cwd=work)
    outfile = write_output_file(work, "httpx_output.jsonl", out or "")

    urls = _parse_httpx_jsonl(out or "")
    msg = f"{len(urls)} alive urls"
    return finalize("ok", msg, options, " ".join(args), t0, out, output_file=outfile, urls=urls)
