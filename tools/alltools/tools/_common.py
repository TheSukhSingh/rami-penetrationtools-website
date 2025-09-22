# tools/alltools/tools/_common.py
from __future__ import annotations
import os, sys, shutil, time, re
from pathlib import Path
from typing import List, Tuple

BUCKET_KEYS = ("domains", "hosts", "ips", "ports", "urls", "endpoints", "findings")

def resolve_bin(*names: str) -> str | None:
    """Return first resolvable binary from names; try .exe on Windows too."""
    for name in names:
        p = shutil.which(name)
        if p:
            return p
        if sys.platform.startswith("win") and not name.lower().endswith(".exe"):
            p = shutil.which(name + ".exe")
            if p:
                return p
    return None

def read_targets_from_options(options: dict) -> Tuple[List[str], str]:
    """
    Returns (targets, source_desc). Supports:
      - options["file_path"] when input_method == "file"
      - options["value"] when input_method == "manual"
    """
    im = (options or {}).get("input_method", "").lower()
    if im == "file" and options.get("file_path") and os.path.exists(options["file_path"]):
        with open(options["file_path"], "r", encoding="utf-8", errors="ignore") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        return lines, f"file:{options['file_path']}"
    val = (options or {}).get("value", "")
    if isinstance(val, str) and val.strip():
        # split by newline/comma/whitespace
        parts = re.split(r"[\s,]+", val.strip())
        parts = [p for p in parts if p]
        return parts, "value"
    return [], "empty"

def ensure_work_dir(options: dict) -> Path:
    wd = Path(options.get("work_dir") or Path(os.getenv("TEMP", "/tmp")) / "hackr_runs").resolve()
    wd.mkdir(parents=True, exist_ok=True)
    return wd

def write_output_file(work_dir: Path, name: str, content: str) -> str:
    out_path = work_dir / name
    out_path.write_text(content, encoding="utf-8", errors="ignore")
    return str(out_path)

def now_ms() -> int:
    return int(time.time() * 1000)

def finalize(status: str, message: str, options: dict, command: str, t0: int, raw_out: str,
             output_file: str | None = None, **buckets) -> dict:
    """
    Standardize manifest shape. Buckets are lists keyed by BUCKET_KEYS.
    """
    out = {
        "status": status,
        "message": message,
        "parameters": {k: options.get(k) for k in sorted(options.keys())},
        "command": command,
        "execution_ms": max(0, now_ms() - t0),
        "output": raw_out or "",
    }
    if output_file:
        out["output_file"] = output_file

    for k in BUCKET_KEYS:
        v = buckets.get(k)
        if v:
            # dedupe preserving order
            seen = set()
            uniq = []
            for it in v:
                if it not in seen:
                    uniq.append(it); seen.add(it)
            out[k] = uniq
    return out

# Simple regex helpers
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
IP_RE  = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}"
                    r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")
