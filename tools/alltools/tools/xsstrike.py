# tools/alltools/tools/xsstrike.py
from __future__ import annotations
from pathlib import Path
from typing import List
import os
import re

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 3600
RE_FINDING = re.compile(r"(?i)(reflected|stored)\s*xss|vulnerable|payload", re.I)


def _parse_xsstrike(text: str) -> List[str]:
    vulns: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        if RE_FINDING.search(s):
            if s not in seen:
                seen.add(s); vulns.append(s)
    return vulns


def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "xsstrike")
    slug = options.get("tool_slug", "xsstrike")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    # XSStrike is usually a python module/package
    py = resolve_bin("python3", "python")
    if not py:
        return finalize("error", "python not found for XSStrike", options, "xsstrike", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 1000)
    if not urls:
        raise ValidationError("Provide URLs to scan with XSStrike.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    vulns: List[str] = []
    all_raw = []
    used_cmd = ""

    for u in urls:
        # non-interactive mode; skip heavy DOM checks for speed by default
        args = [py, "-m", "XSStrike", "-u", u, "--crawl", "0", "--blind", "--skip-dom"]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 120), cwd=work_dir)
        if out:
            all_raw.append(out)
            vulns.extend(_parse_xsstrike(out))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "xsstrike_output.txt", raw or "")

    # de-dup
    seen = set()
    vulns = [x for x in vulns if not (x in seen or seen.add(x))]

    status = "ok" if (len(vulns) > 0 or raw) else "error"
    msg = f"{len(vulns)} findings"
    return finalize(status, msg, options, used_cmd or "xsstrike", t0, raw, output_file=outfile, vulns=vulns,
                    error_reason=None if status == "ok" else "OTHER")
