# tools/alltools/tools/commix.py
from __future__ import annotations
from pathlib import Path
from typing import List
import re

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


HARD_TIMEOUT = 7200
RE_INJECT = re.compile(r"(?i)(command injection|injection parameter|vulnerable)")

def _parse_commix(text: str) -> (List[str], List[str]):
    vulns, exps = [], []
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if RE_INJECT.search(s):
            vulns.append(s)
        if s.lower().startswith("[payload]") or "payload:" in s.lower():
            exps.append(s)
    sv, se = set(), set()
    return [x for x in vulns if not (x in sv or sv.add(x))], [x for x in exps if not (x in se or se.add(x))]

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "commix")
    slug = options.get("tool_slug", "commix")
    policy = options.get("_policy") or get_effective_policy(slug)

    exe = resolve_bin("commix.py", "commix")
    if not exe:
        return finalize("error", "commix not installed", options, "commix", t0, "", error_reason="NOT_INSTALLED")

    urls, _   = read_targets(options, accept_keys=("urls",),   cap=2000)
    params, _ = read_targets(options, accept_keys=("params",), cap=5000)
    if not urls:
        raise ValidationError("Provide URLs to scan with commix.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    vulns: List[str] = []
    exps:  List[str] = []
    all_raw = []
    used_cmd = ""

    for u in urls:
        args = [exe, "--batch", "-u", u, "--ignore-redirects"]
        for p in (params or [])[:5]:
            args += ["-p", p]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work_dir)
        all_raw.append(out or "")
        v, r = _parse_commix(out or "")
        vulns.extend(v); exps.extend(r)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "commix_output.txt", raw or "")

    sv, se = set(), set()
    vulns = [x for x in vulns if not (x in sv or sv.add(x))]
    exps  = [x for x in exps  if not (x in se or se.add(x))]

    status = "ok"
    msg = f"{len(vulns)} vulns, {len(exps)} details"
    return finalize(status, msg, options, used_cmd or "commix", t0, raw, output_file=outfile,
                    vulns=vulns, exploit_results=exps)
