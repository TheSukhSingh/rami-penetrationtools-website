import os
import time
from urllib.parse import urlunparse

from tools.alltools._manifest_utils import ensure_work_dir, write_lines, finalize_manifest

# Common web ports mapping (feel free to expand)
HTTP_PORTS  = {80, 8080, 8000, 3000, 5000, 8888, 81}
HTTPS_PORTS = {443, 8443, 9443}

def _to_url(host, port):
    try:
        p = int(port)
    except Exception:
        return None
    scheme = "https" if p in HTTPS_PORTS else "http" if p in HTTP_PORTS else None
    if not scheme:
        # heuristic: unknown port? still try http
        scheme = "http"
    # urlunparse wants a netloc; we skip path/query
    return f"{scheme}://{host}:{p}"

def run_scan(data):
    """
    Input expectation:
      - either 'file_path' pointing to lines of 'host:port'
      - or 'services' list in data (runner may inject from previous step)
    Output:
      - 'urls' list + 'output_file' pointing to a canonical txt
    """
    started = time.time()
    work_dir = ensure_work_dir(data, "services_to_urls")

    # Collect services
    services = []
    fp = data.get("file_path")
    if fp and os.path.exists(fp):
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            services = [ln.strip() for ln in f if ln.strip()]
    else:
        services = data.get("services") or data.get("ports") or []

    urls = []
    for ln in services:
        if ":" not in ln:
            continue
        host, port = ln.split(":", 1)
        host = host.strip()
        port = port.strip()
        u = _to_url(host, port)
        if u:
            urls.append(u)

    # Persist
    ofile = write_lines(work_dir, "services_to_urls", "urls", urls)

    # Standard manifest
    return finalize_manifest(
        slug="services_to_urls",
        options=data,
        command_str="(internal) services_to_urls",
        started_at=started,
        stdout="\n".join(urls) if urls else "No URLs derived.",
        parsed={"urls": urls},
        primary="urls",
        extra={"execution_ms": int((time.time() - started) * 1000)},
    )
