# tools/alltools/tools/dnsx.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from ._common import (
    resolve_bin, ensure_work_dir, read_targets,
    DOMAIN_RE, IPV4_RE, IPV6_RE, run_cmd, write_output_file,
    finalize, ValidationError, now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 300  # seconds

def _parse_dnsx_lines(text: str) -> Tuple[List[str], List[str]]:
    """
    dnsx lines look like:
      sub.example.com A 1.2.3.4
      api.example.org AAAA 2606:4700:...:abcd
    We'll:
      - collect left token as a domain if it looks like one
      - collect any IPv4/6 tokens as ips
    """
    domains: List[str] = []
    ips: List[str] = []
    seen_d = set(); seen_i = set()
    for raw in (text or "").splitlines():
        ln = (raw or "").strip()
        if not ln:
            continue
        # first token (leftmost) is usually the fqdn
        first = ln.split()[0]
        if DOMAIN_RE.match(first):
            d = first.lower()
            if d not in seen_d:
                seen_d.add(d); domains.append(d)
        # collect any IP tokens
        for tok in ln.split():
            t = tok.strip("[]()")
            if IPV4_RE.match(t) or IPV6_RE.match(t):
                if t not in seen_i:
                    seen_i.add(t); ips.append(t)
    return domains, ips

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "dnsx")
    slug = options.get("tool_slug", "dnsx")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("dnsx", "dnsx.exe")
    if not exe:
        return finalize("error", "dnsx not installed", options, "dnsx", t0, "", error_reason="NOT_INSTALLED")

    # inputs: domains or hosts (we treat hosts as domains for resolution)
    raw, _ = read_targets(options, accept_keys=("domains", "hosts"), cap=ipol.get("max_targets") or 100)
    if not raw:
        raise ValidationError("At least one domain/host is required.", "INVALID_PARAMS", "no input")

    # threads / timeout
    threads   = clamp_from_constraints(options, "threads",   policy.get("runtime_constraints", {}).get("threads"),   default=50, kind="int") or 50
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=60, kind="int") or 60
    retries   = clamp_from_constraints(options, "retries",   policy.get("runtime_constraints", {}).get("retries"),   default=2,  kind="int") or 2
    silent    = bool(options.get("silent", True))

    # write input list
    fp = Path(work_dir) / "dnsx_targets.txt"
    fp.write_text("\n".join(raw), encoding="utf-8")

    # args
    args: List[str] = [exe, "-l", str(fp), "-a", "-retries", str(retries), "-t", str(threads)]
    if silent:
        args.append("-silent")

    # run
    timeout = min(HARD_TIMEOUT, max(timeout_s, 5) + 30)
    rc, out, _ms = run_cmd(args, timeout_s=timeout, cwd=work_dir)
    outfile = write_output_file(work_dir, "dnsx_output.txt", out or "")

    # parse → domains + ips
    domains, ips = _parse_dnsx_lines(out)

    status = "ok" if rc == 0 else "error"
    msg = f"{len(domains)} domains, {len(ips)} ips"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    domains=domains, ips=ips, error_reason=None if rc == 0 else "OTHER")
