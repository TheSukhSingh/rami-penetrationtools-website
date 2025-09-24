from __future__ import annotations
import os
from pathlib import Path
from ._common import (
    resolve_bin, ensure_work_dir, read_targets, classify_domains,
    run_cmd, write_output_file, finalize, ValidationError, now_ms,  # <-- add now_ms
)
from tools.policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 300  # absolute ceiling

def run_scan(options: dict) -> dict:
    t0 = now_ms()                                 # <-- use common clock
    work_dir = ensure_work_dir(options)
    slug   = options.get("tool_slug", "subfinder")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol   = policy.get("input_policy", {}) or {}
    rcons  = policy.get("runtime_constraints", {}) or {}

    # Resolve executable with fallback
    bin_candidates = (policy.get("binaries") or {}).get("names") or ["subfinder", "subfinder.exe"]
    exe = resolve_bin(*bin_candidates)
    if not exe:
        return finalize(
            "error",
            "Subfinder is not installed or not on PATH",
            options,
            "subfinder",
            t0,
            raw_out="Executable not found. Tried: " + ", ".join(bin_candidates),
            error_reason="NOT_INSTALLED",
            error_detail="resolve_bin returned None"
        )

    try:
        # 1) Collect input
        raw_targets, source = read_targets(
            options,
            accept_keys=tuple(ipol.get("accepts") or ("domains",)),
            file_max_bytes=ipol.get("file_max_bytes", 200_000),
            cap=ipol.get("max_targets", 50),
        )
        if not raw_targets:
            raise ValidationError("At least one domain is required.", "INVALID_PARAMS", "no input")

        # 2) Validate/normalize
        valid, invalid, _ = classify_domains(raw_targets)
        if invalid:
            raise ValidationError(
                f"{len(invalid)} invalid domains found",
                "INVALID_PARAMS",
                ", ".join(invalid[:10])
            )
        max_dom = ipol.get("max_targets", 50)
        if len(valid) > max_dom:
            raise ValidationError(
                f"Too many domains: {len(valid)} (max {max_dom})",
                "TOO_MANY_DOMAINS",
                f"{len(valid)}>{max_dom}"
            )

        # 3) Runtime params
        timeout_s = clamp_from_constraints(options, "timeout_s", rcons.get("timeout_s"), default=60, kind="int")
        threads   = clamp_from_constraints(options, "threads",   rcons.get("threads"),   default=10, kind="int")
        timeout_s = min(timeout_s, HARD_TIMEOUT)
        all_src   = bool(options.get("all_sources", False))
        silent    = bool(options.get("silent", True))

        # 4) Build command
        args = [exe]
        if silent:  args.append("-silent")
        if all_src: args.append("-all")
        args += ["-t", str(threads), "-timeout", str(timeout_s)]
        # NOTE: remove "-nc" unless you’ve confirmed it exists in your subfinder build.

        # Pass domains
        if len(valid) <= 5:
            for d in valid:
                args += ["-d", d]
        else:
            targets_txt = Path(work_dir) / "subfinder_targets.txt"
            targets_txt.write_text("\n".join(valid), encoding="utf-8", errors="ignore")
            args += ["-dL", str(targets_txt)]

        # 5) Execute
        rc, out, ms = run_cmd(args, timeout_s=timeout_s, cwd=work_dir)

        # 6) Parse + persist
        lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
        tmp = classify_domains(lines)
        got_valid = tmp[0] if isinstance(tmp, (list, tuple)) else []
        outfile = write_output_file(work_dir, "subfinder_output.txt", out or "")

        if rc != 0:
            return finalize(
                "error", f"Subfinder error (exit={rc})",
                options, " ".join(args), t0, out, output_file=outfile,
                error_reason="OTHER",
                error_detail=(lines[:5] and "\n".join(lines[:5])) or None
            )

        return finalize(
            "ok",
            f"Found {len(got_valid)} subdomains",
            options, " ".join(args), t0, out,
            output_file=outfile,
            domains=got_valid
        )

    except ValidationError as ve:
        return finalize(
            "error", ve.message, options, "subfinder", t0, raw_out="",
            error_reason=ve.reason, error_detail=ve.detail
        )
    except Exception as e:
        return finalize(
            "error", "Unexpected error while running subfinder",
            options, "subfinder", t0, raw_out=str(e),
            error_reason="OTHER", error_detail=repr(e)
        )
