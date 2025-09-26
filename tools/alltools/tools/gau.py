# tools/alltools/tools/gau.py
from __future__ import annotations
import os, subprocess, shlex
from ._common import ensure_work_dir, read_targets, write_output_file, finalize, ValidationError, URL_RE, resolve_bin

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed*1000) if hasattr(os,"times") else 0
    work_dir = ensure_work_dir(options)
    slug="gau"
    exe = resolve_bin("gau","gau.exe")
    if not exe:
        return finalize("error","gau not installed",options,"gau",t0,"",error_reason="NOT_INSTALLED")

    raw,_ = read_targets(options, accept_keys=("domains","hosts"), cap=100)
    if not raw: raise ValidationError("At least one domain is required.","INVALID_PARAMS","no input")
    domain = raw[0]
    subs = bool(options.get("subs", True))

    # echo domain | gau [-subs]
    cmd = f'echo {shlex.quote(domain)} | "{exe}"' + (" -subs" if subs else "")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(work_dir))
        out = (res.stdout or "")
        rc = res.returncode
    except Exception as e:
        return finalize("error","Failed to execute gau",options,"gau",t0,str(e),error_reason="OTHER",error_detail=repr(e))

    outfile = write_output_file(work_dir, "gau_output.txt", out or "")
    urls = [m.group(0) for m in URL_RE.finditer(out or "")]
    status="ok" if rc==0 else "error"
    return finalize(status, f"{len(urls)} URLs", options, cmd, t0, out, output_file=outfile,
                    urls=urls, error_reason=None if rc==0 else "OTHER")
