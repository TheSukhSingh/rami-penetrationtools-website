# tools/alltools/tools/gospider.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import glob
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

def _derive(urls: List[str]) -> Tuple[List[str], List[str]]:
    eps, params = [], []
    se, sp = set(), set()
    for u in urls or []:
        try:
            spx = urlsplit(u)
            pth = spx.path or "/"
            if pth not in se:
                se.add(pth); eps.append(pth)
            for k, _ in parse_qsl(spx.query or "", keep_blank_values=True):
                if k not in sp:
                    sp.add(k); params.append(k)
        except Exception:
            continue
    return eps, params

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "gospider")
    slug = options.get("tool_slug", "gospider")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("gospider")
    if not exe:
        return finalize("error", "gospider not installed", options, "gospider", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls","domains"), cap=ipol.get("max_targets") or 5000)
    if not urls:
        raise ValidationError("Provide URLs/domains for gospider.", "INVALID_PARAMS", "no input")

    depth     = clamp_from_constraints(options, "depth",     policy.get("runtime_constraints", {}).get("depth"),     default=2, kind="int") or 2
    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=10, kind="int") or 10
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=15, kind="int") or 15

    fp = Path(work_dir) / "seeds.txt"
    fp.write_text("\n".join(urls), encoding="utf-8")
    outdir = Path(work_dir) / "out"
    outdir.mkdir(parents=True, exist_ok=True)

    args = [exe, "-S", str(fp), "-o", str(outdir), "-d", str(depth), "-t", str(threads), "-c", str(timeout_s), "-q"]
    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 300), cwd=work_dir)

    # gospider writes per-target .txt files under outdir
    found: List[str] = []
    for f in outdir.rglob("*.txt"):
        try:
            for ln in f.read_text("utf-8", errors="ignore").splitlines():
                s = (ln or "").strip()
                if s.startswith("http://") or s.startswith("https://"):
                    found.append(s)
        except Exception:
            continue

    raw = (out or "")
    outfile = write_output_file(work_dir, "gospider_output.txt", raw)

    # de-dup
    seen = set(); found = [x for x in found if not (x in seen or seen.add(x))]

    eps, params = _derive(found)
    status = "ok"
    msg = f"{len(found)} urls, {len(eps)} endpoints, {len(params)} params"
    return finalize(status, msg, options, " ".join(args), t0, raw, output_file=outfile,
                    urls=found, endpoints=eps, params=params)
