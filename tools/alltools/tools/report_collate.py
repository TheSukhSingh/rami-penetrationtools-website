# tools/alltools/tools/report_collate.py
from __future__ import annotations
from typing import List, Dict, Any
import json
import re

try:
    from ._common import (
        ensure_work_dir, read_targets, finalize, write_output_file, now_ms
    )
except ImportError:
    from _common import (
        ensure_work_dir, read_targets, finalize, write_output_file, now_ms
    )

SEV_RE = re.compile(r"(?i)\b(critical|high|medium|low|info)\b")

def _dedupe(lst: List[str]) -> List[str]:
    seen = set(); out = []
    for x in lst or []:
        s = str(x).strip()
        if not s: continue
        if s in seen: continue
        seen.add(s); out.append(s)
    return out

def _severity_of(s: str) -> str:
    m = SEV_RE.search(s or "")
    return (m.group(1).lower() if m else "unknown")

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "report_collate")

    domains, _   = read_targets(options, ("domains",),   cap=200000)
    ips, _       = read_targets(options, ("ips",),       cap=200000)
    urls, _      = read_targets(options, ("urls",),      cap=400000)
    endpoints, _ = read_targets(options, ("endpoints",), cap=400000)
    params, _    = read_targets(options, ("params",),    cap=200000)
    services, _  = read_targets(options, ("services",),  cap=200000)
    techs, _     = read_targets(options, ("tech_stack",),cap=200000)
    vulns, _     = read_targets(options, ("vulns",),     cap=400000)
    exploits, _  = read_targets(options, ("exploit_results",), cap=200000)
    shots, _     = read_targets(options, ("screenshots",), cap=400000)

    # dedupe everything
    domains    = _dedupe(domains)
    ips        = _dedupe(ips)
    urls       = _dedupe(urls)
    endpoints  = _dedupe(endpoints)
    params     = _dedupe(params)
    services   = _dedupe(services)
    techs      = _dedupe([str(t) for t in techs])
    vulns      = _dedupe([str(v) for v in vulns])
    exploits   = _dedupe([str(e) for e in exploits])
    shots      = _dedupe([str(s) for s in shots])

    # severity tally from vuln strings (best-effort)
    sev_counts: Dict[str, int] = {"critical":0,"high":0,"medium":0,"low":0,"info":0,"unknown":0}
    sev_list: List[Dict[str,str]] = []
    for v in vulns:
        sev = _severity_of(v)
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        sev_list.append({"severity": sev, "text": v})

    report: Dict[str, Any] = {
        "summary": {
            "counts": {
                "domains": len(domains), "ips": len(ips), "urls": len(urls),
                "endpoints": len(endpoints), "params": len(params), "services": len(services),
                "tech_stack": len(techs), "vulns": len(vulns), "exploit_results": len(exploits),
                "screenshots": len(shots),
            },
            "severity": sev_counts,
        },
        "domains": domains,
        "ips": ips,
        "urls": urls,
        "endpoints": endpoints,
        "params": params,
        "services": services,
        "tech_stack": techs,
        "vulnerabilities": sev_list,   # keep both structured + original list below
        "vulns_raw": vulns,
        "exploit_results": exploits,
        "screenshots": shots,
    }

    blob = json.dumps(report, indent=2)
    outfp = write_output_file(work_dir, "report.json", blob)
    msg = "report.json created"
    return finalize("ok", msg, options, "report_collate(py)", t0, blob, output_file=outfp)
