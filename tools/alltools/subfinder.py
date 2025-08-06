
import os
import subprocess
import shutil
import time

def run_scan(data):
    # 1) Extract domains from the textarea

    print("→ Using subfinder at:", shutil.which("subfinder"))

    SUBFINDER_BIN = r"/usr/local/bin/subfinder"


    # raw = data.get("subfinder-manual", "").strip()
    # domains = [d.strip() for d in raw.splitlines() if d.strip()]
    # if not domains:
    #     return {"status": "error", "message": "At least one domain is required."}

    method = data.get('input_method', 'manual')
    command = [SUBFINDER_BIN]

    if method == 'file':
        filepath = data.get('file_path', '')
        if not filepath or not os.path.exists(filepath):
            return {"status": "error", "message": "Upload file not found."}
        domain_count = sum(1 for _ in open(filepath))
        file_size_b  = os.path.getsize(filepath)
        command.extend(['-dL', filepath])
    else:
        raw = data.get("subfinder-manual", "").strip()
        domains = [d for d in raw.splitlines() if d.strip()]
        domain_count = len(domains)
        file_size_b  = None
        if not domains:
            return {"status": "error", "message": "At least one domain is required."}
        for d in domains:
            command.extend(['-d', d])







    # 2) Parse options
    silent_flag = data.get("subfinder-silent", "").strip().lower() == "yes"
    threads     = data.get("subfinder-threads", "").strip()  or "10"
    timeout_opt = data.get("subfinder-timeout", "").strip() or "10"

    all_flag = data.get("subfinder-all",   "").strip().lower() == "yes"
    max_time = data.get("subfinder-max-time", "").strip() or "10"

    # 3) Build the command
    if silent_flag:
        command.append("-silent")

    if all_flag:
        command.append("-all")

    command.extend(["-t", threads, "-timeout", timeout_opt])
    command.extend(["-max-time", max_time])
    command.append("-nc")

    # for domain in domains:
    #     command.extend(["-d", domain])

    command_str = " ".join(command)

    print(f"DEBUG: subfinder command → {command_str}")

    start = time.time()
    try:
        # 4) Run it, merging stderr into stdout and enforce a 60s timeout
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60
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

        # 5) Check return code
        if result.returncode != 0:
            return {
                "status": "error",
                "message": f"Subfinder error:\n{output}",
                "domain_count": domain_count,
                "file_size_b":  file_size_b,
                "execution_ms": execution_ms,
                "error_reason": "OTHER",
                "error_detail": output
            }

        return {
            "status": "success",
            "command": command_str,
            "output": output,
            "message": "Scan completed successfully.",
            "domain_count": domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": execution_ms,
            "error_reason": None,
            "error_detail": None
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "message": "Subfinder is not installed or not found in PATH.",
            "domain_count": domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": FileNotFoundError
        }
    except subprocess.TimeoutExpired:
        execution_ms = int((time.time() - start) * 1000)
        return {
            "status": "error",
            "message": "Subfinder timed out.",
            "domain_count": domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": execution_ms,
            "error_reason": "TIMEOUT",
            "error_detail": subprocess.TimeoutExpired
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "domain_count": domain_count,
            "file_size_b":  file_size_b,
            "execution_ms": 0,
            "error_reason": "INVALID_PARAMS",
            "error_detail": e
        }





















