# tools/alltools/tools/nikto.py
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
    from _common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 3600
PLUS_LINE = re.compile(r"^\s*\+\s+(.*)$")


def _parse_nikto(text: str) -> List[str]:
    vulns: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        m = PLUS_LINE.match(ln or "")
        if not m:
            continue
        s = m.group(1).strip()
        if s and s not in seen:
            seen.add(s); vulns.append(s)
    return vulns


def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "nikto")
    slug = options.get("tool_slug", "nikto")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("nikto")
    if not exe:
        return finalize("error", "nikto not installed", options, "nikto", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 2000)
    if not urls:
        raise ValidationError("Provide URLs to scan with nikto.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=90, kind="int") or 90

    vulns: List[str] = []
    all_raw = []
    used_cmd = ""

    for u in urls:
        args = [exe, "-host", u, "-nolookup", "-nointeractive"]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)
        if out:
            all_raw.append(out)
            vulns.extend(_parse_nikto(out))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "nikto_output.txt", raw or "")

    # de-dup
    seen = set()
    vulns = [x for x in vulns if not (x in seen or seen.add(x))]

    status = "ok" if (len(vulns) > 0 or raw) else "error"
    msg = f"{len(vulns)} findings"
    return finalize(status, msg, options, used_cmd or "nikto", t0, raw, output_file=outfile, vulns=vulns,
                    error_reason=None if status == "ok" else "OTHER")
