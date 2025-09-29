# tools/alltools/tools/subfinder.py
from __future__ import annotations
from pathlib import Path
from typing import List
import json

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms, DOMAIN_RE
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 1800

def _parse_jsonl(blob: str) -> List[str]:
    out, seen = [], set()
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s: continue
        try:
            obj = json.loads(s)
        except Exception:
            # fallback: plain text line with hostname
            s2 = s.lstrip("*.").lower()
            if DOMAIN_RE.match(s2) and s2 not in seen:
                seen.add(s2); out.append(s2)
            continue
        host = (obj.get("host") or obj.get("dns_names") or obj.get("name") or "").strip().lower()
        if host:
            host = host.lstrip("*.")  # normalize
            if DOMAIN_RE.match(host) and host not in seen:
                seen.add(host); out.append(host)
    return out

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work = ensure_work_dir(options, "subfinder")
    slug = options.get("tool_slug", "subfinder")
    pol  = options.get("_policy") or get_effective_policy(slug)
    ipol = pol.get("input_policy", {}) or {}

    exe = resolve_bin("subfinder", "subfinder.exe")
    if not exe:
        return finalize("error", "subfinder not installed", options, "subfinder", t0, "", error_reason="NOT_INSTALLED")

    roots, _ = read_targets(options, accept_keys=("domains",), cap=ipol.get("max_targets") or 100)
    if not roots:
        raise ValidationError("Provide root domain(s) for subfinder.", "INVALID_PARAMS", "no input")

    threads   = clamp_from_constraints(options, "threads",   pol.get("runtime_constraints",{}).get("threads"),   default=10, kind="int") or 10
    timeout_s = clamp_from_constraints(options, "timeout_s", pol.get("runtime_constraints",{}).get("timeout_s"), default=60, kind="int") or 60
    all_src   = bool(options.get("all_sources", pol.get("runtime_constraints",{}).get("all_sources", False)))
    silent    = bool(options.get("silent", pol.get("runtime_constraints",{}).get("silent", True)))

    fp = Path(work) / "roots.txt"
    fp.write_text("\n".join(roots), encoding="utf-8")

    args = [exe, "-dL", str(fp), "-t", str(threads), "-timeout", str(timeout_s), "-oJ"]
    if all_src: args.append("-all")
    if silent:  args.append("-silent")

    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 120), cwd=work)
    outfile = write_output_file(work, "subfinder_output.jsonl", out or "")

    subs = _parse_jsonl(out or "")
    msg  = f"{len(subs)} subdomains"
    return finalize("ok", msg, options, " ".join(args), t0, out, output_file=outfile, domains=subs)
