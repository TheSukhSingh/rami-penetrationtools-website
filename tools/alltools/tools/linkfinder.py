import shutil
import subprocess
import time
from tools.utils.domain_classification import classify_lines
from tools.alltools._manifest_utils import split_typed, finalize_manifest

def run_scan(data):
    print("→ Using linkfinder at:", shutil.which("linkfinder"))
    command = ["linkfinder"]

    domain = data.get("linkfinder-domain", "").strip()
    if not domain:
        return {"status":"error","message":"At least one domain is required.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"Missing linkfinder-domain"}

    command.extend(["-i", domain])

    regex = data.get("linkfinder-regex", "").strip()
    if regex:
        command.extend(["-r", regex])

    cookies = data.get("linkfinder-cookies", "").strip()
    if cookies:
        command.extend(["-c", cookies])

    timeout = data.get("linkfinder-timeout", "").strip() or "10"
    try:
        t = int(timeout)
        if not (2 <= t <= 60):
            raise ValueError
    except ValueError:
        return {"status":"error","message":"Timeout must be between 2-60 seconds","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"Timeout must be 2-60"}
    command.extend(["-t", str(timeout)])

    command_str = " ".join(command)
    start = time.time()
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)

        stdout = result.stdout.strip() or "No output captured."
        if result.returncode != 0:
            return {"status":"error","message":f"linkfinder error:\n{stdout}","execution_ms":execution_ms,"error_reason":"OTHER","error_detail":stdout}

        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        typed = split_typed(lines)
        parsed = {"endpoints": typed["endpoints"]}
        extra = {
            "total_domain_count": None,
            "valid_domain_count": None,
            "invalid_domain_count": None,
            "duplicate_domain_count": None,
            "file_size_b": None,
            "execution_ms": execution_ms,
            "error_reason": None,
            "error_detail": None,
            "value_entered": None,
        }
        return finalize_manifest(slug="linkfinder", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="endpoints", extra=extra)
    except FileNotFoundError:
        return {"status":"error","message":"linkfinder not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"binary not found"}
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status":"error","message":"linkfinder timed out.","execution_ms":execution_ms,"error_reason":"TIMEOUT","error_detail":"Subprocess timed out"}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}","execution_ms":int((time.time() - start) * 1000),"error_reason":"OTHER","error_detail":str(e)}
