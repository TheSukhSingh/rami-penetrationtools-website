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

HARD_TIMEOUT = 600

RE_BEHIND = re.compile(r"(?i)is\s+behind\s+(.*)")

def _parse_waf(text: str) -> List[str]:
    wafs: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        m = RE_BEHIND.search(s)
        if m:
            name = m.group(1).strip().strip(".")
            if name and name not in seen:
                seen.add(name); wafs.append(f"WAF: {name}")
        elif "No WAF detected" in s or "No WAF" in s:
            if "WAF: None" not in seen:
                seen.add("WAF: None"); wafs.append("WAF: None")
    return wafs

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "wafw00f")
    slug = options.get("tool_slug", "wafw00f")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("wafw00f", "wafw00f.bat", "wafw00f.cmd")
    if not exe:
        # python module fallback
        py = resolve_bin("python3", "python")
        if not py:
            return finalize("error", "wafw00f not installed", options, "wafw00f", t0, "", error_reason="NOT_INSTALLED")
        exe = py

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 5000)
    if not urls:
        raise ValidationError("Provide URLs to fingerprint WAF.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=20, kind="int") or 20

    all_out = []
    used_cmd = ""
    for u in urls:
        if exe.endswith("python") or exe.endswith("python3"):
            args = [exe, "-m", "wafw00f", u]
        else:
            args = [exe, u]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 40), cwd=work_dir)
        if out:
            all_out.append(out)

    out = "\n".join(all_out)
    outfile = write_output_file(work_dir, "wafw00f_output.txt", out or "")

    wafs = _parse_waf(out)
    status = "ok"
    msg = f"{len(wafs)} detections"
    return finalize(status, msg, options, used_cmd or "wafw00f", t0, out, output_file=outfile,
                    tech_stack=wafs)
