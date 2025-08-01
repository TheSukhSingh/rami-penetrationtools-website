# import subprocess
# import os
# import traceback

# def run_scan(data):
#     # targets.txt should contain one domain or URL per line
#     targets = data.get("targets", "").strip()
#     if not targets or not os.path.exists(targets):
#         return {
#             "status": "error",
#             "message": "GAU: targets file is missing or invalid."
#         }

#     flags = []

#     # ─── concurrency (--threads) (default: 50) ───
#     threads = data.get("threads", "").strip() or "50"
#     flags += ["--threads", threads]

#     # ─── timeout (--timeout) (default: 30) ───
#     timeout = data.get("timeout", "").strip() or "30"
#     flags += ["--timeout", timeout]

#     # ─── include subdomains (--subs) [y/n] (default: n) ───
#     subs = data.get("subs", "").strip().lower()
#     if subs == "y":
#         flags.append("--subs")

#     # ─── specify providers (--providers) comma-separated ───
#     providers = data.get("providers", "").strip()
#     if providers:
#         flags += ["--providers", providers]

#     # ─── retries (--retries) (default: 3) ───
#     retries = data.get("retries", "").strip() or "3"
#     flags += ["--retries", retries]

#     # ─── blacklist extensions (--blacklist) ───
#     blacklist = data.get("blacklist", "").strip()
#     if blacklist:
#         flags += ["--blacklist", blacklist]

#     # ─── filter status codes (--fc) ───
#     # fc = data.get("fc", "").strip()
#     # if fc:
#     #     flags += ["--fc", fc]

#     # ─── match status codes (--mc) ───
#     # mc = data.get("mc", "").strip()
#     # if mc:
#     #     flags += ["--mc", mc]

#     # ─── filter MIME types (--ft) ───
#     # ft = data.get("ft", "").strip()
#     # if ft:
#     #     flags += ["--ft", ft]

#     # ─── match MIME types (--mt) ───
#     # mt = data.get("mt", "").strip()
#     # if mt:
#     #     flags += ["--mt", mt]

#     # ─── remove param duplicates (--fp) ───
#     # fp = data.get("fp", "").strip().lower()
#     # if fp == "y":
#     #     flags.append("--fp")

#     # ─── JSON output (--json) ───
#     json_flag = data.get("json", "").strip().lower()
#     if json_flag == "y":
#         flags.append("--json")

#     # ─── proxy (--proxy) ───
#     # proxy = data.get("proxy", "").strip()
#     # if proxy:
#     #     flags += ["--proxy", proxy]

#     # ─── date range (--from) ───
#     # date_from = data.get("from", "").strip()
#     # if date_from:
#     #     flags += ["--from", date_from]

#     # ─── date range (--to) ───
#     # date_to = data.get("to", "").strip()
#     # if date_to:
#     #     flags += ["--to", date_to]

#     # Read URLs from the file and pipe into gau
#     try:
#         with open(targets, "r") as f:
#             input_data = f.read()
#     except Exception as e:
#         return {
#             "status": "error",
#             "message": f"GAU: failed reading targets file: {str(e)}"
#         }

#     # Build command and UI display
#     command = ["gau"] + flags + ["-"]
#     display_file = os.path.basename(targets)
#     flag_str = " ".join(flags)
#     command_str = f"hacker@gg > gau {flag_str} < {display_file}"

#     try:
#         result = subprocess.run(
#             command,
#             input=input_data,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True
#         )
#         if result.returncode != 0:
#             err = result.stderr.strip() or result.stdout.strip() or "Unknown gau error"
#             return {"status": "error", "message": f"GAU error:\n{err}"}

#         output = result.stdout.strip() or "No output captured."
#         return {
#             "status": "success",
#             "command": command_str,
#             "output": output
#         }

#     except FileNotFoundError:
#         return {
#             "status": "error",
#             "message": "GAU is not installed or not found in PATH."
#         }
#     except Exception as e:
#         traceback.print_exc()
#         return {"status": "error", "message": f"GAU exception: {str(e)}"}




# gau.py
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
