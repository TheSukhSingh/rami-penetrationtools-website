import subprocess
import os
import traceback

def run_scan(data):
    """
    Execute a GAU (GetAllURLs) scan using options provided by the front-end.

    The UI supplies either a manual list of domains/URLs or the name of a
    file containing targets via the keys ``gau-manual`` and ``gau-file``.
    Additional options are namespaced with a ``gau-`` prefix.
    """
    # Determine the targets input
    manual_input = (data.get("gau-manual", "") or "").strip()
    file_input   = (data.get("gau-file", "") or "").strip()

    if file_input:
        targets = file_input
    elif manual_input:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
        tmp.write(manual_input)
        tmp.close()
        targets = tmp.name
    else:
        return {
            "status": "error",
            "message": "GAU: no targets supplied. Please provide manual input or upload a file."
        }

    if not os.path.exists(targets):
        return {
            "status": "error",
            "message": "GAU: targets file is missing or invalid."
        }

    flags = []
    # ─── concurrency (--threads) ───
    threads = (data.get("gau-threads", "") or "").strip() or "50"
    flags += ["--threads", threads]
    # ─── timeout (--timeout) ───
    timeout = (data.get("gau-timeout", "") or "").strip() or "30"
    flags += ["--timeout", timeout]
    # ─── include subdomains (--subs) ───
    if (data.get("gau-subs", "") or "").strip().lower() in ("y","yes","true","1"):
        flags.append("--subs")
    # ─── providers, retries, blacklist ───
    prov = (data.get("gau-providers", "") or "").strip()
    if prov: flags += ["--providers", prov]
    retr = (data.get("gau-retries", "") or "").strip() or "3"
    flags += ["--retries", retr]
    blkl = (data.get("gau-blacklist", "") or "").strip()
    if blkl: flags += ["--blacklist", blkl]
    # ─── JSON output ───
    if (data.get("gau-json", "") or "").strip().lower() in ("y","yes","true","1"):
        flags.append("--json")

    try:
        with open(targets, "r") as f:
            input_data = f.read()
    except Exception as e:
        return {"status":"error","message":f"GAU: failed reading targets file: {e}"}

    command = ["gau"] + flags + ["-"]
    display_file = os.path.basename(targets)
    flag_str = " ".join(flags)
    command_str = f"hacker@gg > gau {flag_str} < {display_file}"

    try:
        result = subprocess.run(
            command, input=input_data,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown gau error"
            return {"status":"error","message":f"GAU error:\n{err}"}
        return {"status":"success","command":command_str,"output":result.stdout.strip() or "No output captured."}
    except FileNotFoundError:
        return {"status":"error","message":"GAU is not installed or not found in PATH."}
    except Exception as e:
        traceback.print_exc()
        return {"status":"error","message":f"GAU exception: {e}"}
