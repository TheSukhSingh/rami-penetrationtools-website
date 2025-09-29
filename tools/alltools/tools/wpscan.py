from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json
import os

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

HARD_TIMEOUT = 1800

def _extract_wpscan(data: Dict[str, Any]) -> (List[str], List[str]):
    techs: List[str] = ["wordpress"]
    vulns: List[str] = []

    # site info
    v = None
    try:
        v = (data.get("version") or {}).get("number")
    except Exception:
        v = None
    if v:
        techs.append(f"wordpress@{v}")

    # interesting findings
    for item in (data.get("interesting_findings") or []):
        t = item.get("to_s") or item.get("name") or item.get("url")
        if t and t not in techs:
            techs.append(str(t))

    # plugins
    plugins = data.get("plugins") or {}
    for name, pdata in plugins.items():
        pver = (pdata.get("version") or {}).get("number")
        lib = f"{name}@{pver}" if pver else name
        if lib not in techs:
            techs.append(lib)
        for v in (pdata.get("vulnerabilities") or []):
            title = v.get("title") or v.get("name") or v.get("id") or "Plugin vulnerability"
            ref = None
            ids = v.get("references") or {}
            cves = ids.get("cve") or ids.get("CVE")
            if cves:
                ref = cves[0] if isinstance(cves, list) else cves
            msg = f"{lib}: {title}" + (f" ({ref})" if ref else "")
            vulns.append(msg)

    # themes
    themes = data.get("themes") or {}
    for name, tdata in themes.items():
        tver = (tdata.get("version") or {}).get("number")
        lib = f"{name}@{tver}" if tver else name
        if lib not in techs:
            techs.append(lib)
        for v in (tdata.get("vulnerabilities") or []):
            title = v.get("title") or v.get("name") or v.get("id") or "Theme vulnerability"
            ref = None
            ids = v.get("references") or {}
            cves = ids.get("cve") or ids.get("CVE")
            if cves:
                ref = cves[0] if isinstance(cves, list) else cves
            msg = f"{lib}: {title}" + (f" ({ref})" if ref else "")
            vulns.append(msg)

    return techs, vulns

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "wpscan")
    slug = options.get("tool_slug", "wpscan")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("wpscan")
    if not exe:
        return finalize("error", "wpscan not installed", options, "wpscan", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 1000)
    if not urls:
        raise ValidationError("Provide WordPress site URLs.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=300, kind="int") or 300

    token = options.get("api_token") or os.environ.get("WPSCAN_API_TOKEN")

    techs: List[str] = []
    vulns: List[str] = []
    all_raw = []
    used_cmd = ""
    for u in urls:
        args = [exe, "--url", u, "--no-banner", "--format", "json"]
        if token:
            args += ["--api-token", token]
        used_cmd = " ".join(args[:2] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s), cwd=work_dir)
        if out:
            all_raw.append(out)
            try:
                data = json.loads(out)
                t, v = _extract_wpscan(data)
                techs.extend(t); vulns.extend(v)
            except Exception:
                pass

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "wpscan_output.json", raw or "")

    # de-dup
    seen = set(); techs = [x for x in techs if not (x in seen or seen.add(x))]
    seen = set(); vulns = [x for x in vulns if not (x in seen or seen.add(x))]

    status = "ok"
    msg = f"{len(techs)} tech, {len(vulns)} vulns"
    return finalize(status, msg, options, used_cmd or "wpscan", t0, raw, output_file=outfile,
                    tech_stack=techs, vulns=vulns)
