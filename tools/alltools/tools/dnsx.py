# tools/alltools/tools/dnsx.py
from __future__ import annotations
import os, shlex
from pathlib import Path
from typing import Dict, Any, List, Tuple
from tools.policies import get_effective_policy, clamp_from_constraints 

from ._common import (
    resolve_bin, ValidationError, now_ms, ensure_work_dir, write_output_file,
    read_domains_validated, coerce_int_range, run_cmd, finalize, IP_RE
)

def _parse_dnsx_output(raw: str) -> Tuple[List[str], List[str]]:
    """
    dnsx typically prints lines like:
      example.com 93.184.216.34
      a.example.com 2606:2800:220:1:248:1893:25c8:1946
    Heuristic: first token that isn't an IP -> domain/host; all IPs via regex.
    """
    hosts, ips = [], []
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        # collect IPs
        for ip in IP_RE.findall(ln):
            ips.append(ip)
        # guess host/domain as first token with a dot that isn't an IP
        tok = ln.split()[0]
        # quick reject if token is IP already
        if not IP_RE.fullmatch(tok) and "." in tok:
            hosts.append(tok)
    return hosts, ips

def run_scan(options: Dict[str, Any]) -> Dict[str, Any]:
    t0 = now_ms()
    slug = options.get("tool_slug", "dnsx")
    try:
        # 0) policy (prefer snapshot placed by runner)
        policy = options.get("_policy") or get_effective_policy(slug)
        ipol   = policy.get("input_policy", {})
        rcons  = policy.get("runtime_constraints", {})
        bins   = (policy.get("binaries") or {}).get("names") or ["dnsx"]

        # 1) inputs + validation from policy
        domains, diag = read_domains_validated(
            options,
            cap=ipol.get("max_targets", 50),
            file_max_bytes=ipol.get("file_max_bytes", 100_000),
        )

        # 2) params from field constraints
        threads   = clamp_from_constraints(options, "threads",   rcons.get("threads"),   default=50, kind="int")
        retries   = clamp_from_constraints(options, "retry",     rcons.get("retry"),     default=2,  kind="int")
        timeout_s = clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=45, kind="int")

        # 3) binary (search order from policy)
        bin_path = None
        for b in bins:
            bin_path = resolve_bin(b)
            if bin_path:
                break
        if not bin_path:
            raise ValidationError("dnsx binary not found in PATH", "BIN_NOT_FOUND", ",".join(bins))


        # 4) working dir + input file
        work_dir: Path = ensure_work_dir(options)
        in_file = work_dir / "dnsx_input.txt"
        in_file.write_text("\n".join(domains), encoding="utf-8", errors="ignore")

        # 5) command (dnsx reads -dL file)
        cmd = [
            bin_path,
            "-silent",
            "-resp",
            "-a", "-aaaa",
            "-t", str(threads),
            "-retries", str(retries),
            "-dL", str(in_file),
        ]
        code, raw, _ms = run_cmd(cmd, timeout_s=timeout_s, cwd=work_dir)

        # 6) parse + store
        hosts, ips = _parse_dnsx_output(raw)
        out_file = write_output_file(work_dir, "dnsx_output.txt", raw)

        status  = "success" if code == 0 else "failed"
        message = "Resolved DNS successfully" if code == 0 else f"dnsx exited with code {code}"
        res = finalize(
            status=status,
            message=message,
            options=options,
            command=" ".join(shlex.quote(a) for a in cmd),
            t0_ms=t0,
            raw_out=raw,
            output_file=out_file,
            hosts=hosts,
            domains=hosts,  # treat hostnames as domains for bucketing; your downstream merges them
            ips=ips,
        )
        # attach diagnostics (old behavior)
        res.update(diag)
        return res

    except ValidationError as ve:
        return finalize(
            status="failed",
            message=ve.message,
            options=options,
            command="dnsx",
            t0_ms=t0,
            raw_out="",
            error_reason=ve.reason,
            error_detail=ve.detail,
        )
    except Exception as e:
        return finalize(
            status="failed",
            message="Unhandled exception in dnsx adapter",
            options=options,
            command="dnsx",
            t0_ms=t0,
            raw_out=str(e),
            error_reason="UNHANDLED",
            error_detail=repr(e),
        )
