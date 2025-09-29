# tools/alltools/tools/fuxploider.py
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

def _parse_json(blob: str) -> List[str]:
    exps: List[str] = []
    try:
        data = json.loads(blob)
        for k in ("vulnerabilities","results","findings"):
            items = data.get(k)
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        msg = it.get("url") or it.get("message") or it.get("path")
                        if msg:
                            exps.append(str(msg))
    except Exception:
        pass
    # de-dup
    seen = set()
    return [x for x in exps if not (x in seen or seen.add(x))]

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "fuxploider")
    slug = options.get("tool_slug", "fuxploider")
    policy = options.get("_policy") or get_effective_policy(slug)

    exe = resolve_bin("fuxploider", "fuxploider.py")
    if not exe:
        return finalize("error", "fuxploider not installed", options, "fuxploider", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","endpoints"), cap=2000)
    if not urls:
        raise ValidationError("Provide URLs/endpoints for fuxploider.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=60, kind="int") or 60

    exps: List[str] = []
    all_raw = []
    used_cmd = ""
    for u in urls:
        args = [exe, "-u", u, "--random-agent", "--output-format", "json"]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)
        all_raw.append(out or "")
        exps.extend(_parse_json(out or ""))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "fuxploider_output.json", raw or "")
    status = "ok"
    msg = f"{len(exps)} exploit results"
    return finalize(status, msg, options, used_cmd or "fuxploider", t0, raw, output_file=outfile,
                    exploit_results=exps)
