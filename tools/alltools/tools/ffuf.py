# tools/alltools/tools/ffuf.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import json
from urllib.parse import urlsplit, parse_qsl

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 3600

def _derive(end_urls: List[str]) -> Tuple[List[str], List[str]]:
    endpoints, params = [], []
    se, sp = set(), set()
    for u in end_urls or []:
        try:
            spx = urlsplit(u)
            pth = spx.path or "/"
            if pth and pth not in se:
                se.add(pth); endpoints.append(pth)
            for k, _ in parse_qsl(spx.query or "", keep_blank_values=True):
                if k not in sp:
                    sp.add(k); params.append(k)
        except Exception:
            continue
    return endpoints, params

def _parse_ffuf_json(blob: str) -> List[str]:
    urls: List[str] = []
    try:
        data = json.loads(blob)
    except Exception:
        return urls
    for it in (data.get("results") or []):
        u = it.get("url") or it.get("input")
        if u:
            urls.append(u)
    # dedupe
    seen = set()
    return [x for x in urls if not (x in seen or seen.add(x))]

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "ffuf")
    slug = options.get("tool_slug", "ffuf")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("ffuf", "ffuf.exe")
    if not exe:
        return finalize("error", "ffuf not installed", options, "ffuf", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","hosts","domains"), cap=ipol.get("max_targets") or 10000)
    if not urls:
        raise ValidationError("Provide a base URL/host/domain for ffuf.", "INVALID_PARAMS", "no input")

    # wordlist
    wordlist = options.get("wordlist")
    if not wordlist:
        raise ValidationError("wordlist is required for ffuf (-w).", "INVALID_PARAMS", "missing wordlist")

    # knobs
    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=50, kind="int") or 50
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30
    mc        = options.get("match_codes") or "200,204,301,302,307,401,403"
    fs        = options.get("filter_size")  # optional

    out_all = []
    urls_found: List[str] = []
    used_cmd = ""

    for base in urls:
        # Replace FUZZ token or append /FUZZ if not present
        if "FUZZ" not in base:
            if base.endswith("/"):
                target = base + "FUZZ"
            else:
                target = base.rstrip("/") + "/FUZZ"
        else:
            target = base

        out_json = Path(work_dir) / f"ffuf_{abs(hash(target))}.json"
        args = [exe, "-u", target, "-w", str(wordlist), "-mc", str(mc), "-t", str(threads), "-timeout", str(timeout_s), "-of", "json", "-o", str(out_json)]
        if fs: args += ["-fs", str(fs)]
        used_cmd = " ".join(args[:4] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work_dir)
        # read JSON file if produced
        if out_json.exists():
            try:
                blob = out_json.read_text("utf-8", errors="ignore")
                out_all.append(blob)
                urls_found.extend(_parse_ffuf_json(blob))
            except Exception:
                pass

    raw = "\n".join(out_all)
    outfile = write_output_file(work_dir, "ffuf_output.jsonl", raw or "")

    endpoints, params = _derive(urls_found)
    status = "ok"
    msg = f"{len(endpoints)} endpoints, {len(params)} params"
    return finalize(status, msg, options, used_cmd or "ffuf", t0, raw, output_file=outfile,
                    endpoints=endpoints, params=params)
