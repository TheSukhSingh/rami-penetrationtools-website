# tools/alltools/tools/hakrawler.py
from __future__ import annotations
from pathlib import Path
from typing import List
from urllib.parse import urlsplit, parse_qsl

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

HARD_TIMEOUT = 1800

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "hakrawler")
    slug = options.get("tool_slug", "hakrawler")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("hakrawler")
    if not exe:
        return finalize("error", "hakrawler not installed", options, "hakrawler", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","domains"), cap=ipol.get("max_targets") or 5000)
    if not urls:
        raise ValidationError("Provide URLs/domains for hakrawler.", "INVALID_PARAMS", "no input")

    fp = Path(work_dir) / "targets.txt"
    fp.write_text("\n".join(urls), encoding="utf-8")

    depth     = clamp_from_constraints(options, "depth",     policy.get("runtime_constraints", {}).get("depth"),     default=3, kind="int") or 3
    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=20, kind="int") or 20
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=10, kind="int") or 10

    args = [exe, "-plain", "-depth", str(depth), "-concurrency", str(threads), "-usewayback", "-timeout", str(timeout_s)]
    # feed file via stdin (hakrawler reads from stdin if no -url)
    # We emulate: cat targets.txt | hakrawler ...
    # Simpler: run once per target to avoid shell piping dependencies:
    all_out = []
    for u in urls:
        per_args = args + ["-url", u]
        rc, out, _ms = run_cmd(per_args, timeout_s=min(HARD_TIMEOUT, timeout_s + 60), cwd=work_dir)
        if out:
            all_out.append(out)

    raw = "\n".join(all_out)
    outfile = write_output_file(work_dir, "hakrawler_output.txt", raw or "")

    found: List[str] = []
    seen = set()
    for ln in (raw or "").splitlines():
        s = (ln or "").strip()
        if s.startswith("http://") or s.startswith("https://"):
            if s not in seen:
                seen.add(s); found.append(s)

    status = "ok"
    msg = f"{len(found)} urls"
    return finalize(status, msg, options, "hakrawler -plain ...", t0, raw, output_file=outfile,
                    urls=found)
