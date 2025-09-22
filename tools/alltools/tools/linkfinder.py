# tools/alltools/tools/linkfinder.py
from __future__ import annotations
import subprocess, shlex
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms
)

DEFAULT_TIMEOUT = 60

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    urls, _ = read_targets_from_options(options)

    # LinkFinder is a Python CLI; commonly "linkfinder"
    bin_path = resolve_bin("linkfinder")
    print("→ Using linkfinder at:", bin_path)

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
                timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
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
