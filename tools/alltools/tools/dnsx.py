# tools/alltools/tools/dnsx.py
from __future__ import annotations
import subprocess
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms, IP_RE
)

DEFAULT_TIMEOUT = 45

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    targets, _ = read_targets_from_options(options)

    bin_path = resolve_bin("dnsx")
    print("→ Using dnsx at:", bin_path)

    if not bin_path:
        return finalize("error", "dnsx not found in PATH", options, "dnsx -silent -resp -a -aaaa", t0, "", error_reason="INVALID_PARAMS")
    if not targets:
        return finalize("error", "no input domains", options, "dnsx", t0, "", error_reason="INVALID_PARAMS")

    cmd = [bin_path, "-silent", "-resp", "-a", "-aaaa"]
    try:
        proc = subprocess.run(
            cmd, input="\n".join(targets), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout.strip()
        ofile = write_output_file(work_dir, "dnsx_out.txt", raw + ("\n" if raw else ""))
        domains, ips = [], []
        for line in raw.splitlines():
            parts = line.split()
            if parts:
                domains.append(parts[0].strip())
                ips.extend(IP_RE.findall(line))
        domains = [d for d in dict.fromkeys(domains)]
        ips = [ip for ip in dict.fromkeys(ips)]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "dnsx exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, domains=domains, ips=ips)
    except subprocess.TimeoutExpired:
        return finalize("error", "dnsx timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"dnsx failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
