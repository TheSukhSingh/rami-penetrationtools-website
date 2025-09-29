# tools/alltools/tools/katana.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlsplit, parse_qsl
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, URL_RE,
    run_cmd, write_output_file, finalize, ValidationError, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 900  # seconds

def _parse_urls(text: str) -> List[str]:
    urls: List[str] = []
    seen = set()
    for raw in (text or "").splitlines():
        s = (raw or "").strip()
        if not s:
            continue
        # katana prints URLs (and may include extra cols with flags). Keep first http(s) token.
        u = None
        for tok in s.split():
            if tok.startswith("http://") or tok.startswith("https://"):
                u = tok; break
        if not u:
            continue
        if u in seen: 
            continue
        seen.add(u); urls.append(u)
    return urls

def _derive_endpoints_params(urls: List[str]) -> Tuple[List[str], List[str]]:
    endpoints: List[str] = []
    params: List[str] = []
    seen_ep, seen_p = set(), set()
    for u in urls or []:
        try:
            sp = urlsplit(u)
        except Exception:
            continue
        path = sp.path or "/"
        if path and path not in seen_ep:
            seen_ep.add(path); endpoints.append(path)
        if sp.query:
            for k, _v in parse_qsl(sp.query, keep_blank_values=True):
                if k not in seen_p:
                    seen_p.add(k); params.append(k)
    return endpoints, params

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "katana")
    slug = options.get("tool_slug", "katana")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("katana", "katana.exe")
    if not exe:
        return finalize("error", "katana not installed", options, "katana", t0, "", error_reason="NOT_INSTALLED")

    # prefer urls, fall back to domains
    urls, _     = read_targets(options, accept_keys=("urls",),     cap=ipol.get("max_targets") or 10000)
    domains, _  = read_targets(options, accept_keys=("domains",),  cap=ipol.get("max_targets") or 10000)
    if not urls and not domains:
        raise ValidationError("Provide URLs or domains to crawl.", "INVALID_PARAMS", "no input")

    # runtime knobs
    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=50,  kind="int") or 50
    depth     = clamp_from_constraints(options, "depth",     policy.get("runtime_constraints", {}).get("depth"),     default=3,   kind="int") or 3
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=15,  kind="int") or 15
    silent    = bool(options.get("silent", True))

    # write inputs (katana supports -u or -list)
    args: List[str] = [exe, "-no-color", "-nc", "-d", str(depth), "-t", str(threads), "-timeout", str(timeout_s)]
    if silent: args.append("-silent")

    if urls:
        fp = Path(work_dir) / "katana_urls.txt"
        fp.write_text("\n".join(urls), encoding="utf-8")
        args += ["-list", str(fp)]
    else:
        # Katana can take domains with -u (it will probe http/https) — better to be explicit
        fp = Path(work_dir) / "katana_domains.txt"
        fp.write_text("\n".join(domains), encoding="utf-8")
        args += ["-list", str(fp)]

    # run
    timeout = min(HARD_TIMEOUT, max(timeout_s, 5) + 300)
    rc, out, _ms = run_cmd(args, timeout_s=timeout, cwd=work_dir)
    outfile = write_output_file(work_dir, "katana_output.txt", out or "")

    discovered = _parse_urls(out)
    endpoints, params = _derive_endpoints_params(discovered)

    status = "ok" if rc == 0 else "error"
    msg = f"{len(discovered)} urls, {len(endpoints)} endpoints, {len(params)} params"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    urls=discovered, endpoints=endpoints, params=params,
                    error_reason=None if rc == 0 else "OTHER")
