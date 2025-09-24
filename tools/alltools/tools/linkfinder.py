# tools/alltools/tools/linkfinder.py
from __future__ import annotations
from pathlib import Path
import os, re
from ._common import resolve_bin, ensure_work_dir, read_targets, run_cmd, write_output_file, finalize, ValidationError, URL_RE
from tools.policies import get_effective_policy, clamp_from_constraints

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed*1000) if hasattr(os,"times") else 0
    work_dir = ensure_work_dir(options)
    slug="linkfinder"
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy",{})
    exe = resolve_bin("linkfinder","linkfinder.py")  # pip console-script or file
    if not exe:
        return finalize("error","linkfinder not installed",options,"linkfinder",t0,"",error_reason="NOT_INSTALLED")

    raw,_ = read_targets(options, accept_keys=tuple(ipol.get("accepts") or ("urls",)), cap=100)
    if not raw: raise ValidationError("At least one URL is required.","INVALID_PARAMS","no input")

    timeout_s = clamp_from_constraints(options,"timeout_s", None, default=120, kind="int") or 120

    if len(raw) == 1:
        args = [exe, "-i", raw[0], "-o", "cli", "-d"]
    else:
        fp = Path(work_dir)/"linkfinder_targets.txt"; fp.write_text("\n".join(raw), "utf-8")
        args = [exe, "-l", str(fp), "-o", "cli", "-d"]

    rc, out, ms = run_cmd(args, timeout_s=timeout_s, cwd=work_dir)
    outfile = write_output_file(work_dir, "linkfinder_output.txt", out or "")
    # LinkFinder CLI prints both absolute and relative endpoints; keep both, dedup inside finalize
    endpoints = [m.group(0) for m in URL_RE.finditer(out or "")]
    status="ok" if rc==0 else "error"
    return finalize(status, f"{len(endpoints)} endpoints", options, " ".join(args), t0, out, output_file=outfile,
                    endpoints=endpoints, error_reason=None if rc==0 else "OTHER")
