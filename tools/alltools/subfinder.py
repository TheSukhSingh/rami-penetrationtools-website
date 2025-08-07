
import os
from tools.utils.domain_classification import classify_lines
import subprocess
import shutil
import time


def run_scan(data):
    print("→ Using subfinder at:", shutil.which("subfinder"))

    SUBFINDER_BIN = r"/usr/local/bin/subfinder"
    total_domain_count = valid_domain_count = invalid_domain_count = duplicate_domain_count = 0
    file_size_b = None
    tmp = None
    method = data.get('input_method', 'manual')
    command = [SUBFINDER_BIN]

    if method == 'file':
        # 1) locate the file
        filepath = data.get('file_path', '')
        if not filepath or not os.path.exists(filepath):
            return {
                "status":               "error",
                "message":              "Upload file not found.",
                "total_domain_count":   None,
                "valid_domain_count":   None,
                "invalid_domain_count": None,
                "duplicate_domain_count": None,
                "file_size_b":          file_size_b,
                "execution_ms":         0,
                "error_reason":         "INVALID_PARAMS",
                "error_detail":         "Missing or inaccessible file",
                "value_entered":        None
            }

        # 2) quick size guard (e.g. 100 KB max)
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

        # 3) read & classify every line
        with open(filepath) as f:
            lines = [l.strip() for l in f if l.strip()]

        total_domain_count   = len(lines)

        valid, invalid, duplicate_domain_count = classify_lines(lines)
        valid_domain_count   = len(valid)
        invalid_domain_count = len(invalid)

        # 4) reject any invalid entries
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

        # 6) rebuild a filtered temp file containing only the valid list
        tmp = filepath + ".filtered"
        with open(tmp, 'w') as f:
            f.write("\n".join(valid))
        filepath = tmp
        # now hand off to subfinder via -dL
        command.extend(['-dL', filepath])
    else:
        raw = data.get("subfinder-manual", "")
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
        for d in valid:
            command.extend(['-d', d])

    # 2) Parse options
    silent_flag = data.get("subfinder-silent",   "").strip().lower() == "yes"
    all_flag    = data.get("subfinder-all",      "").strip().lower() == "yes"
    threads     = data.get("subfinder-threads",  "").strip() or "10"
    timeout_opt = data.get("subfinder-timeout",  "").strip() or "30"
    max_time    = data.get("subfinder-max-time", "").strip() or "5"

    # Threads limit
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
    
    # Timeout limit
    try:
        t2 = int(timeout_opt)
        if not (10 <= t2 <= 120):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Timeout must be between 10-120 seconds",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Timeout must be between 10-120 seconds",
            "value_entered": t2
        }
    
    # Max Time limit
    try:
        t3 = int(max_time)
        if not (1 <= t3 <= 15):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Max time must be between 1-15 min",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Max time must be between 1-15 min",
            "value_entered": t3
        }

    # 3) Build the command
    if silent_flag:
        command.append("-silent")

    if all_flag:
        command.append("-all")

    command.extend(["-t", threads, "-timeout", timeout_opt])
    command.extend(["-max-time", max_time])
    command.append("-nc")

    command_str = " ".join(command)

    print(f"DEBUG: subfinder command → {command_str}")

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
                "message": f"Subfinder error:\n{output}",
                "total_domain_count":   total_domain_count ,
                "valid_domain_count":   valid_domain_count,
                "invalid_domain_count": invalid_domain_count,
                "duplicate_domain_count" : duplicate_domain_count,
                "file_size_b":  file_size_b,
                "execution_ms": execution_ms,
                "error_reason": "OTHER",
                "error_detail": output,
                "value_entered": None
            }

        return {
            "status": "success",
            "output": output,
            "message": "Scan completed successfully.",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": execution_ms,
            "error_reason": None,
            "error_detail": None,
            "value_entered": None
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "message": "Subfinder is not installed or not found in PATH.",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(FileNotFoundError),
            "value_entered": None
        }
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "message": "Subfinder timed out.",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": execution_ms,
            "error_reason": "TIMEOUT",
            "error_detail": str(subprocess.TimeoutExpired),
            "value_entered": None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": int((time.time() - start) * 1000),
            "error_reason": "INVALID_PARAMS",
            "error_detail": str(e),
            "value_entered": None
        }

    finally:
        # clean up the filtered‐file if we created one
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

