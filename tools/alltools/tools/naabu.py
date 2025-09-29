# tools/alltools/tools/naabu.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import json

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms, DOMAIN_RE, IPV4_RE, IPV6_RE
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 7200

PORT_SCHEMES: Dict[int, str] = {
    80: "http", 8080: "http", 8000: "http", 8888: "http",
    443: "https", 8443: "https",
    22: "ssh", 21: "ftp", 25: "smtp", 110: "pop3", 143: "imap",
    3389: "rdp", 3306: "mysql", 5432: "postgres", 6379: "redis",
    27017: "mongodb",
}

def _pick_host(obj) -> str:
    # prefer "host" (fqdn) else ip
    host = obj.get("host") or obj.get("hostname") or ""
    if host: return str(host)
    return str(obj.get("ip") or "")

def _parse_naabu_jsonl(blob: str) -> (List[str], List[str]):
    ports, services = [], []
    sp, ss = set(), set()
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s: continue
        try:
            obj = json.loads(s)
        except Exception:
            # fallback: text "host:port"
            if ":" in s:
                if s not in sp:
                    sp.add(s); ports.append(s)
            continue
        host = _pick_host(obj)
        port = int(obj.get("port", 0) or 0)
        if not host or not port:
            continue
        pp = f"{host}:{port}"
        if pp not in sp:
            sp.add(pp); ports.append(pp)
        scheme = PORT_SCHEMES.get(port, "tcp")
        svc = f"{scheme}://{host}:{port}"
        if svc not in ss:
            ss.add(svc); services.append(svc)
    return ports, services

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work = ensure_work_dir(options, "naabu")
    slug = options.get("tool_slug", "naabu")
    pol  = options.get("_policy") or get_effective_policy(slug)
    ipol = pol.get("input_policy", {}) or {}

    exe = resolve_bin("naabu", "naabu.exe")
    if not exe:
        return finalize("error", "naabu not installed", options, "naabu", t0, "", error_reason="NOT_INSTALLED")

    targets, _ = read_targets(options, accept_keys=("hosts","ips","domains"), cap=ipol.get("max_targets") or 100000)
    if not targets:
        raise ValidationError("Provide hosts/ips/domains for naabu.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", pol.get("runtime_constraints",{}).get("timeout_s"), default=60, kind="int") or 60
    ports_opt = options.get("ports")          # e.g., "top-1000" or "1-65535" or "80,443"
    exclude   = options.get("exclude_ports")  # optional

    fp = Path(work) / "targets.txt"
    fp.write_text("\n".join(targets), encoding="utf-8")

    args = [exe, "-list", str(fp), "-json", "-silent", "-verify", "-timeout", str(timeout_s)]
    if ports_opt: args += ["-ports", str(ports_opt)]
    if exclude:   args += ["-exclude-ports", str(exclude)]

    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work)
    outfile = write_output_file(work, "naabu_output.jsonl", out or "")

    ports, services = _parse_naabu_jsonl(out or "")
    msg = f"{len(ports)} open, {len(services)} services"
    return finalize("ok", msg, options, " ".join(args), t0, out, output_file=outfile,
                    ports=ports, services=services)
