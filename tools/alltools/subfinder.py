
import subprocess
import shutil


def run_scan(data):
    # 1) Extract domains from the textarea

    print("→ Using subfinder at:", shutil.which("subfinder"))

    raw = data.get("subfinder-manual", "").strip()
    domains = [d.strip() for d in raw.splitlines() if d.strip()]
    if not domains:
        return {"status": "error", "message": "At least one domain is required."}

    # 2) Parse options
    silent_flag = data.get("subfinder-silent", "").strip().lower() == "yes"
    threads     = data.get("subfinder-threads", "").strip()  or "10"
    timeout_opt = data.get("subfinder-timeout", "").strip() or "10"

    all_flag = data.get("subfinder-all",   "").strip().lower() == "yes"
    max_time = data.get("subfinder-max-time", "").strip() or "10"

    # 3) Build the command
    command = ["subfinder"]
    if silent_flag:
        command.append("-silent")

    if all_flag:
        command.append("-all")

    command.extend(["-t", threads, "-timeout", timeout_opt])
    command.extend(["-max-time", max_time])

    for domain in domains:
        command.extend(["-d", domain])

    command_str = " ".join(command)

    print(f"DEBUG: subfinder command → {command_str}")

    try:
        # 4) Run it, merging stderr into stdout and enforce a 60s timeout
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # timeout=60
        )
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
                "message": f"Subfinder error:\n{output}"
            }

        return {
            "status": "success",
            "command": command_str,
            "output": output,
            "message": "Scan completed successfully."
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "message": "Subfinder is not installed or not found in PATH."
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Subfinder timed out."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }





















