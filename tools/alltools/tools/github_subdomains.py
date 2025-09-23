# tools/alltools/tools/github_subdomains.py
from __future__ import annotations
import os, shlex
from pathlib import Path
from typing import Dict, Any, List, Tuple
from tools.policies import get_effective_policy, clamp_from_constraints

from ._common import (
    resolve_bin, ValidationError, now_ms, ensure_work_dir, write_output_file,
    read_domains_validated, coerce_int_range, run_cmd, finalize
)

def run_scan(options: Dict[str, Any]) -> Dict[str, Any]:
    t0 = now_ms()
    try:
        # 0) policy
        slug   = options.get("tool_slug", "github_subdomains")
        policy = options.get("_policy") or get_effective_policy(slug)
        ipol   = policy.get("input_policy", {})
        rcons  = policy.get("runtime_constraints", {})
        bins   = (policy.get("binaries") or {}).get("names") or ["github-subdomains"]

        # 1) domains to enumerate org/subdomains for
        domains, diag = read_domains_validated(
            options,
            cap=ipol.get("max_targets", 50),
            file_max_bytes=ipol.get("file_max_bytes", 100_000),
        )

        # 2) params
        timeout_s = clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=60, kind="int")

        # 3) token + binary
        token = (options.get("token") or os.getenv("GITHUB_TOKEN") or "").strip()
        if not token:
            raise ValidationError("Missing GitHub token", "INVALID_PARAMS", "Provide 'token' or GITHUB_TOKEN env var")

        bin_path = None
        for b in bins:
            bin_path = resolve_bin(b)
            if bin_path:
                break
        if not bin_path:
            raise ValidationError("github-subdomains binary not found in PATH", "BIN_NOT_FOUND", ",".join(bins))

        # 4) working dir
        work_dir: Path = ensure_work_dir(options)

        # 5) run once per domain (most tools expect a single -d)
        outs: List[str] = []
        exit_codes: List[int] = []
        env = dict(os.environ)
        env["GITHUB_TOKEN"] = token

        for d in domains:
            # popular syntax: github-subdomains -d example.com
            cmd = [bin_path, "-d", d]
            code, raw, _ms = run_cmd(cmd, timeout_s=timeout_s, cwd=work_dir, env=env)
            outs.append(raw or "")
            exit_codes.append(code)

        raw_all = "\n".join(outs)
        # treat every non-empty token with a dot as a host (very conservative)
        hosts = []
        for ln in raw_all.splitlines():
            ln = ln.strip()
            if ln and "." in ln and " " not in ln:
                hosts.append(ln)

        out_file = write_output_file(work_dir, "github_subdomains_output.txt", raw_all)

        any_fail = any(c != 0 for c in exit_codes)
        status  = "success" if not any_fail else "failed"
        message = "Enumerated subdomains from GitHub" if not any_fail else f"github-subdomains had {sum(1 for c in exit_codes if c!=0)} failures"

        res = finalize(
            status=status,
            message=message,
            options=options,
            command=" && ".join(" ".join(shlex.quote(a) for a in [bin_path, "-d", d]) for d in domains) or "github-subdomains",
            t0_ms=t0,
            raw_out=raw_all,
            output_file=out_file,
            hosts=hosts,
            domains=hosts,
        )
        res.update(diag)
        return res

    except ValidationError as ve:
        return finalize(
            status="failed",
            message=ve.message,
            options=options,
            command="github-subdomains",
            t0_ms=t0,
            raw_out="",
            error_reason=ve.reason,
            error_detail=ve.detail,
        )
    except Exception as e:
        return finalize(
            status="failed",
            message="Unhandled exception in github-subdomains adapter",
            options=options,
            command="github-subdomains",
            t0_ms=t0,
            raw_out=str(e),
            error_reason="UNHANDLED",
            error_detail=repr(e),
        )
