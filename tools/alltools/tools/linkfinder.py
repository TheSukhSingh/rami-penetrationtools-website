# tools/alltools/tools/linkfinder.py
from __future__ import annotations
from pathlib import Path
from typing import List
from urllib.parse import urlsplit

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy
except ImportError:
    from policies import get_effective_policy


HARD_TIMEOUT = 3600

def _derive_endpoints(urls: List[str]) -> List[str]:
    out, seen = [], set()
    for u in urls or []:
        try:
            p = urlsplit(u).path or "/"
        except Exception:
            p = "/"
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work = ensure_work_dir(options, "linkfinder")
    slug = options.get("tool_slug", "linkfinder")
    pol  = options.get("_policy") or get_effective_policy(slug)

    # linkfinder is a python module; try binary name then python -m
    exe = resolve_bin("linkfinder")
    py  = resolve_bin("python3", "python")

    if not exe and not py:
        return finalize("error", "linkfinder not installed", options, "linkfinder", t0, "", error_reason="NOT_INSTALLED")

    seeds, _ = read_targets(options, accept_keys=("urls",), cap=5000)
    if not seeds:
        raise ValidationError("Provide JS/page URLs for linkfinder.", "INVALID_PARAMS", "no input")

    found_urls: List[str] = []
    all_raw = []
    used_cmd = ""

    for u in seeds:
        if exe:
            args = [exe, "-i", u, "-o", "cli"]
        else:
            args = [py, "-m", "linkfinder", "-i", u, "-o", "cli"]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work)
        all_raw.append(out or "")
        for ln in (out or "").splitlines():
            s = (ln or "").strip()
            if s.startswith("http://") or s.startswith("https://"):
                found_urls.append(s)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work, "linkfinder_output.txt", raw or "")

    # de-dup
    seen = set(); found_urls = [x for x in found_urls if not (x in seen or seen.add(x))]
    endpoints = _derive_endpoints(found_urls)

    msg = f"{len(found_urls)} urls, {len(endpoints)} endpoints"
    return finalize("ok", msg, options, used_cmd or "linkfinder", t0, raw, output_file=outfile,
                    urls=found_urls, endpoints=endpoints)
