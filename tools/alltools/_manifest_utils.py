from __future__ import annotations
import os, re, time, tempfile
from pathlib import Path
from typing import Dict, List, Iterable

# Simple validators for classifying lines
URL_RE    = re.compile(r'(?i)^(?:https?://)[^\s]+$')
IPV4_RE   = re.compile(r'^(?:\d{1,3}\.){3}\d{1,3}$')
DOMAIN_RE = re.compile(
    r'^(?=.{1,253}$)(?!-)(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\.?$'
)
PORT_RE   = re.compile(r'^(.+?):(\d{1,5})$')  # host:port

def _uniq(seq: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for s in seq:
        s = s.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

def ensure_work_dir(options: Dict, slug: str) -> str:
    d = options.get("work_dir")
    if not d:
        d = tempfile.mkdtemp(prefix=f"{slug}_")
    Path(d).mkdir(parents=True, exist_ok=True)
    return d

def write_lines(work_dir: str, slug: str, kind: str, lines: Iterable[str]) -> str:
    lines = _uniq(lines)
    path = Path(work_dir) / f"{slug}_{kind}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

def split_typed(lines: Iterable[str]) -> Dict[str, List[str]]:
    """Classify generic CLI line outputs into typed buckets."""
    urls, ips, domains, hosts, ports, endpoints = [], [], [], [], [], []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if URL_RE.match(s):
            urls.append(s)
            # attempt to derive endpoint path
            try:
                if '/' in s[8:]:
                    endpoints.append("/" + s.split('://', 1)[1].split('/', 1)[1])
            except Exception:
                pass
            continue
        if PORT_RE.match(s):
            ports.append(s)
            host = s.split(':', 1)[0]
            if IPV4_RE.match(host) or DOMAIN_RE.match(host):
                hosts.append(host)
            continue
        if IPV4_RE.match(s):
            ips.append(s)
            hosts.append(s)
            continue
        if DOMAIN_RE.match(s):
            d = s.lower()
            domains.append(d)
            hosts.append(d)
            continue
        if s.startswith('/'):
            endpoints.append(s)

    return {
        "urls": _uniq(urls),
        "ips": _uniq(ips),
        "domains": _uniq(domains),
        "hosts": _uniq(hosts),
        "ports": _uniq(ports),
        "endpoints": _uniq(endpoints),
    }

def finalize_manifest(
    *, slug: str, options: Dict, command_str: str, started_at: float, stdout: str,
    parsed: Dict[str, List[str]] | None = None, primary: str | None = None,
    extra: Dict | None = None
) -> Dict:
    """
    Standard success manifest. Provide 'parsed' with lists for any of:
    urls, domains, hosts, ips, ports, endpoints. 'primary' chooses which
    file path to expose as output_file (if None, first non-empty is used).
    """
    work_dir = ensure_work_dir(options, slug)
    parsed = parsed or {}
    file_map = {}
    for key, vals in parsed.items():
        if vals:
            file_map[key] = write_lines(work_dir, slug, key, vals)

    output_file = None
    if primary and parsed.get(primary):
        output_file = file_map.get(primary)
    else:
        for k in ("urls", "domains", "hosts", "ips", "ports", "endpoints"):
            if parsed.get(k):
                output_file = file_map.get(k)
                break

    exec_ms = int((time.time() - started_at) * 1000)
    manifest = {
        "status": "success",
        "message": "Scan completed successfully.",
        "output": stdout,
        "command": command_str,
        "parameters": {k: v for k, v in (options or {}).items() if k != "work_dir"},
        "execution_ms": exec_ms,
        "output_file": output_file,
    }
    for key, vals in parsed.items():
        if vals:
            manifest[key] = vals if len(vals) <= 500 else vals[:500]
            manifest[f"{key}_count"] = len(vals)

    if extra:
        manifest.update(extra)
    return manifest
