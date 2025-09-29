# tools/alltools/tools/gau.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlsplit, parse_qsl
from ._common import (
    resolve_bin, ensure_work_dir, read_targets,
    run_cmd, write_output_file, finalize, ValidationError, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 900  # seconds

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

def _parse_gau(text: str) -> List[str]:
    urls: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        # gau (plain) returns URLs per line
        if not (s.startswith("http://") or s.startswith("https://")):
            continue
        if s in seen:
            continue
        seen.add(s); urls.append(s)
    return urls

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "gau")
    slug = options.get("tool_slug", "gau")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("gau", "gau.exe")
    if not exe:
        return finalize("error", "gau not installed", options, "gau", t0, "", error_reason="NOT_INSTALLED")

    domains, _ = read_targets(options, accept_keys=("domains","hosts"), cap=ipol.get("max_targets") or 500)
    if not domains:
        raise ValidationError("Provide at least one domain/host.", "INVALID_PARAMS", "no input")

    include_subs = bool(options.get("include_subdomains", True))
    timeout_s    = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    # Write list (gau wants input via stdin or -subs -o/-oD; we'll just call once per domain for simplicity)
    fp = Path(work_dir) / "gau_targets.txt"
    fp.write_text("\n".join(domains), encoding="utf-8")

    args: List[str] = [exe]
    if include_subs:
        args.append("--subs")
    # Read from file via shell redirection is cumbersome in subprocess; call gau per domain
    # but to keep things simple and fast, we’ll cat the file and pipe it.
    shell_cmd = f"type {fp}" if (Path().anchor and os.name == "nt") else f"cat {fp}"
    # Fallback to multiple invocations if shell is restricted; instead, just pass first N domains inline.
    # Simpler approach: invoke once per domain:
    out_all = []
    for d in domains:
        per_args = args + [d]
        rc, out, _ms = run_cmd(per_args, timeout_s=min(HARD_TIMEOUT, timeout_s + 30), cwd=work_dir)
        out_all.append(out or "")
    out = "\n".join(out_all)
    outfile = write_output_file(work_dir, "gau_output.txt", out)

    urls = _parse_gau(out)
    endpoints, params = _derive_endpoints_params(urls)

    status = "ok"
    msg = f"{len(urls)} urls, {len(endpoints)} endpoints, {len(params)} params"
    return finalize(status, msg, options, " ".join(args + ["<domains>"]), t0, out, output_file=outfile,
                    urls=urls, endpoints=endpoints, params=params)
