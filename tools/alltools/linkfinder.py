import subprocess
import os
import traceback
import sys

def run_scan(data):
    # Validate targets file
    targets = data.get("targets", "").strip()
    if not targets or not os.path.exists(targets):
        return {"status": "error", "message": "LinkFinder: targets file is missing or invalid."}

    flags = []

    # ─── domain flag (-d) to crawl entire site (default: off) ───
    domain_flag = data.get("domain", "").strip().lower()
    if domain_flag == "y":
        flags.append("-d")

    # ─── regex filter (-r) (optional) ───
    regex = data.get("regex", "").strip()
    if regex:
        flags += ["-r", regex]

    # ─── burp compatible output (-b) (optional) ───
    burp = data.get("burp", "").strip().lower()
    if burp == "y":
        flags.append("-b")

    # ─── cookies for authenticated JS (-c) (optional) ───
    cookies = data.get("cookies", "").strip()
    if cookies:
        flags += ["-c", cookies]

    # ─── timeout (-t) seconds (default: 10) ───
    timeout = data.get("timeout", "").strip() or "10"
    flags += ["-t", timeout]

    # Build command via Python -m
    command = [sys.executable, "-m", "linkfinder"] + flags + ["-i", targets]

    # Prepare UI‑friendly command string with basename
    display_tgt = os.path.basename(targets)
    flag_str = " ".join(flags)
    command_str = f"hacker@gg > linkfinder {flag_str} -i {display_tgt}"

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown LinkFinder error"
            return {"status": "error", "message": f"LinkFinder error:\n{err}"}

        output = result.stdout.strip() or "No output captured."
        return {
            "status":  "success",
            "command": command_str,
            "output":  output
        }

    except FileNotFoundError:
        return {"status": "error", "message": "Python interpreter not found or LinkFinder module missing."}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"LinkFinder exception: {str(e)}"}
