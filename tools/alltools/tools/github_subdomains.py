# tools/alltools/tools/github_subdomains.py
from __future__ import annotations
import os, re, time, json
from pathlib import Path
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, run_cmd, write_output_file,
    finalize, ValidationError, classify_domains
)
import subprocess

HARD_TIMEOUT=300

def _fallback_github_api(dom: str, token: str, work_dir: Path, t0: int, options: dict):
    """
    Very small fallback: uses 'gh api' if installed OR curl via subprocess.
    Searches code for the domain string and extracts subdomains by regex.
    """
    # Prefer gh if available
    gh = resolve_bin("gh","gh.exe")
    headers = f"Authorization: token {token}"
    q = f'"{dom}" in:file'  # keep this mild
    urls=[]
    if gh:
        cmd = [gh, "api", "-H", headers, "/search/code", "-f", f"q={q}", "-f", "per_page=50"]
        rc,out,ms = run_cmd(cmd, timeout_s=HARD_TIMEOUT, cwd=work_dir)
        if rc==0:
            try:
                data = json.loads(out)
                for item in data.get("items", []):
                    # pull_text_url if present; otherwise skip
                    pass
            except: pass
        raw = out or ""
    else:
        # curl fallback
        curl = resolve_bin("curl","curl.exe")
        if not curl:
            return finalize("error","Neither github-subdomains nor 'gh' nor 'curl' available",
                            options,"github-subdomains",t0,"",error_reason="NOT_INSTALLED")
        api = f"https://api.github.com/search/code?q={dom}+in:file&per_page=50"
        rc,out,ms = run_cmd([curl,"-s","-H",headers,api], timeout_s=HARD_TIMEOUT, cwd=work_dir)
        raw = out or ""

    # very light regex just to get subdomains
    sub_re = re.compile(rf"(?:[a-z0-9-]+\.)+{re.escape(dom)}", re.I)
    candidates = list(dict.fromkeys(sub_re.findall(raw)))
    good, bad = classify_domains(candidates)
    return finalize("ok", f"{len(good)} candidates (API fallback)", options, "github-api", t0, raw, domains=good)

def run_scan(options: dict) -> dict:
    t0 = int(os.times().elapsed*1000) if hasattr(os,"times") else 0
    work_dir = ensure_work_dir(options)
    slug="github-subdomains"
    token = options.get("github_token") or os.getenv("GITHUB_SUBDOMAINS_KEY")
    if not token:
        return finalize("error","Missing GitHub token (GITHUB_SUBDOMAINS_KEY).",options,"github-subdomains",t0,"",error_reason="INVALID_PARAMS", error_detail="set env or options.github_token")

    raw,_ = read_targets(options, accept_keys=("domains",), cap=5)
    if not raw: raise ValidationError("At least one root domain is required.","INVALID_PARAMS","no input")
    dom = raw[0]

    # Try the popular CLI if present
    exe = resolve_bin("github-subdomains","github-subdomains.exe")
    if exe:
        args = [exe, "-d", dom, "-t", token]
        rc,out,ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work_dir)
        outfile = write_output_file(work_dir, "github_subdomains_output.txt", out or "")
        lines = [(ln or "").strip() for ln in (out or "").splitlines() if ln.strip()]
        good,_ = classify_domains(lines)
        status="ok" if rc==0 else "error"
        return finalize(status, f"{len(good)} subdomains", options, " ".join(args), t0, out, output_file=outfile,
                        domains=good, error_reason=None if rc==0 else "OTHER")

    # Fallback to tiny API helper
    return _fallback_github_api(dom, token, work_dir, t0, options)
