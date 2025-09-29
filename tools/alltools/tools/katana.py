# tools/alltools/tools/katana.py
from __future__ import annotations
from pathlib import Path
from typing import List
import json
from urllib.parse import urlsplit

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


HARD_TIMEOUT = 5400

def _paths(urls: List[str]) -> List[str]:
    out, seen = [], set()
    for u in urls or []:
        try:
            p = urlsplit(u).path or "/"
        except Exception:
            p = "/"
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def _parse_katana(blob: str) -> List[str]:
    urls, seen = [], set()
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s: continue
        if s.startswith("{"):
            # jsonl
            try:
                obj = json.loads(s)
                u = obj.get("url") or obj.get("request","").get("url")
                if u and u not in seen:
                    seen.add(u); urls.append(u)
                continue
            except Exception:
                pass
        # fallback: plain URL per line
        if s.startswith("http://") or s.startswith("https://"):
            if s not in seen:
                seen.add(s); urls.append(s)
    return urls

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work = ensure_work_dir(options, "katana")
    slug = options.get("tool_slug", "katana")
    pol  = options.get("_policy") or get_effective_policy(slug)
    ipol = pol.get("input_policy", {}) or {}

    exe = resolve_bin("katana", "katana.exe")
    if not exe:
        return finalize("error", "katana not installed", options, "katana", t0, "", error_reason="NOT_INSTALLED")

    seeds, _ = read_targets(options, accept_keys=("urls","domains"), cap=ipol.get("max_targets") or 5000)
    if not seeds:
        raise ValidationError("Provide urls/domains for katana.", "INVALID_PARAMS", "no input")

    depth     = clamp_from_constraints(options, "depth",     pol.get("runtime_constraints",{}).get("depth"),     default=2,  kind="int") or 2
    timeout_s = clamp_from_constraints(options, "timeout_s", pol.get("runtime_constraints",{}).get("timeout_s"), default=20, kind="int") or 20
    rate      = clamp_from_constraints(options, "rate",      pol.get("runtime_constraints",{}).get("rate"),      default=200, kind="int") or 200

    fp = Path(work) / "seeds.txt"
    fp.write_text("\n".join(seeds), encoding="utf-8")

    # Prefer JSONL if supported; otherwise plain output
    args = [exe, "-list", str(fp), "-d", str(depth), "-silent", "-nc", "-timeout", str(timeout_s), "-rate-limit", str(rate), "-jsonl"]
    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work)

    urls = _parse_katana(out or "")
    outfile = write_output_file(work, "katana_output.txt", out or "")

    endpoints = _paths(urls)
    msg = f"{len(urls)} urls, {len(endpoints)} endpoints"
    return finalize("ok", msg, options, " ".join(args), t0, out, output_file=outfile, urls=urls, endpoints=endpoints)
