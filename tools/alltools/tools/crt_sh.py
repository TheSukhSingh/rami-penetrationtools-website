# tools/alltools/tools/crt_sh.py
from __future__ import annotations
from typing import List
import json
import os

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets, DOMAIN_RE,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

HARD_TIMEOUT = 900

def _dedupe_domains(names: List[str]) -> List[str]:
    out, seen = [], set()
    for n in names or []:
        for part in str(n).splitlines():
            s = part.strip().lower()
            if not s: 
                continue
            # crt_sh name_value may have wildcard or multiple entries separated by newlines
            s = s.lstrip("*.").strip()
            if DOMAIN_RE.match(s) and s not in seen:
                seen.add(s); out.append(s)
    return out

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "crt_sh")
    slug = options.get("tool_slug", "crt_sh")
    # note: no special policy needs beyond max_targets

    curl = resolve_bin("curl")
    if not curl:
        return finalize("error", "curl not installed (required for crt_sh API)", options, "crt_sh", t0, "", error_reason="NOT_INSTALLED")

    domains, _ = read_targets(options, accept_keys=("domains",), cap=50)
    if not domains:
        raise ValidationError("Provide root domain(s) for crt_sh.", "INVALID_PARAMS", "no input")

    all_raw = []
    found: List[str] = []
    used_cmd = ""

    for d in domains:
        # %25 = '%', query all subdomains of domain
        url = f"https://crt_sh/?q=%25.{d}&output=json"
        args = [curl, "-fsSL", url]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work_dir)
        if out:
            all_raw.append(out)
            try:
                arr = json.loads(out)
                names = [it.get("name_value") for it in (arr if isinstance(arr, list) else [])]
                found.extend(_dedupe_domains(names))
            except Exception:
                # fallback: try to parse lines as text (rare)
                for ln in out.splitlines():
                    s = (ln or "").strip().lower()
                    if DOMAIN_RE.match(s):
                        found.append(s)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "crtsh_output.jsonl", raw or "")

    # de-dup
    seen = set(); found = [x for x in found if not (x in seen or seen.add(x))]

    status = "ok"
    msg = f"{len(found)} subdomains"
    return finalize(status, msg, options, used_cmd or "crt_sh", t0, raw, output_file=outfile,
                    domains=found)
