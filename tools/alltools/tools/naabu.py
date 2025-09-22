# tools/alltools/tools/naabu.py
from __future__ import annotations
import subprocess
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms
)

DEFAULT_TIMEOUT = 60

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    targets, _ = read_targets_from_options(options)

    bin_path = resolve_bin("naabu")
    print("→ Using naabu at:", bin_path)

    if not bin_path:
        return finalize("error", "naabu not found in PATH", options, "naabu -silent -top-ports 100", t0, "", error_reason="INVALID_PARAMS")
    if not targets:
        return finalize("error", "no input hosts", options, "naabu", t0, "", error_reason="INVALID_PARAMS")

    ports_arg = options.get("ports")  # e.g., "80,443,8080"
    cmd = [bin_path, "-silent"]
    if ports_arg:
        cmd += ["-p", str(ports_arg)]
    else:
        cmd += ["-top-ports", "100"]

    try:
        proc = subprocess.run(
            cmd, input="\n".join(targets), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout.strip()
        ofile = write_output_file(work_dir, "naabu_out.txt", raw + ("\n" if raw else ""))
        # naabu prints "host:port"
        ports = [ln.strip() for ln in raw.splitlines() if ":" in ln]
        hosts = [ln.split(":")[0].strip() for ln in ports]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "naabu exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, ports=ports, hosts=list(dict.fromkeys(hosts)))
    except subprocess.TimeoutExpired:
        return finalize("error", "naabu timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"naabu failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
