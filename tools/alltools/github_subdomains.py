import subprocess
import os
import traceback
from urllib.parse import urlparse
import dotenv

dotenv.load_dotenv()

def _s(data, key):
    v = data.get(key, "")
    return v.strip() if isinstance(v, str) else ""

def run_scan(data):
    """
    Execute a github-subdomains scan based on options provided by the front-end.
    """
    target = _s(data, "github-url")
    if not target:
        return {"status":"error","message":"GitHub-subdomains: URL/org-repo is required (via 'github-url')."}

    flags = ["-d", target]
    if _s(data, "github-extended").lower() in ("y","yes","true","1"):
        flags.append("-e")
    if _s(data, "github-exit-disabled").lower() in ("y","yes","true","1"):
        flags.append("-k")
    if _s(data, "github-raw").lower() in ("y","yes","true","1"):
        flags.append("-raw")

    token = os.getenv('GITHUB_SUBDOMAIN_TOKEN')

    # Derive output filename
    if target.startswith(("http://","https://")):
        p = urlparse(target)
        name = (p.path.lstrip("/") or p.netloc).replace("/", "_")
    else:
        name = target.replace("/", "_")
    out_file = f"{name}.txt"
    flags += ["-o", out_file]

    # Hard-coded token
    flags += ["-t", token]

    cmd = ["github-subdomains"] + flags

    # Mask display
    disp, it = [], iter(flags)
    for f in it:
        if f == "-t":
            next(it, None)
            disp += ["-t", "<token>"]
        elif f == "-o":
            v = next(it, "")
            disp += ["-o", os.path.basename(v)]
        else:
            disp.append(f)
    display_cmd = f"hackr@gg > github-subdomains {' '.join(disp)}"

    try:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="ignore"
        )
        if res.returncode != 0:
            err = (res.stderr or res.stdout or "").strip() or "Unknown error"
            return {"status":"error","message":f"GitHub-subdomains error:\n{err}"}
        return {"status":"success","command":display_cmd,"output":res.stdout.strip() or "No output captured."}
    except FileNotFoundError:
        return {"status":"error","message":"`github-subdomains` not found in your PATH."}
    except Exception as e:
        traceback.print_exc()
        return {"status":"error","message":f"Exception: {e}"}
