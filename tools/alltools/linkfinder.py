import subprocess
import os
import traceback
import sys

def run_scan(data):
    """
    Run LinkFinder against a domain with optional regex filtering, Burp output,
    cookies, and custom timeout.

    Expected data keys:
      - linkfinder-domain: (string) target domain/URL (required)
      - linkfinder-regex: (string) regex filter for URLs
      - linkfinder-burp: ("yes"/"no") enable Burp-compatible output
      - linkfinder-cookies: (string) cookie header value
      - linkfinder-timeout: (string/int) request timeout in seconds (default: 10)
    """
    # ─── Required domain ───
    domain = data.get("linkfinder-domain", "").strip()
    if not domain:
        return {"status": "error", "message": "LinkFinder: Domain is required."}

    flags = []

    # ─── Regex filter (-r) ───
    regex = data.get("linkfinder-regex", "").strip()
    if regex:
        flags += ["-r", regex]

    # ─── Burp format (-b) ───
    burp = data.get("linkfinder-burp", "no").strip().lower()
    if burp in ("yes", "y"):
        flags.append("-b")

    # ─── Cookies (-c) ───
    cookies = data.get("linkfinder-cookies", "").strip()
    if cookies:
        flags += ["-c", cookies]

    # ─── Timeout (-t) ───
    timeout = data.get("linkfinder-timeout", "").strip() or "10"
    flags += ["-t", timeout]

    # ─── Build command and UI preview ───
    cmd = [sys.executable, "-m", "linkfinder", "-i", domain] + flags
    flag_str = " ".join(flags)
    command_str = f"hacker@gg > linkfinder -i {domain}" + (f" {flag_str}" if flag_str else "")

    try:
        result = subprocess.run(
            cmd,
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
