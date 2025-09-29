# tools/alltools/tools/naabu.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, PORT_RE,
    run_cmd, write_output_file, finalize, ValidationError, now_ms, DOMAIN_RE, IPV4_RE, IPV6_RE
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 600  # seconds

def _parse_naabu(text: str) -> Tuple[List[str], List[str]]:
    """
    Default naabu -silent output: ip:port
    We'll emit:
      - ports:   ["host:port"]
      - services:["host:port"]  (scheme unknown; services_to_urls will guess HTTP(S) later)
    """
    ports: List[str] = []
    services: List[str] = []
    seen = set()
    for ln in (text or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        m = PORT_RE.match(s)
        if not m:
            # some naabu builds output "host:port/open/tcp"
            # try to salvage first host:port
            if "/" in s and ":" in s:
                s = s.split("/")[0]
                m = PORT_RE.match(s)
            if not m:
                continue
        hostport = f"{m.group(1)}:{m.group(2)}"
        if hostport in seen:
            continue
        seen.add(hostport)
        ports.append(hostport)
        services.append(hostport)
    return ports, services

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "naabu")
    slug = options.get("tool_slug", "naabu")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("naabu", "naabu.exe")
    if not exe:
        return finalize("error", "naabu not installed", options, "naabu", t0, "", error_reason="NOT_INSTALLED")

    raw, _ = read_targets(options, accept_keys=("hosts", "ips", "domains"), cap=ipol.get("max_targets") or 200)
    if not raw:
        raise ValidationError("At least one host/ip/domain is required.", "INVALID_PARAMS", "no input")

    # runtime
    rate      = clamp_from_constraints(options, "rate",      policy.get("runtime_constraints", {}).get("rate"),      default=1000, kind="int") or 1000
    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=90,   kind="int") or 90
    top_ports = clamp_from_constraints(options, "top_ports", policy.get("runtime_constraints", {}).get("top_ports"), default=100,  kind="int") or 100
    retries   = clamp_from_constraints(options, "retries",   policy.get("runtime_constraints", {}).get("retries"),   default=1,   kind="int") or 1
    silent    = bool(options.get("silent", True))

    fp = Path(work_dir) / "naabu_targets.txt"
    fp.write_text("\n".join(raw), encoding="utf-8")

    args: List[str] = [
        exe, "-list", str(fp),
        "-top-ports", str(top_ports),
        "-rate", str(rate),
        "-retries", str(retries),
        "-verify"  # better signal: actually connect to confirm
    ]
    if silent: args.append("-silent")

    # execute
    timeout = min(HARD_TIMEOUT, max(timeout_s, 5) + 60)
    rc, out, _ms = run_cmd(args, timeout_s=timeout, cwd=work_dir)
    outfile = write_output_file(work_dir, "naabu_output.txt", out or "")

    ports, services = _parse_naabu(out)
    status = "ok" if rc == 0 else "error"
    msg = f"{len(services)} services"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile,
                    ports=ports, services=services, error_reason=None if rc == 0 else "OTHER")
