import shutil
import subprocess
import os
import time
import dotenv
from tools.alltools._manifest_utils import split_typed, finalize_manifest

dotenv.load_dotenv()

def run_scan(data):
    print("→ Using github-subdomains at:", shutil.which("github-subdomains"))

    GSD_BIN = r"/usr/local/bin/github-subdomains"
    command = [GSD_BIN]

    target = data.get("github-url", "").strip()
    if not target:
        return {"status":"error","message":"Missing repo URL (github-url)","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"Provide a GitHub repository URL"}

    if data.get("github-raw","").strip().lower() == "yes":
        command.append("--raw")
    if data.get("github-extended","").strip().lower() == "yes":
        command.append("--extended")
    if data.get("github-exit-disabled","").strip().lower() == "yes":
        command.append("--exit-on-ratelimit")

    command.extend([target])
    command_str = " ".join(command)

    start = time.time()
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        execution_ms = int((time.time() - start) * 1000)

        stdout = result.stdout.strip() or "No output captured."
        if result.returncode != 0:
            return {"status":"error","message":f"Github subdomain error:\n{stdout}","execution_ms":execution_ms,"error_reason":"OTHER","error_detail":stdout}

        lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
        typed = split_typed(lines)
        parsed = {"domains": typed["domains"]}
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
        return finalize_manifest(slug="github_subdomains", options=data, command_str=command_str, started_at=start, stdout=stdout, parsed=parsed, primary="domains", extra=extra)
    except FileNotFoundError:
        return {"status":"error","message":"github-subdomains not found.","execution_ms":0,"error_reason":"INVALID_PARAMS","error_detail":"binary not found"}
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {"status":"error","message":"Github subdomain timed out.","execution_ms":execution_ms,"error_reason":"TIMEOUT","error_detail":"Subprocess timed out"}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}","execution_ms":int((time.time() - start) * 1000),"error_reason":"OTHER","error_detail":str(e)}
