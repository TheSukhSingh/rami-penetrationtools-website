# tools/alltools/tools/nuclei.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 3600  # seconds


def _parse_nuclei_jsonl(blob: str) -> List[str]:
    vulns: List[str] = []
    for ln in (blob or "").splitlines():
        s = (ln or "").strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        tid = obj.get("template-id") or obj.get("id") or "template"
        sev = obj.get("severity") or obj.get("info", {}).get("severity")
        url = obj.get("matched-at") or obj.get("host") or obj.get("url")
        name = obj.get("info", {}).get("name")
        parts = [p for p in [tid, sev, name, url] if p]
        vulns.append(" | ".join(map(str, parts)))
    # de-dup
    seen = set()
    return [x for x in vulns if not (x in seen or seen.add(x))]


def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "nuclei")
    slug = options.get("tool_slug", "nuclei")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("nuclei")
    if not exe:
        return finalize("error", "nuclei not installed", options, "nuclei", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 100000)
    if not urls:
        raise ValidationError("Provide URLs to scan with nuclei.", "INVALID_PARAMS", "no input")

    # knobs
    timeout_s  = clamp_from_constraints(options, "timeout_s",  policy.get("runtime_constraints", {}).get("timeout_s"),  default=20,  kind="int") or 20
    rate       = clamp_from_constraints(options, "rate",       policy.get("runtime_constraints", {}).get("rate"),       default=150, kind="int") or 150
    ctimeout   = clamp_from_constraints(options, "conn_timeout", policy.get("runtime_constraints", {}).get("conn_timeout"), default=10, kind="int") or 10
    templates  = options.get("templates") or []  # optional: folder or list of template paths
    severities = options.get("severities") or []  # e.g., ["critical","high","medium"]

    # input file
    fp = Path(work_dir) / "nuclei_targets.txt"
    fp.write_text("\n".join(urls), encoding="utf-8")

    args: List[str] = [
        exe, "-l", str(fp),
        "-jsonl",
        "-timeout", str(timeout_s),
        "-rate-limit", str(rate),
        "-c", str(ctimeout),
        "-no-color", "-silent",
    ]
    if templates:
        if isinstance(templates, (list, tuple)):
            for t in templates:
                args += ["-t", str(t)]
        else:
            args += ["-t", str(templates)]
    if severities:
        args += ["-severity", ",".join(severities)]

    rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 600), cwd=work_dir)
    outfile = write_output_file(work_dir, "nuclei_output.jsonl", out or "")

    vulns = _parse_nuclei_jsonl(out)
    status = "ok" if (rc == 0 or len(vulns) > 0) else "error"
    msg = f"{len(vulns)} findings"
    return finalize(status, msg, options, " ".join(args), t0, out, output_file=outfile, vulns=vulns,
                    error_reason=None if status == "ok" else "OTHER")
