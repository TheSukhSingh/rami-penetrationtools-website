# tools/alltools/tools/s3scanner.py
from __future__ import annotations
from pathlib import Path
from typing import List
import json
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


HARD_TIMEOUT = 1800
RE_POSITIVE = re.compile(r"\[\+\]|\bpublic\b|\bopen\b|\bworld[- ]readable\b", re.I)


def _parse_json_or_text(out: str) -> List[str]:
    # Many forks output JSON; others print text with [+] lines
    out = out or ""
    vulns: List[str] = []

    # try JSON
    try:
        data = json.loads(out)
        items = data if isinstance(data, list) else [data]
        for it in items:
            if not isinstance(it, dict): 
                continue
            name = it.get("bucket") or it.get("name")
            status = it.get("status") or it.get("permission")
            msg = f"{name}: {status}" if name or status else None
            if msg:
                vulns.append(msg)
    except Exception:
        # fallback text
        for ln in out.splitlines():
            s = (ln or "").strip()
            if not s:
                continue
            if RE_POSITIVE.search(s.lower()):
                vulns.append(s)

    # de-dup
    seen = set()
    return [x for x in vulns if not (x in seen or seen.add(x))]


def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "s3scanner")
    slug = options.get("tool_slug", "s3scanner")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("s3scanner", "S3Scanner", "s3-buckets-scanner")
    if not exe:
        # common python module name
        py = resolve_bin("python3", "python")
        if not py:
            return finalize("error", "s3scanner not installed", options, "s3scanner", t0, "", error_reason="NOT_INSTALLED")
        exe = py

    # Accept domains or urls; we just pass the host parts/fqdns as bucket candidates or patterns
    domains, _ = read_targets(options, accept_keys=("domains","hosts"), cap=ipol.get("max_targets") or 2000)
    urls, _    = read_targets(options, accept_keys=("urls",),          cap=2000)
    targets = domains + urls
    if not targets:
        raise ValidationError("Provide domains/hosts or URLs for S3 scanning.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=60, kind="int") or 60

    vulns: List[str] = []
    all_raw = []
    used_cmd = ""

    for t in targets:
        if exe.endswith("python") or exe.endswith("python3"):
            args = [exe, "-m", "s3scanner", t]
        else:
            args = [exe, t]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)
        if out:
            all_raw.append(out)
            vulns.extend(_parse_json_or_text(out))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "s3scanner_output.txt", raw or "")

    status = "ok" if (len(vulns) > 0 or raw) else "error"
    msg = f"{len(vulns)} findings"
    return finalize(status, msg, options, used_cmd or "s3scanner", t0, raw, output_file=outfile, vulns=vulns,
                    error_reason=None if status == "ok" else "OTHER")
