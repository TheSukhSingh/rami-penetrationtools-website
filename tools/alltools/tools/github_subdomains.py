# tools/alltools/tools/github_subdomains.py
from __future__ import annotations
from typing import List
import os

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets, DOMAIN_RE,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *
try:
    from tools.policies import get_effective_policy
except ImportError:
    from policies import get_effective_policy

HARD_TIMEOUT = 1800

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "github_subdomains")
    slug = options.get("tool_slug", "github_subdomains")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("github_subdomains", "github_subdomains")
    if not exe:
        return finalize("error", "github_subdomains not installed", options, "github_subdomains", t0, "", error_reason="NOT_INSTALLED")

    token = options.get("github_token") or os.environ.get("GITHUB_TOKEN")
    if not token:
        # tool may still run unauthenticated (limited); continue, but warn via message
        pass

    domains, _ = read_targets(options, accept_keys=("domains",), cap=ipol.get("max_targets") or 100)
    if not domains:
        raise ValidationError("Provide root domain(s) for GitHub subdomain search.", "INVALID_PARAMS", "no input")

    env = dict(os.environ)
    if token:
        env["GITHUB_TOKEN"] = token

    all_raw = []
    subdomains: List[str] = []
    used_cmd = ""

    for d in domains:
        args = [exe, "-d", d]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work_dir)
        all_raw.append(out or "")
        for ln in (out or "").splitlines():
            s = (ln or "").strip().lower()
            if DOMAIN_RE.match(s):
                subdomains.append(s)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "github_subdomains_output.txt", raw or "")

    status = "ok"
    msg = f"{len(subdomains)} subdomains"
    return finalize(status, msg, options, used_cmd or "github_subdomains", t0, raw, output_file=outfile,
                    domains=subdomains)
