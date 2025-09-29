# tools/alltools/tools/sqlmap.py
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
RE_VULN = re.compile(r"(?i)is vulnerable|parameter .*? is vulnerable|type:.*?sql", re.S)
RE_DUMP = re.compile(r"(?i)Database:\s|\[INFO\]\s+fetched", re.S)

def _parse_sqlmap(text: str) -> (List[str], List[str]):
    vulns, results = [], []
    if RE_VULN.search(text or ""):
        vulns.append("SQLi detected")
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if "Payload:" in s or "Parameter:" in s:
            results.append(s)
        if s.startswith("Database:") or s.startswith("Table:") or s.startswith("Column:"):
            results.append(s)
    # de-dup
    sv = set(); se = set()
    vulns   = [x for x in vulns if not (x in sv or sv.add(x))]
    results = [x for x in results if not (x in se or se.add(x))]
    return vulns, results

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "sqlmap")
    slug = options.get("tool_slug", "sqlmap")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("sqlmap.py", "sqlmap")
    if not exe:
        return finalize("error", "sqlmap not installed", options, "sqlmap", t0, "", error_reason="NOT_INSTALLED")

    urls, _   = read_targets(options, accept_keys=("urls",),   cap=ipol.get("max_targets") or 2000)
    params, _ = read_targets(options, accept_keys=("params",), cap=5000)  # optional
    if not urls:
        raise ValidationError("Provide URLs to scan with sqlmap.", "INVALID_PARAMS", "no input")

    level     = clamp_from_constraints(options, "level",     policy.get("runtime_constraints", {}).get("level"),     default=2,  kind="int") or 2
    risk      = clamp_from_constraints(options, "risk",      policy.get("runtime_constraints", {}).get("risk"),      default=1,  kind="int") or 1
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    all_raw = []
    all_vulns: List[str] = []
    exps: List[str] = []
    used_cmd = ""

    for u in urls:
        args = [exe, "-u", u, "--batch", f"--level={level}", f"--risk={risk}", "--random-agent"]
        for p in (params or [])[:5]:
            args += ["-p", p]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work_dir)
        all_raw.append(out or "")
        v, r = _parse_sqlmap(out or "")
        all_vulns.extend(v); exps.extend(r)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "sqlmap_output.txt", raw or "")

    # de-dup
    sv = set(); se = set()
    all_vulns = [x for x in all_vulns if not (x in sv or sv.add(x))]
    exps      = [x for x in exps      if not (x in se or se.add(x))]

    status = "ok"
    msg = f"{len(all_vulns)} vulns, {len(exps)} details"
    return finalize(status, msg, options, used_cmd or "sqlmap", t0, raw, output_file=outfile,
                    vulns=all_vulns, exploit_results=exps)
