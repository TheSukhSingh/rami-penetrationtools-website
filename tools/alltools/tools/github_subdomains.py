# tools/alltools/tools/github_subdomains.py
from __future__ import annotations
import subprocess, os
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms
)

DEFAULT_TIMEOUT = 60

def run_scan(options: dict) -> dict:
    """
    Uses a CLI named `github-subdomains` if present. If you use another tool,
    change the binary name and args below accordingly.
    """
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    targets, _ = read_targets_from_options(options)  # orgs or root domains depending on your tool

    bin_path = resolve_bin("github-subdomains", "github_subdomains")
    print("→ Using github_subdomains at:", bin_path)

    if not bin_path:
        return finalize("error", "github-subdomains not found in PATH", options, "github-subdomains", t0, "", error_reason="INVALID_PARAMS")
    if not targets:
        return finalize("error", "no input", options, "github-subdomains", t0, "", error_reason="INVALID_PARAMS")

    # Most CLI variants read targets from stdin and output subdomains
    cmd = [bin_path]
    try:
        proc = subprocess.run(
            cmd, input="\n".join(targets), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout.strip()
        ofile = write_output_file(work_dir, "github_subdomains_out.txt", raw + ("\n" if raw else ""))
        domains = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "github-subdomains exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, domains=domains)
    except subprocess.TimeoutExpired:
        return finalize("error", "github-subdomains timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"github-subdomains failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
