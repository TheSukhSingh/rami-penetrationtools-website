# import subprocess

# def run_scan(data):
#     # url = data.get("url", "").strip()
#     # if not url:
#     #     return {"status": "error", "message": "URL is required."}
#     # # helper: blank or "y" -> yes, "n" -> no
#     # def yes_by_default(key, default_yes="y"):
#     #     v = data.get(key, "").strip().lower()
#     #     return (v == "" or v == "y")

#     # silent_flag = yes_by_default("silent")        # default yes
#     # nW_flag     = yes_by_default("nW")            # default yes
#     # all_flag    = (data.get("all_flag", "").strip().lower() == "y")

#     # # numeric fields: blank -> default value
#     # threads  = data.get("threads", "").strip()  or "50"
#     # timeout  = data.get("timeout", "").strip()  or "30"
#     # max_time = data.get("max_time", "").strip() or "10"

#     # flags = []
#     # if silent_flag:
#     #     flags.append("-silent")
#     # if nW_flag:
#     #     flags.append("-nW")
#     # if all_flag:
#     #     flags.append("-all")
#     # flags.extend(["-t", threads])
#     # flags.extend(["-timeout", timeout])
#     # flags.extend(["-max-time", max_time])


#     # pull targets out of your actual form-field names
#     raw = data.get("subfinder-manual", "").strip()
#     domains = [d.strip() for d in raw.splitlines() if d.strip()]
#     if not domains:
#         return {"status": "error", "message": "At least one domain is required."}

#     # helper: blank or "y" -> yes
#     def yes_by_default(prefixed_key, default_yes="y"):
#         v = data.get(prefixed_key, "").strip().lower()
#         return (v == "" or v == default_yes)

#     silent_flag = yes_by_default("subfinder-silent")

#     # numeric fields: blank -> default value
#     threads = data.get("subfinder-threads", "").strip() or "10"
#     timeout = data.get("subfinder-timeout", "").strip() or "10"

#     # flags_string = " ".join(flags)
#     # command_str = f"hacker@gg > subfinder {flags_string} -d {url}"

#     try:
#         # command = ["subfinder"] + flags + ["-d", url]
#         command = ["subfinder"] 
#         if silent_flag:
#             command.append("-silent")
#         command.extend(["-t", threads])
#         command.extend(["-timeout", timeout])
#         # append each domain
#         for d in domains:
#             command.extend(["-d", d])

#         command_str = " ".join(command)
#         result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


#         if result.returncode != 0:
#             err = result.stderr.strip() or result.stdout.strip() or "Unknown subfinder error"
#             return {"status": "error", "message": f"Subfinder error:\n{err}"}

#         output = result.stdout.strip() or "No output captured."

#         return {
#             "status": "success",
#             "command": command_str,
#             "output": output,
#             "message": "Scan completed successfully."
#         }

#     except FileNotFoundError:
#         return {"status": "error", "message": "Subfinder is not installed or not found in PATH."}
#     except Exception as e:
#         return {"status": "error", "message": f"Unexpected error: {str(e)}"}














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
            timeout=60
        )

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
            "message": "Subfinder timed out after 60 seconds."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }





















