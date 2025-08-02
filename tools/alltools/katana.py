
import subprocess
import os
import traceback

def run_scan(data):
    """
    Run a Katana scan using options provided by the front-end.
    """
    import tempfile

    manual = (data.get("katana-manual", "") or "").strip()
    filein = (data.get("katana-file", "") or "").strip()

    if filein:
        targets = filein
    elif manual:
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
        tmp.write(manual)
        tmp.close()
        targets = tmp.name
    else:
        return {"status":"error","message":"Katana: no targets supplied. Provide manual or file input."}

    if not os.path.exists(targets):
        return {"status":"error","message":"Katana: targets file is missing or invalid."}

    flags = []
    if (sil := (data.get("katana-silent","") or "").strip().lower()) in ("","y","yes","true","1"):
        flags.append("-silent")
    if (js := (data.get("katana-jc","") or "").strip().lower()) in ("","y","yes","true","1"):
        flags.append("-jc")
    if (hl := (data.get("katana-headless","") or "").strip().lower()) in ("y","yes","true","1"):
        flags.append("-hl")
    conc = (data.get("katana-c","") or "").strip() or "20"
    flags += ["-c", conc]
    timeout = (data.get("katana-timeout","") or "").strip() or "10"
    flags += ["-timeout", timeout]

    command = ["katana"] + flags + ["-list", targets]
    display = os.path.basename(targets)
    command_str = f"hacker@gg > katana {' '.join(flags)} -list {display}"

    try:
        res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "Unknown katana error"
            return {"status":"error","message":f"Katana error:\n{err}"}
        return {"status":"success","command":command_str,"output":res.stdout.strip() or "No output captured."}
    except Exception as e:
        traceback.print_exc()
        return {"status":"error","message":f"Katana exception: {e}"}
