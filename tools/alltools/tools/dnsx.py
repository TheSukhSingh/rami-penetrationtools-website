# tools/alltools/tools/dnsx.py
from __future__ import annotations
from pathlib import Path
import os, re
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, classify_domains,
    run_cmd, write_output_file, finalize, ValidationError, IPV4_RE, IPV6_RE
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 300

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed * 1000) if hasattr(os, "times") else 0
    work_dir = ensure_work_dir(options)
    slug   = options.get("tool_slug", "dnsx")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol   = policy.get("input_policy", {})
    rcons  = policy.get("runtime_constraints", {})
    exe    = resolve_bin("dnsx", "dnsx.exe")
    if not exe:
        return finalize("error","dnsx not installed or not on PATH",options,"dnsx",t0,"",error_reason="NOT_INSTALLED")

    raw_targets,_ = read_targets(options, accept_keys=tuple(ipol.get("accepts") or ("domains","hosts")), file_max_bytes=ipol.get("file_max_bytes",200_000), cap=ipol.get("max_targets",50))
    if not raw_targets:
        raise ValidationError("At least one domain/host is required.","INVALID_PARAMS","no input")
    valid, invalid = classify_domains(raw_targets)  # treat as hostnames where possible
    if invalid and not valid:
        raise ValidationError("No valid domains/hosts.","INVALID_PARAMS",", ".join(invalid[:10]))

    timeout_s = min(clamp_from_constraints(options,"timeout_s", rcons.get("timeout_s"), default=30, kind="int") or 30, HARD_TIMEOUT)
    threads   = clamp_from_constraints(options,"threads",   rcons.get("threads"),   default=50, kind="int") or 50

    args = [exe, "-silent", "-resp", "-retry", "2", "-t", str(threads), "-timeout", str(timeout_s)]
    if len(valid) <= 5:
        for d in valid: args += ["-d", d]
    else:
        fp = Path(work_dir)/"dnsx_targets.txt"; fp.write_text("\n".join(valid), "utf-8")
        args += ["-l", str(fp)]

    rc, out, ms = run_cmd(args, timeout_s=timeout_s, cwd=work_dir)
    outfile = write_output_file(work_dir, "dnsx_output.txt", out or "")
    lines = [(ln or "").strip() for ln in (out or "").splitlines() if ln.strip()]

    ips = []
    doms = []
    ip_re = re.compile(rf"(?:{IPV4_RE.pattern})|(?:{IPV6_RE.pattern})", re.I)
    for ln in lines:
        # dnsx often prints "sub.example.com [A] 1.2.3.4" or tab-separated
        parts = re.split(r"\s+", ln)
        if parts:
            doms.append(parts[0])
        for m in ip_re.findall(ln):
            ips.append(m)

    good, _, _ = classify_domains(doms)
    status = "ok" if rc == 0 else "error"
    msg = f"Resolved {len(good)} names, {len(ips)} IPs" if rc == 0 else f"dnsx error (exit={rc})"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    domains=good, ips=ips, error_reason=None if rc==0 else "OTHER")
