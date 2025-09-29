# tools/alltools/tools/services_to_urls.py
from __future__ import annotations
from typing import List, Tuple
from ._common import (
    ensure_work_dir, read_targets, PORT_RE, finalize, ValidationError, now_ms
)

# Simple HTTP(S) guesser for common ports
HTTP_PORTS  = {80, 8080, 8000, 8008, 3000, 8888}
HTTPS_PORTS = {443, 8443, 9443, 444}

def _to_url(host: str, port: int) -> str | None:
    if port in HTTPS_PORTS:
        return f"https://{host}:{port}" if port != 443 else f"https://{host}"
    if port in HTTP_PORTS:
        return f"http://{host}:{port}" if port != 80 else f"http://{host}"
    # non-http services are ignored by design (this tool is for web paths)
    return None

def _from_services(services: List[str]) -> List[str]:
    urls: List[str] = []
    seen = set()
    for s in services or []:
        m = PORT_RE.match(s.strip())
        if not m:
            continue
        host, port = m.group(1), int(m.group(2))
        u = _to_url(host, port)
        if not u: 
            continue
        if u not in seen:
            seen.add(u); urls.append(u)
    return urls

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    ensure_work_dir(options, "services_to_urls")  # no fs i/o needed
    services, _ = read_targets(options, accept_keys=("services",), cap=100000)
    ports, _    = read_targets(options, accept_keys=("ports",),    cap=100000)

    if not services and not ports:
        raise ValidationError("No services/ports provided.", "INVALID_PARAMS", "no input")

    # Prefer services; if only ports given, treat them as services
    use = services or ports
    urls = _from_services(use)

    status = "ok"
    msg = f"{len(urls)} urls"
    return finalize(status, msg, options, "services_to_urls", t0, "", output_file=None, urls=urls)
