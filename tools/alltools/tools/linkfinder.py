# tools/alltools/tools/linkfinder.py
from __future__ import annotations
import subprocess, shlex
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints
from ._common import read_targets

DEFAULT_TIMEOUT = 60

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    slug   = options.get("tool_slug", "linkfinder")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol   = policy.get("input_policy", {})
    rcons  = policy.get("runtime_constraints", {})
    bins   = (policy.get("binaries") or {}).get("names") or ["linkfinder"]

    urls, _ = read_targets(
        options,
        accept_keys=tuple(ipol.get("accepts") or ("urls",)),
        file_max_bytes=ipol.get("file_max_bytes", 200_000),
        cap=ipol.get("max_targets", 200),
    )


    bin_path = None
    for b in bins:
        bin_path = resolve_bin(b)
        if bin_path:
            break

    if not bin_path:
        return finalize("error", "linkfinder not found in PATH", options, "linkfinder -i <url> -o cli", t0, "", error_reason="INVALID_PARAMS")
    if not urls:
        return finalize("error", "no input urls", options, "linkfinder", t0, "", error_reason="INVALID_PARAMS")

    endpoints = []
    raw_agg = []
    # Run per-URL to keep output clean (it’s usually fast)
    for u in urls:
        cmd = [bin_path, "-i", u, "-o", "cli"]
        try:
            proc = subprocess.run(
                cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=DEFAULT_TIMEOUT, kind="int")

            )
            raw_agg.append(proc.stdout)
            # linkfinder CLI outputs one path per line
            for ln in proc.stdout.splitlines():
                ln = ln.strip()
                if ln:
                    endpoints.append(ln)
        except subprocess.TimeoutExpired:
            raw_agg.append(f"[timeout] {u}")
        except Exception as e:
            raw_agg.append(f"[error:{e}] {u}")

    raw = "\n".join(raw_agg)
    ofile = write_output_file(work_dir, "linkfinder_out.txt", raw + ("\n" if raw else ""))
    return finalize("success", "ok", options, "linkfinder -i <url> -o cli", t0, raw, ofile, endpoints=endpoints)
