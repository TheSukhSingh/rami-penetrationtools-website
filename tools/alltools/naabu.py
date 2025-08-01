import subprocess
import os
import traceback

def run_scan(data):
    targets = data.get("targets")
    if not targets or not os.path.exists(targets):
        return {
            "status": "error",
            "message": "Targets file missing or invalid."
        }

    flags = []

    # ─── silent? [y/n] (default: y) ───
    sil_raw = data.get("silent", "").strip().lower()
    if sil_raw == "" or sil_raw == "y":
        flags.append("-silent")

    # ─── top‑ports (default: 100) ───
    top_ports = data.get("top_ports", "").strip() or "100"
    flags += ["-top-ports", top_ports]

    # ─── rate (default: 1000) ───
    rate_val = data.get("rate", "").strip() or "1000"
    flags += ["-rate", rate_val]

    # ─── timeout (default: 5) ───
    timeout = data.get("timeout", "").strip() or "5"
    flags += ["-timeout", timeout]

    # build the actual command & the UI‑friendly header
    command     = ["naabu"] + flags + ["-l", targets]
    display     = os.path.basename(targets)
    command_str = f"hacker@gg > naabu {' '.join(flags)} -l {display}"

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown naabu error"
            return {"status": "error", "message": f"Naabu error:\n{err}"}
        
        output = result.stdout.strip() or "No output captured."

        return {
            "status": "success",
            "command": command_str,
            "output": output
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Naabu exception: {str(e)}"
        }
