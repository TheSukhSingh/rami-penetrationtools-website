# tools/alltools/tools/gospider.py
from __future__ import annotations
import subprocess
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms, URL_RE
)
from tools.policies import get_effective_policy, clamp_from_constraints
from ._common import read_targets

DEFAULT_TIMEOUT = 90

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)

    slug   = options.get("tool_slug", "gospider")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol   = policy.get("input_policy", {})
    rcons  = policy.get("runtime_constraints", {})
    bins   = (policy.get("binaries") or {}).get("names") or ["gospider"]

    seeds, _ = read_targets(
        options,
        accept_keys=tuple(ipol.get("accepts") or ("urls","domains")),
        file_max_bytes=ipol.get("file_max_bytes", 200_000),
        cap=ipol.get("max_targets", 200),
    )

    bin_path = None
    for b in bins:
        bin_path = resolve_bin(b)
        if bin_path:
            break

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
            timeout=clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=DEFAULT_TIMEOUT, kind="int")

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
