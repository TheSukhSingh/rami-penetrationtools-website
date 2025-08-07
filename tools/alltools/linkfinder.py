import shutil
import subprocess
import time
from tools.utils.domain_classification import classify_lines

def run_scan(data):
    print("→ Using linkfinder at:", shutil.which("linkfinder"))
    command = ["linkfinder"]
    # ─── Required domain ───
    domain = data.get("linkfinder-domain", "").strip()
    if not domain:
        return {
            "status":               "error",
            "message":              "At least one domain is required.",
            "total_domain_count":None,
            "valid_domain_count": None,
            "invalid_domain_count": None,
            "duplicate_domain_count": None,
            "file_size_b":          None,
            "execution_ms":         0,
            "error_reason":         "INVALID_PARAMS",
            "error_detail":         "No domains submitted",
            "value_entered":        None
        }
    
    valid, invalid, _ = classify_lines([domain])
    if invalid:
        return {
            "status": "error",
            "message": "Invalid domain provided.",
            "total_domain_count":1,
            "valid_domain_count": 0,
            "invalid_domain_count": 1,
            "duplicate_domain_count": 0,
            "file_size_b": None,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": "Invalid domain provided.",
            "value_entered": None,
        }
    command.extend(["-i", domain])
    # ─── Regex filter (-r) ───
    regex = data.get("linkfinder-regex", "").strip()
    if regex:
        command.extend(["-r", regex])

    # ─── Burp format (-b) ───
    burp = data.get("linkfinder-burp", "").strip().lower() == "yes"
    if burp:
        command.append("-b")

    # ─── Cookies (-c) ───
    cookies = data.get("linkfinder-cookies", "").strip()
    if cookies:
        command.extend(["-c", cookies])

    # ─── Timeout (-t) ───
    timeout = data.get("linkfinder-timeout", "").strip() or "10"
    try:
        t = int(timeout)
        if not (2 <= t <= 60):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Timeout must be between 2-60",
            "total_domain_count":1 ,
            "valid_domain_count": 1,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Timeout must be between 2-60",
            "value_entered": t
        }
    command.extend(["-t", timeout])

    command_str = " ".join(command)

    print(f"DEBUG: linkfinder command → {command_str}")

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
                "message": f"linkfinder error:\n{output}",
                "total_domain_count":1 ,
                "valid_domain_count": 1,
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
            "total_domain_count":1 ,
            "valid_domain_count": 1,
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
            "message": "linkfinder is not installed or not found in PATH.",
            "total_domain_count":1 ,
            "valid_domain_count": 1,
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
            "message": "linkfinder timed out.",
            "total_domain_count":1 ,
            "valid_domain_count": 1,
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
            "total_domain_count":1 ,
            "valid_domain_count": 1,
            "invalid_domain_count": None,
            "duplicate_domain_count" : None,
            "file_size_b":  None,
            "execution_ms": int((time.time() - start) * 1000),
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(e),
            "value_entered": None
        }



