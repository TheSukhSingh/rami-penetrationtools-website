import os
from tools.utils.domain_classification import classify_lines
import subprocess
import shutil
import time
from tools.alltools._manifest_utils import split_typed, finalize_manifest


def run_scan(data):
    print("→ Using subfinder at:", shutil.which("subfinder"))

    SUBFINDER_BIN = r"/usr/local/bin/subfinder"
    total_domain_count = valid_domain_count = invalid_domain_count = duplicate_domain_count = 0
    file_size_b = None
    method = data.get('input_method', 'manual')

    if method == 'file':
        filepath = data.get('file_path', '')
        if not filepath or not os.path.exists(filepath):
            return {
                "status": "error",
                "message": "Upload file not found.",
                "total_domain_count": None,
                "valid_domain_count": None,
                "invalid_domain_count": None,
                "duplicate_domain_count": None,
                "file_size_b": file_size_b,
                "execution_ms": 0,
                "error_reason": "INVALID_PARAMS",
                "error_detail": "Missing or inaccessible file",
                "value_entered": None
            }
        file_size_b = os.path.getsize(filepath)
        if file_size_b > 100_000:
            return {
                "status": "error",
                "message": f"Uploaded file too large ({file_size_b} bytes)",
                "total_domain_count": None,
                "valid_domain_count": None,
                "invalid_domain_count": None,
                "duplicate_domain_count": None,
                "file_size_b": file_size_b,
                "execution_ms": 0,
                "error_reason": "FILE_TOO_LARGE",
                "error_detail": f"{file_size_b} > 100000 bytes limit",
                "value_entered": file_size_b
            }
        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        if invalid:
            return {"status": "error", "message": f"{len(invalid)} invalid domains", "execution_ms": 0, "error_reason": "INVALID_PARAMS", "error_detail": ", ".join(invalid[:10])}
        if len(valid) > 50:
            return {"status": "error", "message": f"Too many domains: {len(valid)} (max 50)", "execution_ms": 0, "error_reason": "TOO_MANY_DOMAINS", "error_detail": f"{len(valid)} > 50"}
        targets = "\n".join(valid)
        valid_domain_count, invalid_domain_count = len(valid), len(invalid) if invalid else 0
    else:
        raw = data.get("subfinder-manual", "")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        if not valid:
            return {"status": "error", "message": "At least one valid domain is required.", "execution_ms": 0, "error_reason": "INVALID_PARAMS", "error_detail": "No valid domains"}
        if len(valid) > 50:
            return {"status": "error", "message": f"Too many domains: {len(valid)} (max 50)", "execution_ms": 0, "error_reason": "TOO_MANY_DOMAINS", "error_detail": f"{len(valid)} > 50"}
        targets = "\n".join(valid)
        valid_domain_count, invalid_domain_count = len(valid), len(invalid)

    command = [SUBFINDER_BIN, "-silent"]
    if (data.get("subfinder-all","").strip().lower() == "yes"):
        command.append("-all")
    if (data.get("subfinder-silent","").strip().lower() == "yes"):
        command.append("-silent")
    timeout = (data.get("subfinder-timeout") or "").strip() or "10"
    threads = (data.get("subfinder-threads") or "").strip() or "20"
    if timeout: command += ["-timeout", timeout]
    if threads: command += ["-t", threads]
    command_str = " ".join(command)

    start = time.time()
    try:
        result = subprocess.run(command, input=targets, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)
        stdout = result.stdout.strip() or "No output captured."
        if result.returncode != 0:
            return {"status": "error", "message": f"subfinder error:\n{stdout}", "execution_ms": execution_ms, "error_reason": "OTHER", "error_detail": stdout}

        typed = split_typed(stdout.splitlines())
        parsed = {"domains": typed["domains"]}
        extra = {
            "total_domain_count": total_domain_count,
            "valid_domain_count": valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count": duplicate_domain_count,
            "file_size_b": file_size_b,
            "execution_ms": execution_ms,
            "error_reason": None,
            "error_detail": None,
            "value_entered": None,
        }
        return finalize_manifest(slug="subfinder", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="domains", extra=extra)
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status": "error", "message": "subfinder timed out.", "execution_ms": execution_ms, "error_reason": "TIMEOUT", "error_detail": "Subprocess timed out"}
    except FileNotFoundError:
        return {"status": "error", "message": "subfinder is not installed.", "execution_ms": 0, "error_reason": "INVALID_PARAMS", "error_detail": "binary not found"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {e}", "execution_ms": int((time.time() - start) * 1000), "error_reason": "OTHER", "error_detail": str(e)}
