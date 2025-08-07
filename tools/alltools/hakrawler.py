import shutil
import subprocess
import os
import tempfile
import time
from utils.domain_classification import classify_lines



def run_scan(data):
    print("→ Using hakrawler at:", shutil.which("hakrawler"))

    HAKRAWLER_BIN = r"/usr/local/bin/hakrawler"
    total_domain_count = valid_domain_count = invalid_domain_count = duplicate_domain_count = 0
    file_size_b = None
    tmp = None
    method = data.get('input_method', 'manual')
    command = [HAKRAWLER_BIN]

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
        domain_file = tmp

    else:
        raw = data.get("hakrawler-manual", "")
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
                "file_size_b":          None,
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
        
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
            tf.write("\n".join(valid))
            domain_file = tf.name
        
        file_size_b  = None


    # 2) Parse options
    depth = data.get("hakrawler-silent", "").strip() or "2" # 1 2 5
    subdomains     = data.get("hakrawler-threads", "").strip().lower() == "yes"
    threads = data.get("hakrawler-timeout", "").strip() or "8" # 2 8 50
    timeout = data.get("hakrawler-all",   "").strip() or "15" # 3 15 60
    unique = data.get("hakrawler-max-time", "").strip().lower() == "yes"

    try:
        t = int(depth)
        if not (1 <= t <= 5):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Depth must be between 1-5",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Depth must be between 1-5",
            "value_entered": t
        }
    command.extend(["-d", depth])

    try:
        t2 = int(threads)
        if not (2 <= t2 <= 50):
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
            "value_entered": t2
        }
    command.extend(["-t", threads])

    try:
        t3 = int(timeout)
        if not (3 <= t3 <= 60):
            raise ValueError
    except ValueError:
        return {
            "status":"error",
            "message":"Timeout must be between 3-60",
            "total_domain_count":   total_domain_count ,
            "valid_domain_count":   valid_domain_count,
            "invalid_domain_count": invalid_domain_count,
            "duplicate_domain_count" : duplicate_domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": f"Timeout must be between 3-60",
            "value_entered": t3
        }
    command.extend(["-timeout", timeout])




    if subdomains:
        command.append("-subs")

    if unique:
        command.append("-u")

    command_str = " ".join(command)

    print(f"DEBUG: hakrawler command → {command_str}")

    start = time.time()
    try:
        result = subprocess.run(
            command,
            stdin=open(domain_file, "r"),
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
        os.remove(domain_file)
        output = result.stdout.strip() or "No output captured."

        if result.returncode != 0:
            return {
                "status": "error",
                "message": f"Hakrawler error:\n{output}",
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
            "message": "Hakrawler is not installed or not found in PATH.",
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
            "message": "Hakrawler timed out.",
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

