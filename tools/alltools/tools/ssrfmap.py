# tools/alltools/tools/ssrfmap.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import re

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets, DOMAIN_RE, IPV4_RE, IPV6_RE,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 7200
RE_URL = re.compile(r'(?i)\bhttps?://[^\s]+')
RE_HOST = re.compile(r'(?i)\b([a-z0-9.-]+\.[a-z]{2,})\b')

def _mine_hosts(text: str) -> Tuple[List[str], List[str]]:
    doms, ips = [], []
    sd, si = set(), set()
    for tok in re.findall(RE_URL, text or ""):
        # extract host portion
        try:
            host = tok.split("://",1)[1].split("/",1)[0].strip("[]")
        except Exception:
            continue
        if IPV4_RE.match(host) or IPV6_RE.match(host):
            if host not in si:
                si.add(host); ips.append(host)
        elif DOMAIN_RE.match(host):
            h = host.lower()
            if h not in sd:
                sd.add(h); doms.append(h)
    # also raw hostnames
    for m in re.findall(RE_HOST, text or ""):
        h = m.lower()
        if DOMAIN_RE.match(h) and h not in sd:
            sd.add(h); doms.append(h)
    return doms, ips

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "ssrfmap")
    slug = options.get("tool_slug", "ssrfmap")
    policy = options.get("_policy") or get_effective_policy(slug)

    exe = resolve_bin("ssrfmap", "ssrfmap.py")
    if not exe:
        return finalize("error", "ssrfmap not installed", options, "ssrfmap", t0, "", error_reason="NOT_INSTALLED")

    urls, _   = read_targets(options, accept_keys=("urls",),   cap=2000)
    params, _ = read_targets(options, accept_keys=("params",), cap=5000)
    if not urls:
        raise ValidationError("Provide URLs for ssrfmap.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=60, kind="int") or 60

    exps: List[str] = []
    doms: List[str] = []
    ips:  List[str] = []
    all_raw = []
    used_cmd = ""

    for u in urls:
        args = [exe, "-u", u, "--crawl", "0", "--batch"]
        for p in (params or [])[:5]:
            args += ["-p", p]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work_dir)
        all_raw.append(out or "")
        if out:
            exps.append(f"ssrfmap output for {u} captured")
            d, i = _mine_hosts(out or "")
            doms.extend(d); ips.extend(i)

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "ssrfmap_output.txt", raw or "")

    # dedupe
    sd = set(); si = set()
    doms = [x for x in doms if not (x in sd or sd.add(x))]
    ips  = [x for x in ips  if not (x in si or si.add(x))]

    status = "ok"
    msg = f"{len(exps)} results; {len(doms)} domains, {len(ips)} ips discovered"
    return finalize(status, msg, options, used_cmd or "ssrfmap", t0, raw, output_file=outfile,
                    exploit_results=exps, domains=doms, ips=ips)
