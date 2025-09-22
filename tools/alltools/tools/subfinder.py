# tools/alltools/tools/subfinder.py
from __future__ import annotations
import subprocess, os
from pathlib import Path
from ._common import (
    resolve_bin, read_targets_from_options, ensure_work_dir,
    write_output_file, finalize, now_ms
)

DEFAULT_TIMEOUT = 60

def run_scan(options: dict) -> dict:
    """
    subfinder expects -d (single domain) or -dL (file of domains).
    We support both:
      - Manual input -> one domain => -d <domain>
      - Manual input -> many domains => write file + -dL <file>
      - File input -> use that file with -dL
    """
    t0 = now_ms()
    work_dir = ensure_work_dir(options)
    bin_path = resolve_bin("subfinder")
    print("→ Using subfinder at:", bin_path)

    if not bin_path:
        return finalize(
            "error", "subfinder not found in PATH",
            options, "subfinder -silent", t0, "",
            error_reason="INVALID_PARAMS"
        )

    # Load targets from options (manual or file)
    targets, src = read_targets_from_options(options)
    if not targets and not (options.get("input_method") == "file" and options.get("file_path")):
        return finalize("error", "no input root domains", options, "subfinder", t0, "", error_reason="INVALID_PARAMS")

    cmd = [bin_path, "-silent"]

    # If user gave a file explicitly, prefer that
    if options.get("input_method") == "file" and options.get("file_path") and os.path.exists(options["file_path"]):
        cmd += ["-dL", options["file_path"]]
    else:
        # Manual input: 1 domain -> -d; many -> write to file and use -dL
        if len(targets) == 1:
            cmd += ["-d", targets[0]]
        else:
            list_path = Path(work_dir) / "subfinder_input.txt"
            list_path.write_text("\n".join(targets), encoding="utf-8", errors="ignore")
            cmd += ["-dL", str(list_path)]

    # Optional flags
    if options.get("all_sources"):
        cmd.append("-all")
    if options.get("threads"):
        cmd += ["-t", str(options["threads"])]
    if options.get("timeout_s"):
        cmd += ["-timeout", str(int(options["timeout_s"]))]

    try:
        proc = subprocess.run(
            cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(options.get("timeout_s", DEFAULT_TIMEOUT))
        )
        raw = proc.stdout.strip()
        ofile = write_output_file(work_dir, "subfinder_out.txt", raw + ("\n" if raw else ""))
        domains = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        status = "success" if proc.returncode == 0 else "error"
        msg = "ok" if status == "success" else (proc.stderr.strip() or "subfinder exited non-zero")
        return finalize(status, msg, options, " ".join(cmd), t0, raw, ofile, domains=domains)
    except subprocess.TimeoutExpired:
        return finalize("error", "subfinder timed out", options, " ".join(cmd), t0, "", error_reason="TIMEOUT")
    except Exception as e:
        return finalize("error", f"subfinder failed: {e}", options, " ".join(cmd), t0, "", error_reason="EXECUTION_ERROR")
