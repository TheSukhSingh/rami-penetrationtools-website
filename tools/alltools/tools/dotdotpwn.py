# tools/alltools/tools/dotdotpwn.py
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


HARD_TIMEOUT = 3600
RE_VULN = re.compile(r"(?i)vulnerable|found\s+file|200\s+OK")

def _parse(text: str) -> (List[str], List[str]):
    vulns, exps = [], []
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if RE_VULN.search(s):
            if "vulnerable" in s.lower():
                vulns.append(s)
            else:
                exps.append(s)
    sv, se = set(), set()
    return [x for x in vulns if not (x in sv or sv.add(x))], [x for x in exps if not (x in se or se.add(x))]

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "dotdotpwn")
    slug = options.get("tool_slug", "dotdotpwn")
    policy = options.get("_policy") or get_effective_policy(slug)

    exe = resolve_bin("dotdotpwn", "dotdotpwn.pl")
    if not exe:
        return finalize("error", "dotdotpwn not installed", options, "dotdotpwn", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","endpoints"), cap=2000)
    if not urls:
        raise ValidationError("Provide URLs or endpoints for dotdotpwn.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    vulns: List[str] = []
    exps:  List[str] = []
    all_raw = []
    used_cmd = ""

    for u in urls:
        args = [exe, "-m", "http", "-u", u, "-k", "-q"]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)
        all_raw.append(out or "")
        v, r = _parse(out or "")
        vulns.extend(v); exps.extend(r)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "dotdotpwn_output.txt", raw or "")

    sv, se = set(), set()
    vulns = [x for x in vulns if not (x in sv or sv.add(x))]
    exps  = [x for x in exps  if not (x in se or se.add(x))]

    status = "ok"
    msg = f"{len(vulns)} vulns, {len(exps)} details"
    return finalize(status, msg, options, used_cmd or "dotdotpwn", t0, raw, output_file=outfile,
                    vulns=vulns, exploit_results=exps)
