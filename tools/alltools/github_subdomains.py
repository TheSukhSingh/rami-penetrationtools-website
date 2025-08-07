import shutil
import subprocess
import os
import time
from urllib.parse import urlparse
import dotenv

dotenv.load_dotenv()

def run_scan(data):
    print("→ Using github-subdomains at:", shutil.which("github-subdomains"))

    GSD_BIN = r"/usr/local/bin/github-subdomains"
    command = [GSD_BIN]

    target = data.get("github-url", "").strip()
    if not target:
        return {
            "status":"error",
            "message":"Github url not entered",
            "total_domain_count":   None ,
            "valid_domain_count":   None,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Github url not entered",
            "value_entered": None
        }

    command.extend(["-d", target])
    
    extended = data.get("github-extended", "").strip().lower() == "yes"
    if extended:
        command.append("-e")
    
    exit = data.get("github-exit-disabled", "").strip().lower() == "yes"
    if exit:
        command.append("-k")

    raw = data.get("github-raw", "").strip().lower() == "yes"
    if raw:
        command.append("-raw")
    
    token = os.getenv('GITHUB_SUBDOMAIN_TOKEN')

    command.extend("-t", token)

    command_str = " ".join(command)

    print(f"DEBUG: Github subdomain command → {command_str}")

    start = time.time()
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # timeout=60
        )

        execution_ms = int((time.time() - start) * 1000)

        print()
        print("→ cmd:", command)
        print("→ returncode:", result.returncode)
        print("→ stdout repr:", repr(result.stdout))
        print("→ stderr repr:", repr(result.stderr))
        print()
        print()

        output = result.stdout.strip() or "No output captured."

        if result.returncode != 0:
            return {
                "status": "error",
                "message": f"Github subdomain error:\n{output}",
                "total_domain_count":   None ,
                "valid_domain_count":   None,
                "invalid_domain_count": None,
                "duplicate_domain_count" : None,
                "file_size_b":  None,
                "execution_ms": execution_ms,
                "error_reason": "OTHER",
                "error_detail": output,
                "value_entered": None
            }

        return {
            "status": "success",
            "output": output,
            "message": "Scan completed successfully.",
            "total_domain_count":   None ,
            "valid_domain_count":   None,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": execution_ms,
            "error_reason": None,
            "error_detail": None,
            "value_entered": None
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "message": "Github subdomain is not installed or not found in PATH.",
            "total_domain_count":   None ,
            "valid_domain_count":   None,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(FileNotFoundError),
            "value_entered": None
        }
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "message": "Github subdomain timed out.",
            "total_domain_count":   None ,
            "valid_domain_count":   None,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": execution_ms,
            "error_reason": "TIMEOUT",
            "error_detail": str(subprocess.TimeoutExpired),
            "value_entered": None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "total_domain_count":   None ,
            "valid_domain_count":   None,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": int((time.time() - start) * 1000),
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(e),
            "value_entered": None
        }


