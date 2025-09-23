# tools/debug_echo.py
def run_scan(options: dict):
    # Accept text via 'text' (or fall back to whatever you prefer)
    text = (options or {}).get("text") or (options or {}).get("input") or ""
    return {
        "status": "ok",
        "message": "Echo complete",
        "output": text,
        "details": {"length": len(text)}
    }
