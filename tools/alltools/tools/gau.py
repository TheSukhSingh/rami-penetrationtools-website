# tools/alltools/tools/gau.py
from __future__ import annotations
import subprocess
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms, URL_RE
)

DEFAULT_TIMEOUT = 60

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    targets, _ = read_targets_from_options(options)

    bin_path = resolve_bin("gau")
    print("→ Using gau at:", bin_path)

    if not bin_path:
        return finalize("error", "gau not found in PATH", options, "gau -silent", t0, "", error_reason="INVALID_PARAMS")
    if not targets:
        return finalize("error", "no input domains", options, "gau", t0, "", error_reason="INVALID_PARAMS")

    cmd = [bin_path, "-silent"]
    try:
        proc = subprocess.run(
            cmd, input="\n".join(targets), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout.strip()
        ofile = write_output_file(work_dir, "gau_out.txt", raw + ("\n" if raw else ""))
        urls = [ln.strip() for ln in raw.splitlines() if URL_RE.search(ln)]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "gau exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, urls=urls)
    except subprocess.TimeoutExpired:
        return finalize("error", "gau timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"gau failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
