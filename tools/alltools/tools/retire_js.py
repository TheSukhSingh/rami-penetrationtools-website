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

HARD_TIMEOUT = 900

def _parse_retire_json(blob: str) -> (List[str], List[str]):
    techs: List[str] = []
    vulns: List[str] = []
    try:
        data = json.loads(blob)
    except Exception:
        return techs, vulns
    items = data if isinstance(data, list) else [data]
    for it in items:
        stack = [it]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if 'component' in cur:
                    name = str(cur.get('component'))
                    ver = cur.get('version')
                    lib = f"{name}@{ver}" if ver else name
                    if lib and lib not in techs:
                        techs.append(lib)
                    vlist = cur.get('vulnerabilities') or []
                    for v in vlist:
                        cve = None
                        if isinstance(v, dict):
                            cve = v.get('identifiers', {}).get('CVE') or v.get('cve') or v.get('id') or v.get('summary')
                        msg = f"{lib}: {cve}" if cve else f"{lib}: vulnerable"
                        vulns.append(str(msg))
                else:
                    for v in cur.values():
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)
    return techs, vulns

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "retire_js")
    slug = options.get("tool_slug", "retire_js")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("retire", "retire.bat", "retire.cmd", "retire.exe")
    if not exe:
        return finalize("error", "retire.js not installed", options, "retire", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 2000)
    if not urls:
        raise ValidationError("Provide URLs to scan with retire.js.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    all_out_json = []
    used_cmd = ""
    for u in urls:
        args = [exe, "--url", u, "--outputformat", "json"]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 60), cwd=work_dir)
        if out:
            all_out_json.append(out)

    raw = "\n".join(all_out_json)
    outfile = write_output_file(work_dir, "retire_output.json", raw or "")

    techs: List[str] = []
    vulns: List[str] = []
    for chunk in all_out_json:
        t, v = _parse_retire_json(chunk)
        techs.extend(t); vulns.extend(v)

    seen = set()
    techs = [x for x in techs if not (x in seen or seen.add(x))]
    seen = set()
    vulns = [x for x in vulns if not (x in seen or seen.add(x))]

    status = "ok"
    msg = f"{len(techs)} libs, {len(vulns)} vulns"
    return finalize(status, msg, options, used_cmd or "retire", t0, raw, output_file=outfile,
                    tech_stack=techs, vulns=vulns)
