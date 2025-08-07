

import shutil
import time
import subprocess
import os

from tools.utils.domain_classification import classify_lines


def run_scan(data):
    print("→ Using dnsx at:", shutil.which("dnsx"))
    DNSX_BIN = r"/usr/local/bin/dnsx"

    total_domain_count = valid_domain_count = invalid_domain_count = duplicate_domain_count = 0
    file_size_b = None
    tmp = None
    
    method = data.get('input_method', 'manual')

    command = [DNSX_BIN]

    # Acquire and validate targets
    if method == 'file':
        filepath = data.get('file_path', '')
        if not os.path.exists(filepath):
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
                "status":               "error",
                "message":              f"Uploaded file too large ({file_size_b} bytes)",
                "total_domain_count":   None,
                "valid_domain_count":   None,
                "invalid_domain_count": None,
                "duplicate_domain_count" : None,
                "file_size_b":          file_size_b,
                "execution_ms":         0,
                "error_reason":         "FILE_TOO_LARGE",
                "error_detail":         f"{file_size_b} > 100000 bytes limit",
                "value_entered":        file_size_b
            }
        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]

        total_domain_count   = len(lines)
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        valid_domain_count   = len(valid)
        invalid_domain_count = len(invalid)

        if invalid_domain_count > 0:
            return {
                "status":               "error",
                "message":              f"{invalid_domain_count} invalid domains in file",
                "total_domain_count":   total_domain_count,
                "valid_domain_count":   valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count" : duplicate_domain_count,
                "file_size_b":          file_size_b,
                "execution_ms":         0,
                "error_reason":         "INVALID_PARAMS",
                "error_detail":         ", ".join(invalid[:10]),
                "value_entered":        invalid_domain_count
            }

        # 5) reject if too many
        if valid_domain_count > 50:
            return {
                "status":               "error",
                "message":              f"{valid_domain_count} domains in file (max 50)",
                "total_domain_count":   total_domain_count,
                "valid_domain_count":   valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count" : duplicate_domain_count,
                "file_size_b":          file_size_b,
                "execution_ms":         0,
                "error_reason":         "TOO_MANY_DOMAINS",
                "error_detail":         f"{valid_domain_count} > 50 limit",
                "value_entered":        valid_domain_count
            }

    else:
        raw = data.get("dnsx-manual", "")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        total_domain_count  = len(lines)
        if total_domain_count == 0:
            return {
                "status":               "error",
                "message":              "At least one domain is required.",
                "total_domain_count":   total_domain_count,
                "valid_domain_count":   valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count": duplicate_domain_count,
                "file_size_b":          file_size_b,
                "execution_ms":         0,
                "error_reason":         "INVALID_PARAMS",
                "error_detail":         "No domains submitted",
                "value_entered":        None
            }
        valid, invalid, duplicate_domain_count = classify_lines(lines)
        valid_domain_count   = len(valid)
        invalid_domain_count = len(invalid)

        # 3) reject if any invalid domains
        if invalid_domain_count > 0:
            return {
                "status":               "error",
                "message":              f"{invalid_domain_count} invalid domains found",
                "total_domain_count":   total_domain_count ,
                "valid_domain_count":   valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count" : duplicate_domain_count,
                "file_size_b":          None,
                "execution_ms":         0,
                "error_reason":         "INVALID_PARAMS",
                "error_detail":         ", ".join(invalid[:10]),
                "value_entered":        invalid_domain_count
            }
        
        # 4) reject if too many valid domains
        if valid_domain_count > 50:
            return {
                "status":"error",
                "message":f"Too many domains: {valid_domain_count} (max 50)",
                "total_domain_count":   total_domain_count ,
                "valid_domain_count":   valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count" : duplicate_domain_count,
                "file_size_b":  None,
                "execution_ms": 0,
                "error_reason": "TOO_MANY_DOMAINS",
                "error_detail": f"{valid_domain_count} domains > 50 limit",
                "value_entered": valid_domain_count
            }
        
        file_size_b  = None





    threads = (data.get("dnsx-threads") or "").strip() or "50"
    retry = (data.get("dnsx-retry") or "").strip() or "2"

    # threads limit
    try:
        t = int(threads)
        if not (2 <= t <= 50):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Threads must be between 2-50",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Threads must be between 2-50",
            "value_entered": t
        }
    
    # retry limit
    try:
        t2 = int(retry)
        if not (1 <= t2 <= 20):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Retry must be between 1-20",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Threads must be between 1-20",
            "value_entered": t2
        }


    command.append("-resp")
    command.append("-nc")

    rtypes = data.get('dnsx-record-types', [])
    if isinstance(rtypes, str):
        rtypes = [rtypes]

    seen_rtype = set()
    for r in rtypes:
        r = r.lower()
        if r in ('a', 'aaaa', 'cname', 'mx', 'ns', 'txt') and r not in seen_rtype:
            command.append(f"-{r}")
            seen_rtype.add(r)
    
    silent_flag = data.get("dnsx-silent", "").strip().lower() == "yes"
    if silent_flag:
        command.append("-silent")

    command.extend(["-t", threads, "-retry", retry])
    command_str = " ".join(command)

    stdin_data = "\n".join(valid)

    print(f"DEBUG: dnsx command → {command_str}")
    start = time.time()
    try:
        result = subprocess.run(
            command,
            input=stdin_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
                "message": f"dnsx error:\n{output}",
                "total_domain_count": total_domain_count,
                "valid_domain_count": valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count": duplicate_domain_count,
                "file_size_b": file_size_b,
                "execution_ms": execution_ms,
                "error_reason": "OTHER",
                "error_detail": output,
                "value_entered": None
            }
        return {
            "status": "success",
            "output": output,
            "message": "Scan completed successfully.",
            "total_domain_count": total_domain_count,
            "valid_domain_count": valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count": duplicate_domain_count,
            "file_size_b": file_size_b,
            "execution_ms": execution_ms,
            "error_reason": None,
            "error_detail": None,
            "value_entered": None
        }
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "message": "dnsx timed out.",
            "total_domain_count": total_domain_count,
            "valid_domain_count": valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count": duplicate_domain_count,
            "file_size_b": file_size_b,
            "execution_ms": execution_ms,
            "error_reason": "TIMEOUT",
            "error_detail": str(subprocess.TimeoutExpired),
            "value_entered": None
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": "dnsx is not installed or not found in PATH.",
            "total_domain_count": total_domain_count,
            "valid_domain_count": valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count": duplicate_domain_count,
            "file_size_b": file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(FileNotFoundError),
            "value_entered": None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "total_domain_count": total_domain_count,
            "valid_domain_count": valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count": duplicate_domain_count,
            "file_size_b": file_size_b,
            "execution_ms": int((time.time() - start) * 1000),
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(e),
            "value_entered": None
        }
    finally:
        # Cleanup temporary file
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass