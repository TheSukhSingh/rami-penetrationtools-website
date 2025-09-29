# tools/alltools/tools/httpx.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, DOMAIN_RE, PORT_RE,
    run_cmd, write_output_file, finalize, ValidationError, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 600  # seconds

HTTP_PORTS  = {80, 8080, 8000, 8008, 3000, 8888}
HTTPS_PORTS = {443, 8443, 9443, 444}

def _guess_url_from_host(h: str) -> List[str]:
    # When only a bare host/domain was supplied (not recommended),
    # probe both http and https.
    return [f"http://{h}", f"https://{h}"]

def _guess_url_from_service(s: str) -> List[str]:
    m = PORT_RE.match(s.strip())
    if not m:
        return []
    host, port_s = m.group(1), m.group(2)
    port = int(port_s)
    if port in HTTPS_PORTS:
        return [f"https://{host}:{port}" if port != 443 else f"https://{host}"]
    if port in HTTP_PORTS:
        return [f"http://{host}:{port}" if port != 80 else f"http://{host}"]
    return []

def _collect_candidate_urls(options: dict, cap: int) -> List[str]:
    # Prefer explicit urls; else try services; else as a last resort, domains/hosts.
    urls, _     = read_targets(options, accept_keys=("urls",),     cap=cap)
    services, _ = read_targets(options, accept_keys=("services",), cap=cap)
    hosts, _    = read_targets(options, accept_keys=("hosts","domains"), cap=cap)

    cand: List[str] = []
    if urls:
        cand.extend(urls)
    elif services:
        for s in services:
            cand.extend(_guess_url_from_service(s))
    elif hosts:
        for h in hosts:
            cand.extend(_guess_url_from_host(h))
    # de-dup preserve order
    seen = set(); uniq: List[str] = []
    for u in cand:
        if u not in seen:
            seen.add(u); uniq.append(u)
    return uniq[:cap]

def _parse_httpx(text: str) -> List[str]:
    # httpx -silent prints URLs; sometimes with status code (if flags change),
    # We keep only tokens that start with http
    out: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        # split on whitespace; find the first http(s) token
        tok = None
        for t in s.split():
            if t.startswith("http://") or t.startswith("https://"):
                tok = t; break
        if not tok:
            continue
        if tok in seen:
            continue
        seen.add(tok); out.append(tok)
    return out

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "httpx")
    slug = options.get("tool_slug", "httpx")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("httpx", "httpx.exe")
    if not exe:
        return finalize("error", "httpx not installed", options, "httpx", t0, "", error_reason="NOT_INSTALLED")

    cand = _collect_candidate_urls(options, cap=ipol.get("max_targets") or 10000)
    if not cand:
        raise ValidationError("No candidate URLs/hosts/services to probe.", "INVALID_PARAMS", "no input")

    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=50,  kind="int") or 50
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=10,  kind="int") or 10
    silent    = bool(options.get("silent", True))

    fp = Path(work_dir) / "httpx_targets.txt"
    fp.write_text("\n".join(cand), encoding="utf-8")

    # flags: -silent keeps just URLs; -status-code would add codes, but parser is robust either way.
    args: List[str] = [exe, "-l", str(fp), "-follow-redirects", "-no-color", "-t", str(threads), "-timeout", str(timeout_s)]
    if silent:
        args.append("-silent")

    timeout = min(HARD_TIMEOUT, max(timeout_s, 5) + 120)
    rc, out, _ms = run_cmd(args, timeout_s=timeout, cwd=work_dir)
    outfile = write_output_file(work_dir, "httpx_output.txt", out or "")

    alive = _parse_httpx(out)

    status = "ok" if rc == 0 else "error"
    msg = f"{len(alive)} alive urls"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    urls=alive, error_reason=None if rc == 0 else "OTHER")
