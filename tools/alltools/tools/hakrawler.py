# tools/alltools/tools/hakrawler.py
from __future__ import annotations
import os
from ._common import resolve_bin, ensure_work_dir, read_targets, run_cmd, write_output_file, finalize, ValidationError, URL_RE
from tools.policies import get_effective_policy, clamp_from_constraints

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed*1000) if hasattr(os,"times") else 0
    work_dir = ensure_work_dir(options)
    slug="hakrawler"
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy",{})
    exe = resolve_bin("hakrawler","hakrawler.exe")
    if not exe:
        return finalize("error","hakrawler not installed",options,"hakrawler",t0,"",error_reason="NOT_INSTALLED")

    raw,_ = read_targets(options, accept_keys=tuple(ipol.get("accepts") or ("urls","domains")), cap=50)
    if not raw: raise ValidationError("At least one URL/domain is required.","INVALID_PARAMS","no input")
    target = raw[0]  # see note above

    depth = clamp_from_constraints(options,"depth", None, default=2, kind="int") or 2
    timeout_s = clamp_from_constraints(options,"timeout_s", None, default=60, kind="int") or 60

    args = [exe, "-url", target, "-depth", str(depth), "-plain"]
    rc, out, ms = run_cmd(args, timeout_s=timeout_s, cwd=work_dir)
    outfile = write_output_file(work_dir, "hakrawler_output.txt", out or "")
    urls = [m.group(0) for m in URL_RE.finditer(out or "")]
    status="ok" if rc==0 else "error"
    return finalize(status, f"{len(urls)} URLs", options, " ".join(args), t0, out, output_file=outfile,
                    urls=urls, error_reason=None if rc==0 else "OTHER")
