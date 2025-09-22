# tools/alltools/tools/gospider.py
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

    bin_path = resolve_bin("gospider")
    print("→ Using gospider at:", bin_path)

    if not bin_path:
        return finalize("error", "gospider not found in PATH", options, "gospider -S -", t0, "", error_reason="INVALID_PARAMS")
    if not seeds:
        return finalize("error", "no seeds", options, "gospider", t0, "", error_reason="INVALID_PARAMS")

    # -S - tells gospider to read seeds from stdin
    cmd = [bin_path, "-S", "-", "-a", "-q"]
    try:
        proc = subprocess.run(
            cmd, input="\n".join(seeds), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout
        ofile = write_output_file(work_dir, "gospider_out.txt", raw)
        urls = [m.group(0) for m in URL_RE.finditer(raw)]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "gospider exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, urls=urls)
    except subprocess.TimeoutExpired:
        return finalize("error", "gospider timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"gospider failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
