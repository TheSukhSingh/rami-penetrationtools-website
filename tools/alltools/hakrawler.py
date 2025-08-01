# import subprocess
# import os
# import traceback

# def run_scan(data):
#     targets = data.get("targets", "").strip()
#     if not targets or not os.path.exists(targets):
#         return {"status": "error", "message": "Hakrawler: targets file is missing or invalid."}

#     flags = []

#     # ─── depth (-d) (default: 2) ───
#     depth = data.get("depth", "").strip() or "2"
#     flags += ["-d", depth]

#     # ─── include subdomains (-subs) (default: y) ───
#     subs = data.get("subs", "").strip().lower()
#     if subs == "" or subs == "y":
#         flags.append("-subs")

#     # ─── threads (-t) (default: 8) ───
#     threads = data.get("threads", "").strip() or "8"
#     flags += ["-t", threads]

#     # ─── timeout (-timeout) (default: 30) ───
#     timeout = data.get("timeout", "").strip() or "30"
#     flags += ["-timeout", timeout]

#     # ─── unique URLs only (-u) (default: y) ───
#     unique = data.get("unique", "").strip().lower()
#     if unique == "" or unique == "y":
#         flags.append("-u")

#     # ─── JSON output (--json) (default: n) ───
#     json_flag = data.get("json", "").strip().lower()
#     if json_flag == "y":
#         flags.append("-json")

#     # Read URLs from file
#     try:
#         with open(targets, "r") as f:
#             input_data = f.read()
#     except Exception as e:
#         return {
#             "status": "error",
#             "message": f"Hakrawler: failed reading targets file: {str(e)}"
#         }

#     # Build command and UI display
#     command = ["hakrawler"] + flags + ["-"]
#     display_file = os.path.basename(targets)
#     flag_str = " ".join(flags)
#     command_str = f"hacker@gg > hakrawler {flag_str} < {display_file}"

#     try:
#         result = subprocess.run(
#             command,
#             input=input_data,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True
#         )
#         if result.returncode != 0:
#             err = result.stderr.strip() or result.stdout.strip() or "Unknown hakrawler error"
#             return {"status": "error", "message": f"Hakrawler error:\n{err}"}

#         output = result.stdout.strip() or "No output captured."
#         return {
#             "status": "success",
#             "command": command_str,
#             "output": output
#         }

#     except FileNotFoundError:
#         return {
#             "status": "error",
#             "message": "Hakrawler is not installed or not found in PATH."
#         }
#     except Exception as e:
#         traceback.print_exc()
#         return {"status": "error", "message": f"Hakrawler exception: {str(e)}"}





# hakrawler.py
import subprocess
import os
import traceback

def run_scan(data):
    """
    Execute a Hakrawler scan based on options provided by the front-end.
    """
    import tempfile

    manual = (data.get("hakrawler-manual", "") or "").strip()
    filein = (data.get("hakrawler-file", "") or "").strip()

    if filein:
        targets = filein
    elif manual:
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
        tmp.write(manual)
        tmp.close()
        targets = tmp.name
    else:
        return {"status":"error","message":"Hakrawler: no targets supplied. Provide manual or file input."}

    if not os.path.exists(targets):
        return {"status":"error","message":"Hakrawler: targets file is missing or invalid."}

    flags = []
    depth = (data.get("hakrawler-d", "") or "").strip() or "2"
    flags += ["-d", depth]
    if (subs := (data.get("hakrawler-subs","") or "").strip().lower()) in ("","y","yes","true","1"):
        flags.append("-subs")
    threads = (data.get("hakrawler-threads","") or "").strip() or "8"
    flags += ["-t", threads]
    timeout = (data.get("hakrawler-timeout","") or "").strip() or "30"
    flags += ["-timeout", timeout]
    if (uniq := (data.get("hakrawler-unique","") or "").strip().lower()) in ("","y","yes","true","1"):
        flags.append("-u")
    if (jf := (data.get("hakrawler-json","") or "").strip().lower()) in ("y","yes","true","1"):
        flags.append("-json")

    try:
        with open(targets, "r") as f:
            inp = f.read()
    except Exception as e:
        return {"status":"error","message":f"Hakrawler: failed reading targets file: {e}"}

    command = ["hakrawler"] + flags + ["-"]
    display_file = os.path.basename(targets)
    flag_str = " ".join(flags)
    command_str = f"hacker@gg > hakrawler {flag_str} < {display_file}"

    try:
        res = subprocess.run(
            command, input=inp,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "Unknown hakrawler error"
            return {"status":"error","message":f"Hakrawler error:\n{err}"}
        return {"status":"success","command":command_str,"output":res.stdout.strip() or "No output captured."}
    except FileNotFoundError:
        return {"status":"error","message":"Hakrawler is not installed or not found in PATH."}
    except Exception as e:
        traceback.print_exc()
        return {"status":"error","message":f"Hakrawler exception: {e}"}
