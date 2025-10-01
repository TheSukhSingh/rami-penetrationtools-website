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
from ._common import resolve_wordlist_path


HARD_TIMEOUT = 3600
RE_FOUND = re.compile(r"(?i)^\s*/[^ ]+\s+\(Status:")

def _parse_gobuster(text: str, base_url: str) -> List[str]:
    eps: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if RE_FOUND.search(s):
            path = s.split()[0]
            if path and path not in seen:
                seen.add(path); eps.append(path)
    return eps

def run_scan(options: dict) -> dict:

    t0 = now_ms()
    work_dir = ensure_work_dir(options, "gobuster")
    slug = options.get("tool_slug", "gobuster")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}
    # wordlist resolution (options > tier > policy hint > default tier)
    wordlist = (options.get("wordlist") or "").strip()
    if not wordlist:
        wl_tier = (
            options.get("wordlist_tier")
            or ((policy.get("runtime_constraints", {}).get("_hints") or {}).get("wordlist_default"))
            or "medium"
        )
        wordlist = resolve_wordlist_path(wl_tier)

    if not wordlist or not Path(wordlist).exists():
        raise ValidationError("wordlist is required for gobuster.", "INVALID_PARAMS", "missing wordlist")

    exe = resolve_bin("gobuster", "gobuster.exe")
    if not exe:
        return finalize("error", "gobuster not installed", options, "gobuster", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","hosts","domains"), cap=ipol.get("max_targets") or 10000)
    if not urls:
        raise ValidationError("Provide a URL/host/domain for gobuster.", "INVALID_PARAMS", "no input")

    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=50, kind="int") or 50
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    endpoints: List[str] = []
    all_raw = []
    used_cmd = ""

    for base in urls:
        args = [exe, "dir", "-u", base, "-w", str(wordlist), "-t", str(threads)]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work_dir)
        all_raw.append(out or "")
        endpoints.extend(_parse_gobuster(out or "", base))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "gobuster_output.txt", raw or "")
    # dedupe
    seen = set(); endpoints = [x for x in endpoints if not (x in seen or seen.add(x))]

    status = "ok"
    msg = f"{len(endpoints)} endpoints"
    return finalize(status, msg, options, used_cmd or "gobuster", t0, raw, output_file=outfile,
                    endpoints=endpoints)
