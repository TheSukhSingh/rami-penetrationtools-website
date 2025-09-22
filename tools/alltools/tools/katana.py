# tools/alltools/tools/katana.py
from __future__ import annotations
import subprocess
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms, URL_RE
)

DEFAULT_TIMEOUT = 90

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    seeds, _ = read_targets_from_options(options)

    bin_path = resolve_bin("katana")
    print("→ Using katana at:", bin_path)

    if not bin_path:
        return finalize("error", "katana not found in PATH", options, "katana -silent", t0, "", error_reason="INVALID_PARAMS")
    if not seeds:
        return finalize("error", "no seeds", options, "katana", t0, "", error_reason="INVALID_PARAMS")

    cmd = [bin_path, "-silent"]
    try:
        proc = subprocess.run(
            cmd, input="\n".join(seeds), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout
        ofile = write_output_file(work_dir, "katana_out.txt", raw)
        urls = [ln.strip() for ln in raw.splitlines() if URL_RE.search(ln)]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "katana exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, urls=urls)
    except subprocess.TimeoutExpired:
        return finalize("error", "katana timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"katana failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
