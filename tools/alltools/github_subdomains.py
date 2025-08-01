# import subprocess
# import os
# import traceback
# from urllib.parse import urlparse

# def _s(data, key):
#     """Helper that always returns a stripped string (never None)."""
#     v = data.get(key, "")
#     return v.strip() if isinstance(v, str) else ""

# def run_scan(data):
#     # 1) extract & validate target
#     target = _s(data, "url")
#     if not target:
#         return {
#             "status": "error",
#             "message": "GitHub‑subdomains: URL/org‑repo is required (via 'url')."
#         }

#     # 2) build initial flags
#     flags = ["-d", target]
#     if _s(data, "extended").lower() == "y":
#         flags.append("-e")
#     if _s(data, "exit_on_disabled").lower() == "y":
#         flags.append("-k")
#     if _s(data, "raw").lower() == "y":
#         flags.append("-raw")

#     # 3) figure out output filename
#     # 3) figure out output filename (always derive from the repo path)
#     if target.startswith(("http://", "https://")):
#         p = urlparse(target)
#         name = (p.path.lstrip("/") or p.netloc).replace("/", "_")
#     else:
#         name = target.replace("/", "_")
#     out_file = f"{name}.txt"
#     flags += ["-o", out_file]

#     # 4) hard‑coded GitHub token (no user input needed)
#     flags += ["-t", "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"]


#     # 5) build the subprocess command
#     cmd = ["github-subdomains"] + flags

#     # 6) build a masked display string
#     disp = []
#     it = iter(flags)
#     for f in it:
#         if f == "-t":
#             next(it, None)
#             disp += ["-t", "<token>"]
#         elif f == "-o":
#             v = next(it, "")
#             disp += ["-o", os.path.basename(v)]
#         else:
#             disp.append(f)
#     display_cmd = f"hacker@gg > github-subdomains {' '.join(disp)}"

#     # 7) execute with utf-8 decoding and ignore errors
#     try:
#         res = subprocess.run(
#             cmd,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding='utf-8',
#             errors='ignore'
#         )
#         if res.returncode != 0:
#             err = (res.stderr or res.stdout or "").strip() or "Unknown error"
#             return {"status": "error", "message": f"GitHub‑subdomains error:\n{err}"}
#         out = (res.stdout or "").strip() or "No output captured."
#         return {
#             "status":  "success",
#             "command": display_cmd,
#             "output":  out
#         }
#     except FileNotFoundError:
#         return {"status": "error", "message": "`github-subdomains` not found in your PATH."}
#     except Exception as e:
#         traceback.print_exc()
#         return {"status": "error", "message": f"Exception: {str(e)}"}





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
