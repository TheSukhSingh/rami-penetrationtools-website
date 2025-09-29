from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
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

HARD_TIMEOUT = 600  # seconds
PLUGIN_TOKEN = re.compile(r"([A-Za-z0-9_.\-+ ]+)\[")

def _parse_whatweb(text: str) -> List[str]:
    techs: List[str] = []
    seen = set()
    for raw in (text or "").splitlines():
        s = (raw or "").strip()
        if not s:
            continue
        # WhatWeb prints URL then a series of Plugin[info] tokens.
        for tok in s.split():
            if "[" in tok and tok.endswith("]"):
                m = PLUGIN_TOKEN.match(tok)
                if m:
                    name = m.group(1).strip()
                    # skip common noise tokens
                    if name and name.lower() not in ("http-server-header","country","ip","title","status"):
                        if name not in seen:
                            seen.add(name); techs.append(name)
    return techs

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "whatweb")
    slug = options.get("tool_slug", "whatweb")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("whatweb", "whatweb.bat", "whatweb.cmd")
    if not exe:
        return finalize("error", "whatweb not installed", options, "whatweb", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 10000)
    if not urls:
        raise ValidationError("Provide URLs to fingerprint.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=15, kind="int") or 15
    # write inputs
    fp = Path(work_dir) / "targets.txt"
    fp.write_text("\n".join(urls), encoding="utf-8")

    # -i FILE reads list; --no-errors reduces noise; --color=never for clean output
    args: List[str] = [exe, "-i", str(fp), "--no-errors", "--color=never"]
    # Execute
    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 60), cwd=work_dir)
    outfile = write_output_file(work_dir, "whatweb_output.txt", out or "")

    techs = _parse_whatweb(out)
    status = "ok" if rc == 0 else "error"
    msg = f"{len(techs)} tech signals"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    tech_stack=techs, error_reason=None if rc == 0 else "OTHER")
