# tools/alltools/tools/dnsx.py
from __future__ import annotations
from pathlib import Path
from typing import List
import json

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms, DOMAIN_RE, IPV4_RE, IPV6_RE
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 1800

def _parse_dnsx_jsonl(blob: str) -> (List[str], List[str]):
    alive, ips = [], []
    sa, si = set(), set()
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s: continue
        try:
            obj = json.loads(s)
        except Exception:
            # fallback plain line: "domain ip"
            parts = s.split()
            if parts:
                d = parts[0].lower().strip(".")
                if DOMAIN_RE.match(d) and d not in sa:
                    sa.add(d); alive.append(d)
                for p in parts[1:]:
                    if IPV4_RE.match(p) or IPV6_RE.match(p):
                        if p not in si:
                            si.add(p); ips.append(p)
            continue
        host = (obj.get("host") or obj.get("input") or "").lower().strip(".")
        if host and DOMAIN_RE.match(host) and host not in sa:
            sa.add(host); alive.append(host)
        for a in obj.get("a", []) + obj.get("ips", []):
            ip = str(a).strip()
            if (IPV4_RE.match(ip) or IPV6_RE.match(ip)) and ip not in si:
                si.add(ip); ips.append(ip)
    return alive, ips

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work = ensure_work_dir(options, "dnsx")
    slug = options.get("tool_slug", "dnsx")
    pol  = options.get("_policy") or get_effective_policy(slug)
    ipol = pol.get("input_policy", {}) or {}

    exe = resolve_bin("dnsx", "dnsx.exe")
    if not exe:
        return finalize("error", "dnsx not installed", options, "dnsx", t0, "", error_reason="NOT_INSTALLED")

    # accepts domains/hosts (strings)
    doms, _ = read_targets(options, accept_keys=("domains","hosts"), cap=ipol.get("max_targets") or 100000)
    if not doms:
        raise ValidationError("Provide domains/hosts for dnsx.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", pol.get("runtime_constraints",{}).get("timeout_s"), default=30, kind="int") or 30

    fp = Path(work) / "targets.txt"
    fp.write_text("\n".join(doms), encoding="utf-8")

    args = [exe, "-l", str(fp), "-a", "-resp", "-json", "-silent", "-rtime", str(timeout_s)]
    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 60), cwd=work)
    outfile = write_output_file(work, "dnsx_output.jsonl", out or "")

    alive, ips = _parse_dnsx_jsonl(out or "")
    msg = f"{len(alive)} alive, {len(ips)} ips"
    return finalize("ok", msg, options, " ".join(args), t0, out, output_file=outfile, domains=alive, ips=ips)
