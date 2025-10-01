# scanner/engine_clamav.py
from __future__ import annotations
from flask import current_app

try:
    import clamd  # python-clamd
except Exception:
    clamd = None  # type: ignore

def _clamd_client():
    if not clamd:
        return None
    unix_sock = current_app.config.get("CLAMAV_UNIX_SOCKET")
    host      = current_app.config.get("CLAMAV_HOST")
    port      = int(current_app.config.get("CLAMAV_PORT", 3310) or 3310)
    timeout   = int(current_app.config.get("CLAMAV_TIMEOUT", 2) or 2)
    try:
        if unix_sock:
            client = clamd.ClamdUnixSocket(unix_sock, timeout=timeout)
        elif host:
            client = clamd.ClamdNetworkSocket(host=host, port=port, timeout=timeout)
        else:
            return None
        client.ping()
        return client
    except Exception:
        return None

def scan_path_with_clamav(path: str):
    """
    Returns tuple: (verdict, signature or None, raw_result or None)
    verdict in: 'clean' | 'infected' | 'failed'
    """
    client = _clamd_client()
    if not client:
        return None  # engine not available
    try:
        result = client.scan(path)
        if not result or path not in result:
            return ("failed", None, result)
        status, sig = result[path]
        status_up = str(status or "").upper()
        if status_up == "OK":
            return ("clean", None, result)
        if status_up == "FOUND":
            return ("infected", str(sig or "")[:255], result)
        return ("failed", None, result)
    except Exception as e:
        return ("failed", None, {"error": str(e)})
