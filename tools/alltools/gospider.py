import subprocess
import os
import traceback

def run_scan(data):
    """
    Execute a GoSpider scan based on options provided by the front-end.
    """
    import tempfile

    # Targets via manual or file
    manual = (data.get("gospider-manual", "") or "").strip()
    filein = (data.get("gospider-file", "") or "").strip()

    if filein:
        targets = filein
    elif manual:
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
        tmp.write(manual)
        tmp.close()
        targets = tmp.name
    else:
        return {"status":"error","message":"Gospider: no targets supplied. Provide manual or file input."}

    if not os.path.exists(targets):
        return {"status":"error","message":"Gospider: targets file is missing or invalid."}

    flags = []
    # list vs single
    if targets.lower().endswith(".txt"):
        flags += ["-S", targets]
    else:
        flags += ["-s", targets]
    # threads, concurrency, depth, timeout
    if (thr := (data.get("gospider-threads","") or "").strip()):
        flags += ["-t", thr]
    if (c := (data.get("gospider-c","") or "").strip()):
        flags += ["-c", c]
    if (d := (data.get("gospider-d","") or "").strip()):
        flags += ["-d", d]
    if (m := (data.get("gospider-m","") or "").strip()):
        flags += ["-m", m]
    # subs, user-agent, proxy
    if (data.get("gospider-subs","") or "").strip().lower() in ("y","yes","true","1"):
        flags.append("--subs")
    if (ua := (data.get("gospider-u","") or "").strip()):
        flags += ["-u", ua]
    if (p := (data.get("gospider-p","") or "").strip()):
        flags += ["-p", p]

    command = ["gospider"] + flags
    flag_str = " ".join(flags)
    command_str = f"hacker@gg > gospider {flag_str}"

    try:
        res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout or "Unknown gospider error"
            return {"status":"error","message":f"Gospider error:\n{err}"}
        return {"status":"success","command":command_str,"output":res.stdout or "No output captured."}
    except FileNotFoundError:
        return {"status":"error","message":"Gospider is not installed or not found in PATH."}
    except Exception as e:
        traceback.print_exc()
        return {"status":"error","message":f"Gospider exception: {e}"}
