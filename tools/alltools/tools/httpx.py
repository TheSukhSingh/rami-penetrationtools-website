# tools/alltools/tools/httpx.py
from __future__ import annotations
import subprocess, os
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms, URL_RE
)
from tools.policies import get_effective_policy, clamp_from_constraints
from ._common import read_targets  # we’ll use the file cap from policy

DEFAULT_TIMEOUT = 45  # seconds

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)

    # policy
    slug   = options.get("tool_slug", "httpx")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol   = policy.get("input_policy", {})
    rcons  = policy.get("runtime_constraints", {})
    bins   = (policy.get("binaries") or {}).get("names") or ["httpx"]

    # inputs (prefer urls, allow hosts/domains fallback)
    targets, src = read_targets(
        options,
        accept_keys=tuple(ipol.get("accepts") or ("urls","hosts","domains")),
        file_max_bytes=ipol.get("file_max_bytes", 200_000),
        cap=ipol.get("max_targets", 200),
    )


    bin_path = None
    for b in bins:
        bin_path = resolve_bin(b)
        if bin_path:
            break

    if not bin_path:
        return finalize(
            "error", "httpx not found in PATH",
            options, "httpx -silent -nc", t0, "",
            error_reason="INVALID_PARAMS"
        )

    if not targets:
        return finalize("error", "no input targets", options, "httpx", t0, "", error_reason="INVALID_PARAMS")
    
    timeout_s = clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=DEFAULT_TIMEOUT, kind="int")
    cmd = [bin_path, "-silent", "-nc"]  # -nc = no color
    try:
        proc = subprocess.run(
            cmd, input="\n".join(targets), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout = timeout_s
        )
        raw = proc.stdout.strip()
        ofile = write_output_file(work_dir, "httpx_out.txt", raw + ("\n" if raw else ""))
        urls = [m.group(0).strip() for m in URL_RE.finditer(raw)]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "httpx exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, urls=urls)
    except subprocess.TimeoutExpired:
        return finalize("error", "httpx timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except FileNotFoundError:
        return finalize("error", "httpx not found", options, " ".join(cmd), t0, "", error_reason="INVALID_PARAMS")
    except Exception as e:
        return finalize("error", f"httpx failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
