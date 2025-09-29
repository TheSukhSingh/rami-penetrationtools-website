# tools/alltools/tools/subfinder.py
from __future__ import annotations
from pathlib import Path
from typing import List
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, classify_domains,
    run_cmd, write_output_file, finalize, ValidationError, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 300  # seconds

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "subfinder")
    slug = options.get("tool_slug", "subfinder")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {})

    # 1) Resolve binary
    exe = resolve_bin("subfinder", "subfinder.exe")
    if not exe:
        return finalize("error", "subfinder not installed", options, "subfinder", t0, "", error_reason="NOT_INSTALLED")

    # 2) Read inputs
    raw, _ = read_targets(options, accept_keys=("domains",), cap=ipol.get("max_targets") or 50)
    if not raw:
        raise ValidationError("At least one root domain is required.", "INVALID_PARAMS", "no input")
    valid, _ = classify_domains(raw)
    if not valid:
        raise ValidationError("Input must be valid domain(s).", "INVALID_PARAMS", "no valid domains")

    # 3) Options
    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=10, kind="int") or 10
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=60, kind="int") or 60
    all_src   = bool(options.get("all_sources") or False)
    silent    = bool(options.get("silent", True))

    # 4) Compose args
    args: List[str] = [exe]
    if silent:  args.append("-silent")
    if all_src: args.append("-all")
    args += ["-t", str(threads), "-timeout", str(timeout_s)]
    # -d for few, -dL for list
    if len(valid) <= 5:
        for d in valid:
            args += ["-d", d]
    else:
        fp = Path(work_dir) / "subfinder_targets.txt"
        fp.write_text("\n".join(valid), encoding="utf-8")
        args += ["-dL", str(fp)]

    # 5) Execute
    timeout = min(HARD_TIMEOUT, max(timeout_s, 5) + 30)
    rc, out, ms = run_cmd(args, timeout_s=timeout, cwd=work_dir)
    outfile = write_output_file(work_dir, "subfinder_output.txt", out or "")

    # 6) Parse
    lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    good, _ = classify_domains(lines)

    status = "ok" if rc == 0 else "error"
    msg = f"{len(good)} subdomains"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    domains=good, error_reason=None if rc == 0 else "OTHER")
