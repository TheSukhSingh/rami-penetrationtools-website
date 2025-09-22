from tools.utils.domain_classification import classify_lines
import shutil
import subprocess
import os
import time
from tools.alltools._manifest_utils import split_typed, finalize_manifest


def run_scan(data):
    print("→ Using naabu at:", shutil.which("naabu"))

    NAABU_BIN = r"/usr/local/bin/naabu"

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
        if invalid:
            return {"status":"error","message":f"{len(invalid)} invalid hosts.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":", ".join(invalid[:10])}
        targets = "\n".join(valid)
        valid_domain_count, invalid_domain_count = len(valid), len(invalid) if invalid else 0
    else:
        raw = data.get("naabu-manual", "")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        total_domain_count = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        if not valid:
            return {"status":"error","message":"At least one valid host is required.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"No valid hosts"}
        targets = "\n".join(valid)
        valid_domain_count, invalid_domain_count = len(valid), len(invalid)

    command = [NAABU_BIN, "-silent"]
    rate = (data.get("naabu-rate") or "").strip() or ""
    timeout = (data.get("naabu-timeout") or "").strip() or ""
    if data.get("naabu-silent","").strip().lower() == "yes": command.append("-silent")
    if data.get("naabu-top-ports","").strip(): command += ["-top-ports", data.get("naabu-top-ports").strip()]
    if rate: command += ["-rate", rate]
    if timeout: command += ["-timeout", timeout]
    command_str = " ".join(command)

    start = time.time()
    try:
        result = subprocess.run(command, input=targets, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)
        stdout = result.stdout.strip() or "No output captured."
        if result.returncode != 0:
            return {"status":"error","message":f"naabu error:\n{stdout}","execution_ms":execution_ms,"error_reason":"OTHER","error_detail":stdout}

        typed = split_typed(stdout.splitlines())
        parsed = {"ports": typed["ports"], "hosts": typed["hosts"], "ips": typed["ips"]}
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
        return finalize_manifest(slug="naabu", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="ports" if parsed["ports"] else "hosts", extra=extra)
    except FileNotFoundError:
        return {"status":"error","message":"naabu not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"binary not found"}
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status":"error","message":"naabu timed out.","execution_ms":execution_ms,"error_reason":"TIMEOUT","error_detail":"Subprocess timed out"}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}","execution_ms":int((time.time() - start) * 1000),"error_reason":"OTHER","error_detail":str(e)}
