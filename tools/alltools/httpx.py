from tools.utils.domain_classification import classify_lines
import shutil
import subprocess
import os
import time
from tools.alltools._manifest_utils import split_typed, finalize_manifest


def run_scan(data):
    print("→ Using httpx at:", shutil.which("httpx"))

    HTTPX_BIN = r"/usr/local/bin/httpx"
    total_domain_count = valid_domain_count = invalid_domain_count = duplicate_domain_count = 0
    file_size_b = None
    method = data.get('input_method', 'manual')

    if method == 'file':
        filepath = data.get('file_path', '')
        if not filepath or not os.path.exists(filepath):
            return {"status":"error","message":"Upload file not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"Missing or inaccessible file"}
        file_size_b = os.path.getsize(filepath)
        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        if not valid:
            return {"status":"error","message":"No valid targets in file.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"No valid lines"}
        targets = "\n".join(valid)
        valid_domain_count, invalid_domain_count = len(valid), len(invalid) if invalid else 0
    else:
        raw = data.get("httpx-manual", "")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        if not valid:
            return {"status":"error","message":"At least one valid target is required.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"No valid targets"}
        targets = "\n".join(valid)
        valid_domain_count, invalid_domain_count = len(valid), len(invalid)

    command = [HTTPX_BIN, "-silent", "-nc"]
    if data.get("httpx-silent","").strip().lower() == "yes": command.append("-silent")
    if data.get("httpx-status-code","").strip().lower() == "yes": command.append("-status-code")
    if data.get("httpx-title","").strip().lower() == "yes": command.append("-title")
    threads = (data.get("httpx-threads") or "").strip()
    timeout = (data.get("httpx-timeout") or "").strip()
    if threads: command += ["-t", threads]
    if timeout: command += ["-timeout", timeout]

    command_str = " ".join(command)

    start = time.time()
    try:
        result = subprocess.run(command, input=targets, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)
        stdout = result.stdout.strip() or "No output captured."
        if result.returncode != 0:
            return {"status":"error","message":f"httpx error:\n{stdout}","execution_ms":execution_ms,"error_reason":"OTHER","error_detail":stdout}

        typed = split_typed(stdout.splitlines())
        parsed = {"urls": typed["urls"]}
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
        return finalize_manifest(slug="httpx", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="urls", extra=extra)
    except FileNotFoundError:
        return {"status":"error","message":"httpx not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"binary not found"}
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status":"error","message":"httpx timed out.","execution_ms":execution_ms,"error_reason":"TIMEOUT","error_detail":"Subprocess timed out"}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}","execution_ms":int((time.time() - start) * 1000),"error_reason":"OTHER","error_detail":str(e)}
