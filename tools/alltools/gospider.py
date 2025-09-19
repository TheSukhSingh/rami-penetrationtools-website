import shutil
import subprocess
import os
import time
from tools.utils.domain_classification import classify_lines
from tools.alltools._manifest_utils import split_typed, finalize_manifest

def run_scan(data):
    print("→ Using gospider at:", shutil.which("gospider"))

    GOSPIDER_BIN = r"/usr/local/bin/gospider"
    total_domain_count = valid_domain_count = invalid_domain_count = duplicate_domain_count = 0
    file_size_b = None
    method = data.get('input_method', 'manual')
    command = [GOSPIDER_BIN]

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
        raw = data.get("gospider-manual", "")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        targets = "\n".join(valid or lines)
        valid_domain_count, invalid_domain_count = len(valid or lines), len(invalid or [])

    if data.get("gospider-u","").strip(): command += ["-u", data.get("gospider-u").strip()]
    if data.get("gospider-m","").strip(): command += ["-m", data.get("gospider-m").strip()]
    if data.get("gospider-p","").strip(): command += ["-p", data.get("gospider-p").strip()]
    if data.get("gospider-d","").strip(): command += ["-d", data.get("gospider-d").strip()]
    if data.get("gospider-subs","").strip().lower() == "yes": command.append("--subs")
    if data.get("gospider-c","").strip(): command += ["-c", data.get("gospider-c").strip()]
    if data.get("gospider-threads","").strip(): command += ["-t", data.get("gospider-threads").strip()]

    command_str = " ".join(command)
    start = time.time()
    try:
        result = subprocess.run(command, input=targets, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)
        stdout = result.stdout.strip() or "No output captured."

        if result.returncode != 0:
            return {"status":"error","message":f"gospider error:\n{stdout}","execution_ms":execution_ms,"error_reason":"OTHER","error_detail":stdout}

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
        return finalize_manifest(slug="gospider", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="urls" if parsed["urls"] else "endpoints", extra=extra)
    except FileNotFoundError:
        return {"status":"error","message":"gospider not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"binary not found"}
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status":"error","message":"gospider timed out.","execution_ms":execution_ms,"error_reason":"TIMEOUT","error_detail":"Subprocess timed out"}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}","execution_ms":int((time.time() - start) * 1000),"error_reason":"OTHER","error_detail":str(e)}
