
import subprocess
import os

def run_scan(data):
    """
    Execute an httpx scan based on options provided by the front-end.
    """
    import tempfile

    manual = (data.get("httpx-manual", "") or "").strip()
    filein = (data.get("httpx-file", "") or "").strip()

    if filein:
        targets = filein
    elif manual:
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
        tmp.write(manual)
        tmp.close()
        targets = tmp.name
    else:
        return {"status":"error","message":"httpx: no targets supplied. Provide manual or file input."}

    if not os.path.exists(targets):
        return {"status":"error","message":f"Targets file '{targets}' does not exist or is missing."}

    sil = (data.get("httpx-silent","") or "").strip().lower()
    stat = (data.get("httpx-status-code","") or "").strip().lower()
    silent_flag = sil in ("","y","yes","true","1")
    status_flag = stat in ("","y","yes","true","1")

    threads = (data.get("httpx-threads","") or "").strip() or "50"
    timeout = (data.get("httpx-timeout","") or "").strip() or "10"
    title   = (data.get("httpx-title","") or "").strip().lower()

    flags = []
    if silent_flag: flags.append("-silent")
    if status_flag: flags.append("-status-code")
    if title in ("y","yes","true","1"): flags.append("-title")
    flags += ["-t", threads, "-timeout", timeout, "-no-color"]

    display = os.path.basename(targets)
    cmd_str = f"hacker@gg > httpx {' '.join(flags)} -l {display}"
    print(cmd_str)

    try:
        res = subprocess.run(
            ["httpx"] + flags + ["-l", targets],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "Unknown httpx error"
            return {"status":"error","message":f"httpx error:\n{err}"}
        return {"status":"success","command":cmd_str,"output":res.stdout.strip() or "No output captured."}
    except FileNotFoundError:
        return {"status":"error","message":"httpx is not installed or not found in PATH."}
    except Exception as e:
        return {"status":"error","message":f"Unexpected error: {e}"}
