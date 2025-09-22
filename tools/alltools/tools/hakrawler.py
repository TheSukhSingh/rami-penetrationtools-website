import shutil
import subprocess
import os
import time
from tools.utils.domain_classification import classify_lines
from tools.alltools._manifest_utils import split_typed, finalize_manifest


def run_scan(data):
    print("→ Using hakrawler at:", shutil.which("hakrawler"))

    HAKRAWLER_BIN = r"/usr/local/bin/hakrawler"
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
        targets = "\n".join(valid or lines)
        valid_domain_count, invalid_domain_count = len(valid or lines), len(invalid or [])
    else:
        raw = data.get("hakrawler-manual", "")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        targets = "\n".join(valid or lines)
        valid_domain_count, invalid_domain_count = len(valid or lines), len(invalid or [])

    command = [HAKRAWLER_BIN]
    if data.get("hakrawler-unique","").strip().lower() == "yes": command.append("-unique")
    if data.get("hakrawler-subs","").strip().lower() == "yes": command.append("-subs")
    if data.get("hakrawler-d","").strip(): command += ["-d", data.get("hakrawler-d").strip()]
    if data.get("hakrawler-threads","").strip(): command += ["-t", data.get("hakrawler-threads").strip()]
    if data.get("hakrawler-timeout","").strip(): command += ["-timeout", data.get("hakrawler-timeout").strip()]
    command_str = " ".join(command)

    start = time.time()
    try:
        result = subprocess.run(command, input=targets, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)
        stdout = result.stdout.strip() or "No output captured."
        if result.returncode != 0:
            return {"status":"error","message":f"hakrawler error:\n{stdout}","execution_ms":execution_ms,"error_reason":"OTHER","error_detail":stdout}

        typed = split_typed(stdout.splitlines())
        parsed = {"urls": typed["urls"], "endpoints": typed["endpoints"]}
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
        return finalize_manifest(slug="hakrawler", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="urls" if parsed["urls"] else "endpoints", extra=extra)
    except FileNotFoundError:
        return {"status":"error","message":"hakrawler not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"binary not found"}
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status":"error","message":"hakrawler timed out.","execution_ms":execution_ms,"error_reason":"TIMEOUT","error_detail":"Subprocess timed out"}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}","execution_ms":int((time.time() - start) * 1000),"error_reason":"OTHER","error_detail":str(e)}
