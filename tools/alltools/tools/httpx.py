# tools/alltools/tools/httpx.py
from __future__ import annotations
from pathlib import Path
import os
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, run_cmd, write_output_file,
    finalize, ValidationError, URL_RE
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT=300

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed*1000) if hasattr(os,"times") else 0
    work_dir = ensure_work_dir(options)
    slug = options.get("tool_slug","httpx")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy",{})
    rcons = policy.get("runtime_constraints",{})
    exe = resolve_bin("httpx","httpx.exe")
    if not exe:
        return finalize("error","httpx not installed",options,"httpx",t0,"",error_reason="NOT_INSTALLED")

    raw,_ = read_targets(options, accept_keys=tuple(ipol.get("accepts") or ("urls","hosts","domains")),
                         file_max_bytes=ipol.get("file_max_bytes",200_000), cap=ipol.get("max_targets",500))
    if not raw: raise ValidationError("At least one URL/host/domain is required.","INVALID_PARAMS","no input")

    timeout_s = min(clamp_from_constraints(options,"timeout_s", rcons.get("timeout_s"), default=20, kind="int") or 20, HARD_TIMEOUT)
    threads   = clamp_from_constraints(options,"threads",   rcons.get("threads"),   default=50, kind="int") or 50
    follow    = bool(options.get("follow_redirects", False))

    args = [exe, "-silent", "-nc", "-t", str(threads), "-timeout", str(timeout_s)]
    if follow: args.append("-follow-redirects")

    # httpx accepts -u (repeat) or -l file
    if len(raw) <= 5:
        for t in raw: args += ["-u", t]
    else:
        fp = Path(work_dir)/"httpx_targets.txt"; fp.write_text("\n".join(raw), "utf-8")
        args += ["-l", str(fp)]

    rc, out, ms = run_cmd(args, timeout_s=timeout_s, cwd=work_dir)
    outfile = write_output_file(work_dir, "httpx_output.txt", out or "")
    urls = [m.group(0) for m in URL_RE.finditer(out or "")]
    status = "ok" if rc==0 else "error"
    return finalize(status, f"{len(urls)} alive", options, " ".join(args), t0, out, output_file=outfile,
                    urls=urls, error_reason=None if rc==0 else "OTHER")
