# tools/alltools/tools/subfinder.py
from __future__ import annotations
import os
from pathlib import Path
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, classify_domains,
    coerce_int_range, run_cmd, write_output_file, finalize, ValidationError
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 300  # absolute ceiling regardless of user input

def run_scan(options: dict) -> dict:
    """
    subfinder adapter
    Accepts domains from injected lists, file, or manual input.
    Returns typed 'domains' and an artifact file with raw output.
    """
    print(1)
    t0 = int(os.times().elapsed * 1000) if hasattr(os, "times") else 0
    print(1)
    work_dir = ensure_work_dir(options)
    slug   = options.get("tool_slug", "subfinder")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol   = policy.get("input_policy", {})
    rcons  = policy.get("runtime_constraints", {})
    bins   = (policy.get("binaries") or {}).get("names") or ["subfinder"]
    print(2)
    exe = None
    print(2)
    for b in bins:
        exe = resolve_bin(b)
        if exe:
            break
    print(3)
    if not exe:
        return finalize("error", "Subfinder is not installed or not found in PATH.",
                        options, command="subfinder", t0_ms=t0, raw_out="",
                        error_reason="INVALID_PARAMS", error_detail="which(subfinder)=None")
    print(3)


    try:
        print(4)

        print(4)

        raw_targets, source = read_targets(
            options,
            accept_keys=tuple(ipol.get("accepts") or ("domains",)),
            file_max_bytes=ipol.get("file_max_bytes", 200_000),
            cap=ipol.get("max_targets", 50),
        )
        print(5)

        if not raw_targets:
            raise ValidationError("At least one domain is required.", "INVALID_PARAMS", "no input")

        # 3) Validate/normalize domains
        valid, invalid, dup_count = classify_domains(raw_targets)
        print(5)
        if invalid:
            # policy: hard-reject if any invalid in the input
            raise ValidationError(
                f"{len(invalid)} invalid domains found",
                "INVALID_PARAMS",
                ", ".join(invalid[:10])
            )
        print(6)
        max_dom = ipol.get("max_targets", 50)
        if len(valid) > max_dom:
            raise ValidationError(
                f"Too many domains: {len(valid)} (max {max_dom})",
                "TOO_MANY_DOMAINS",
                f"{len(valid)}>{max_dom}"
            )

        print(6)

        timeout_s = clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=60, kind="int")
        threads   = clamp_from_constraints(options, "threads",   rcons.get("threads"),   default=10, kind="int")
        timeout_s = min(timeout_s, HARD_TIMEOUT)  # hard ceiling remains

        all_src   = bool(options.get("all_sources", False))
        silent    = bool(options.get("silent", True))
        print(7)

        # 5) Build command
        args = [exe]
        if silent:   args.append("-silent")
        if all_src:  args.append("-all")
        args += ["-t", str(threads), "-timeout", str(timeout_s), "-nc"]
        print(7)

        # decide whether to pass as -d (many times) or via temp file (-dL)
        if len(valid) <= 5:
            for d in valid:
                args += ["-d", d]
        else:
            targets_txt = Path(work_dir) / "subfinder_targets.txt"
            targets_txt.write_text("\n".join(valid), encoding="utf-8", errors="ignore")
            args += ["-dL", str(targets_txt)]

        print(8)
        # 6) Execute
        rc, out, ms = run_cmd(args, timeout_s=min(timeout_s, HARD_TIMEOUT), cwd=work_dir)

        # 7) Parse output (one domain per line)
        lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
        got_valid, _, _ = classify_domains(lines)

        # 8) Persist artifact and finalize
        outfile = write_output_file(work_dir, "subfinder_output.txt", out or "")
        print(8)
        if rc != 0:
            return finalize(
                "error", f"Subfinder error (exit={rc})",
                options, " ".join(args), t0, out, output_file=outfile,
                error_reason="OTHER", error_detail=(lines[:5] and "\n".join(lines[:5])) or None
            )
        msg = f"Found {len(got_valid)} subdomains (dup:{max(0, len(lines)-len(got_valid))}, invalid dropped:{0})"
        print(9)
        return finalize(
            "ok", msg, options, " ".join(args), t0, out, output_file=outfile,
            domains=got_valid
        )

    except ValidationError as ve:
        print(9)
        return finalize(
            "error", ve.message, options, "subfinder", t0, raw_out="",
            error_reason=ve.reason, error_detail=ve.detail
        )
    except Exception as e:
        print(10)
        return finalize(
            "error", "Unexpected error while running subfinder",
            options, "subfinder", t0, raw_out=str(e), error_reason="OTHER", error_detail=repr(e)
        )
