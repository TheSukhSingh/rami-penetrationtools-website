# tools/alltools/tools/naabu.py
from __future__ import annotations
from pathlib import Path
import os, re
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, run_cmd, write_output_file,
    finalize, ValidationError, IPV4_RE
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT=600

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed*1000) if hasattr(os,"times") else 0
    work_dir = ensure_work_dir(options)
    slug = options.get("tool_slug","naabu")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy",{})
    rcons= policy.get("runtime_constraints",{})
    exe = resolve_bin("naabu","naabu.exe")
    if not exe:
        return finalize("error","naabu not installed",options,"naabu",t0,"",error_reason="NOT_INSTALLED")

    raw,_ = read_targets(options, accept_keys=tuple(ipol.get("accepts") or ("hosts","ips","domains")),
                         file_max_bytes=ipol.get("file_max_bytes",200_000), cap=ipol.get("max_targets",1000))
    if not raw: raise ValidationError("At least one host/IP/domain is required.","INVALID_PARAMS","no input")

    timeout_s = min(clamp_from_constraints(options,"timeout_s", rcons.get("timeout_s"), default=60, kind="int") or 60, HARD_TIMEOUT)
    rate      = clamp_from_constraints(options,"rate",      rcons.get("rate"),      default=1000, kind="int") or 1000
    ports_arg = (options.get("ports") or "").strip()  # pass-through to naabu -p

    args = [exe, "-silent", "-nc", "-rate", str(rate), "-timeout", str(timeout_s)]
    if ports_arg: args += ["-p", ports_arg]

    if len(raw) <= 5:
        for t in raw: args += ["-host", t]
    else:
        fp = Path(work_dir)/"naabu_targets.txt"; fp.write_text("\n".join(raw), "utf-8")
        args += ["-l", str(fp)]

    rc, out, ms = run_cmd(args, timeout_s=timeout_s, cwd=work_dir)
    outfile = write_output_file(work_dir, "naabu_output.txt", out or "")
    # format usually host:port
    services = []
    ports = set()
    for ln in (out or "").splitlines():
        ln = ln.strip()
        if not ln or ":" not in ln: continue
        services.append(ln)
        try:
            p = int(ln.rsplit(":",1)[-1])
            if 0<p<65536: ports.add(p)
        except: pass

    status = "ok" if rc==0 else "error"
    return finalize(status, f"{len(services)} open services", options, " ".join(args), t0, out, output_file=outfile,
                    services=services, ports=[str(p) for p in sorted(ports)], error_reason=None if rc==0 else "OTHER")
