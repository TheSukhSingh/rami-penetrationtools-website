# import subprocess
# import os
# import traceback

# def run_scan(data):
#     targets = data.get("targets")
#     if not targets or not os.path.exists(targets):
#         return {
#             "status": "error",
#             "message": "Targets file missing or invalid."
#         }

#     flags = []

#     # ─── silent? [y/n] (default: y) ───
#     sil_raw = data.get("silent", "").strip().lower()
#     if sil_raw == "" or sil_raw == "y":
#         flags.append("-silent")

#     # ─── top‑ports (default: 100) ───
#     top_ports = data.get("top_ports", "").strip() or "100"
#     flags += ["-top-ports", top_ports]

#     # ─── rate (default: 1000) ───
#     rate_val = data.get("rate", "").strip() or "1000"
#     flags += ["-rate", rate_val]

#     # ─── timeout (default: 5) ───
#     timeout = data.get("timeout", "").strip() or "5"
#     flags += ["-timeout", timeout]

#     # build the actual command & the UI‑friendly header
#     command     = ["naabu"] + flags + ["-l", targets]
#     display     = os.path.basename(targets)
#     command_str = f"hacker@gg > naabu {' '.join(flags)} -l {display}"

#     try:
#         result = subprocess.run(
#             command,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True
#         )

#         if result.returncode != 0:
#             err = result.stderr.strip() or result.stdout.strip() or "Unknown naabu error"
#             return {"status": "error", "message": f"Naabu error:\n{err}"}
        
#         output = result.stdout.strip() or "No output captured."

#         return {
#             "status": "success",
#             "command": command_str,
#             "output": output
#         }

#     except Exception as e:
#         traceback.print_exc()
#         return {
#             "status": "error",
#             "message": f"Naabu exception: {str(e)}"
#         }





import subprocess
import os
import traceback


def run_scan(data):
    """
    Run a Naabu port scan based on provided form data.

    Expected data keys:
      - naabu-input-method: "manual" or "file"
      - naabu-manual: newline-separated hosts (if manual)
      - naabu-file: path to uploaded .txt file (if file)
      - naabu-silent: "yes" or "no"
      - naabu-top-ports: integer as string (default: "100")
      - naabu-rate: integer as string (default: "1000")
      - naabu-timeout: integer as string (default: "5")
    """
    # Determine target input mode
    method = data.get("naabu-input-method", "manual").lower()
    flags = []

    # ─── Targets ───
    if method == "file":
        file_path = data.get("naabu-file")
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "message": "Targets file missing or invalid."}
        # Naabu uses -l for list-file
        flags += ["-l", file_path]
    else:
        manual = data.get("naabu-manual", "")
        hosts = [h.strip() for h in manual.splitlines() if h.strip()]
        if not hosts:
            return {"status": "error", "message": "No hosts provided for manual input."}
        # one -host per entry
        for h in hosts:
            flags += ["-host", h]

    # ─── Silent? (default yes) ───
    sil = data.get("naabu-silent", "").strip().lower()
    if sil in ("", "yes", "y"):  # default to silent
        flags.append("-silent")

    # ─── Top ports (default: 100) ───
    top_ports = data.get("naabu-top-ports", "").strip() or "100"
    flags += ["-top-ports", top_ports]

    # ─── Rate (default: 1000) ───
    rate = data.get("naabu-rate", "").strip() or "1000"
    flags += ["-rate", rate]

    # ─── Timeout (default: 5) ───
    timeout = data.get("naabu-timeout", "").strip() or "5"
    flags += ["-timeout", timeout]

    # Build command and UI preview string
    command = ["naabu"] + flags
    command_str = "hacker@gg > " + " ".join(command)

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown Naabu error"
            return {"status": "error", "message": f"Naabu error:\n{err}"}

        output = result.stdout.strip() or "No output captured."
        return {
            "status": "success",
            "command": command_str,
            "output": output
        }

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"Naabu exception: {str(e)}"}
