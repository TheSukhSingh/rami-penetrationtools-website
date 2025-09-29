# tools/alltools/tools/jwt_crack.py
from __future__ import annotations
from pathlib import Path
from typing import List
import base64
import hmac
import hashlib
import json

try:
    from ._common import (
        ensure_work_dir, read_targets,
        write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

# Pure-Python lightweight HS256/384/512 brute (only if user supplies wordlist).
# This avoids depending on external binaries; will be fast only for small lists.

def _b64url_decode(s: str) -> bytes:
    s = s.strip().replace("-", "+").replace("_", "/")
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad)

def _algo(header_json: str) -> str:
    try:
        obj = json.loads(header_json)
        return obj.get("alg", "HS256").upper()
    except Exception:
        return "HS256"

def _sign(algo: str, key: bytes, msg: bytes) -> bytes:
    digest = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}.get(algo, hashlib.sha256)
    return hmac.new(key, msg, digest).digest()

def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "jwt_crack")
    slug = options.get("tool_slug", "jwt-crack")

    tokens, _ = read_targets(options, accept_keys=("value","tokens"), cap=50)
    if not tokens:
        raise ValidationError("Provide at least one JWT (value/tokens).", "INVALID_PARAMS", "no input")

    wordlist = options.get("wordlist")
    if not wordlist:
        raise ValidationError("Provide a wordlist path for brute.", "INVALID_PARAMS", "missing wordlist")

    # try cracking each token
    results: List[str] = []
    raw_log = []

    try:
        wl = Path(wordlist).read_text("utf-8", errors="ignore").splitlines()
    except Exception as e:
        raise ValidationError("Unable to read wordlist", "INVALID_PARAMS", str(e))

    for tok in tokens:
        parts = (tok or "").split(".")
        if len(parts) != 3:
            continue
        header_b, payload_b, sig_b = parts
        try:
            header_json = _b64url_decode(header_b).decode("utf-8", errors="ignore")
            algo = _algo(header_json)
            msg = f"{header_b}.{payload_b}".encode()
            target_sig = _b64url_decode(sig_b)
        except Exception:
            continue

        found = None
        for w in wl:
            key = w.strip().encode()
            sig = _sign(algo, key, msg)
            if sig == target_sig:
                found = w.strip()
                break
        if found:
            results.append(f"JWT cracked ({algo}): secret = '{found}'")
            raw_log.append(f"{tok[:30]}... -> {found}")
        else:
            raw_log.append(f"{tok[:30]}... -> no match")

    raw = "\n".join(raw_log)
    outfile = write_output_file(work_dir, "jwt_crack_output.txt", raw or "")

    status = "ok"
    msg = f"{len([r for r in results])} cracked"
    return finalize(status, msg, options, "jwt-crack(py)", t0, raw, output_file=outfile,
                    exploit_results=results)
