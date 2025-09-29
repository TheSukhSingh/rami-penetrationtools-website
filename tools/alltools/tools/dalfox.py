# tools/alltools/tools/dalfox.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json

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


def _parse_dalfox_json(blob: str) -> List[str]:
    vulns: List[str] = []
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)  # dalfox --format json emits JSON per line
        except Exception:
            continue
        typ = obj.get("type") or obj.get("vtype") or "xss"
        url = obj.get("target") or obj.get("url")
        payload = obj.get("payload") or obj.get("PoC")
        parts = [p for p in [typ, url, payload] if p]
        vulns.append(" | ".join(map(str, parts)))
    # de-dup
    seen = set()
    return [x for x in vulns if not (x in seen or seen.add(x))]


def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "dalfox")
    slug = options.get("tool_slug", "dalfox")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("dalfox", "dalfox.exe")
    if not exe:
        return finalize("error", "dalfox not installed", options, "dalfox", t0, "", error_reason="NOT_INSTALLED")

    # dalfox can accept urls or use "pipe" mode; we keep it simple: run per URL
    urls, _     = read_targets(options, accept_keys=("urls",),       cap=ipol.get("max_targets") or 5000)
    endpoints, _= read_targets(options, accept_keys=("endpoints",),  cap=5000)  # optional
    params, _   = read_targets(options, accept_keys=("params",),     cap=5000)  # optional

    if not urls:
        raise ValidationError("Provide URLs to scan with dalfox.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    vulns: List[str] = []
    all_raw = []
    used_cmd = ""

    for u in urls:
        args = [exe, "url", u, "--format", "json", "--silence"]
        # optionally guide dalfox to specific params/endpoints (best-effort)
        # (dalfox will discover on its own; this is just a hint)
        for p in (params or [])[:10]:
            args += ["-p", p]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)
        if out:
            all_raw.append(out)
            vulns.extend(_parse_dalfox_json(out))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "dalfox_output.jsonl", raw or "")

    # de-dup
    seen = set()
    vulns = [x for x in vulns if not (x in seen or seen.add(x))]

    status = "ok" if (len(vulns) > 0 or raw) else "error"
    msg = f"{len(vulns)} findings"
    return finalize(status, msg, options, used_cmd or "dalfox", t0, raw, output_file=outfile, vulns=vulns,
                    error_reason=None if status == "ok" else "OTHER")
