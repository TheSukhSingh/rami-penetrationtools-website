# tools/alltools/envcheck.py
from __future__ import annotations
from typing import Dict, List
from tools.policies import IO_BASELINE
try:
    # normal relative import inside the tools pkg
    from .tools._common import resolve_bin
except Exception:
    # fallback if running standalone
    from tools.alltools.tools._common import resolve_bin

# Hints per tool slug (expand if you use custom names/paths via policy overlays)
BINARY_HINTS: Dict[str, List[str]] = {
    "subfinder": ["subfinder"],
    "crt_sh": ["curl"],
    "github_subdomains": ["github_subdomains"],
    "theharvester": ["theHarvester", "theharvester"],
    "dnsx": ["dnsx"],
    "naabu": ["naabu"],
    "httpx": ["httpx"],
    "services-to-urls": [],  # pure-python helper
    "gau": ["gau"],
    "katana": ["katana"],
    "gospider": ["gospider"],
    "hakrawler": ["hakrawler"],
    "linkfinder": ["linkfinder", "python3"],
    "arjun": ["arjun"],
    "paramspider": ["paramspider", "python3"],
    "whatweb": ["whatweb"],
    "wafw00f": ["wafw00f"],
    "retire_js": ["retire", "retire.js", "node"],
    "wpscan": ["wpscan"],
    "ffuf": ["ffuf"],
    "gobuster": ["gobuster"],
    "nuclei": ["nuclei"],
    "nikto": ["nikto"],
    "zap": ["zap-baseline.py", "zap-baseline"],
    "dalfox": ["dalfox"],
    "xsstrike": ["python3"],   # run via -m XSStrike if not on PATH
    "s3scanner": ["s3scanner", "python3"],
    "sqlmap": ["sqlmap", "sqlmap.py"],
    "commix": ["commix", "commix.py"],
    "dotdotpwn": ["dotdotpwn", "dotdotpwn.pl"],
    "fuxploider": ["fuxploider", "fuxploider.py"],
    "ssrfmap": ["ssrfmap", "ssrfmap.py"],
    "hydra": ["hydra"],
    "jwt-crack": [],           # pure python wrapper
    "john": ["john"],
    "gowitness": ["gowitness"],
    "report_collate": [],      # pure python
    "qlgraph": [],             # pure python
}

def check_env() -> Dict[str, Dict[str, bool]]:
    report: Dict[str, Dict[str,bool]] = {}
    for slug in IO_BASELINE.keys():
        hints = BINARY_HINTS.get(slug, [])
        ok = True
        if hints:
            ok = any(resolve_bin(h) for h in hints)
        report[slug] = {"installed": bool(ok)}
    return report
