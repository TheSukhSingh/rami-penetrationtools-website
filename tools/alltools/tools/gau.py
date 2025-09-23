# tools/alltools/tools/gau.py
from __future__ import annotations
import os, shlex
from pathlib import Path
from typing import Dict, Any, List, Tuple
from tools.policies import get_effective_policy, clamp_from_constraints

from ._common import (
    resolve_bin, ValidationError, now_ms, ensure_work_dir, write_output_file,
    read_domains_validated, coerce_int_range, run_cmd, finalize, URL_RE
)

def _extract_urls(raw: str) -> List[str]:
    urls = []
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        urls.extend(URL_RE.findall(ln))
    # de-dupe (preserve order)
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            uniq.append(u); seen.add(u)
    return uniq

def run_scan(options: Dict[str, Any]) -> Dict[str, Any]:
    t0 = now_ms()
    try:
        # 0) policy
        slug   = options.get("tool_slug", "gau")
        policy = options.get("_policy") or get_effective_policy(slug)
        ipol   = policy.get("input_policy", {})
        rcons  = policy.get("runtime_constraints", {})
        bins   = (policy.get("binaries") or {}).get("names") or ["gau"]

        # 1) inputs + validation
        domains, diag = read_domains_validated(
            options,
            cap=ipol.get("max_targets", 50),
            file_max_bytes=ipol.get("file_max_bytes", 100_000),
        )

        # 2) params
        timeout_s = clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=60, kind="int")

        # 3) binary
        bin_path = None
        for b in bins:
            bin_path = resolve_bin(b)
            if bin_path:
                break
        if not bin_path:
            raise ValidationError("gau binary not found in PATH", "BIN_NOT_FOUND", ",".join(bins))


        # 4) working dir
        work_dir: Path = ensure_work_dir(options)

        # 5) run once per domain (simple & reliable)
        outs: List[str] = []
        exit_codes: List[int] = []
        for d in domains:
            cmd = [bin_path, d]
            code, raw, _ms = run_cmd(cmd, timeout_s=timeout_s, cwd=work_dir)
            outs.append(raw or "")
            exit_codes.append(code)

        raw_all = "\n".join(outs)
        urls = _extract_urls(raw_all)
        out_file = write_output_file(work_dir, "gau_output.txt", raw_all)

        # success if none failed
        any_fail = any(c != 0 for c in exit_codes)
        status  = "success" if not any_fail else "failed"
        message = "Collected URLs via gau" if not any_fail else f"gau had {sum(1 for c in exit_codes if c!=0)} failures"

        res = finalize(
            status=status,
            message=message,
            options=options,
            command=" && ".join(" ".join(shlex.quote(a) for a in [bin_path, d]) for d in domains) or "gau",
            t0_ms=t0,
            raw_out=raw_all,
            output_file=out_file,
            urls=urls,
            endpoints=urls,  # keep endpoints == urls for now; specialized extraction can split later
        )
        res.update(diag)
        return res

    except ValidationError as ve:
        return finalize(
            status="failed",
            message=ve.message,
            options=options,
            command="gau",
            t0_ms=t0,
            raw_out="",
            error_reason=ve.reason,
            error_detail=ve.detail,
        )
    except Exception as e:
        return finalize(
            status="failed",
            message="Unhandled exception in gau adapter",
            options=options,
            command="gau",
            t0_ms=t0,
            raw_out=str(e),
            error_reason="UNHANDLED",
            error_detail=repr(e),
        )
