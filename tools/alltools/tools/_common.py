# tools/alltools/tools/_common.py
from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional, Tuple

# ---------- Clock ----------
def now_ms() -> int:
    try:
        return int(time.time() * 1000)
    except Exception:
        return 0

# ---------- Regex validators ----------
URL_RE    = re.compile(r'(?i)^(?:https?://)[^\s]+$')
DOMAIN_RE = re.compile(r'^(?=.{1,253}$)(?!-)(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\.?$')
IPV4_RE   = re.compile(r'^(?:\d{1,3}\.){3}\d{1,3}$')
# loose IPv6 matcher (good enough for dnsx output)
IPV6_RE   = re.compile(r'(?i)^[0-9a-f:]+$')
PORT_RE   = re.compile(r'^(.+?):(\d{1,5})$')

# Canonical buckets
BUCKET_KEYS = (
    "domains","hosts","ips","ports","services",
    "urls","endpoints","params",
    "tech_stack","vulns","exploit_results","screenshots"
)

# ---------- Errors ----------
class ValidationError(Exception):
    def __init__(self, message: str, reason: str = "INVALID_PARAMS", detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.detail = detail

# ---------- FS helpers ----------
def ensure_work_dir(options: dict, slug: Optional[str] = None) -> Path:
    """
    Use options.get('work_dir') when present; else create a temp dir.
    If run_id/step_id provided, namespace under /tmp/tools/<run>/<step>/.
    """
    wd = options.get("work_dir")
    if wd:
        p = Path(wd)
        p.mkdir(parents=True, exist_ok=True)
        return p

    run_id  = str(options.get("run_id") or "adhoc")
    step_id = str(options.get("step_id") or slug or "step")
    root = Path(tempfile.gettempdir()) / "tools" / run_id / step_id
    root.mkdir(parents=True, exist_ok=True)
    return root

def write_output_file(work_dir: Path, filename: str, content: str) -> str:
    fp = Path(work_dir) / filename
    fp.write_text(content or "", encoding="utf-8", errors="ignore")
    return str(fp)

# ---------- Binary resolution ----------
def resolve_bin(*names: str) -> Optional[str]:
    """
    Return first found executable name in PATH. Accepts multiple names (unix/win).
    """
    for n in names:
        if not n:
            continue
        path = shutil.which(n)
        if path:
            return path
    return None

# ---------- Input helpers ----------
def _coerce_lines(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [s.strip() for s in val.replace("\r\n", "\n").split("\n") if s.strip()]
    return []

def read_targets(options: dict, *, accept_keys: Iterable[str], cap: int = 100) -> Tuple[List[str], List[str]]:
    """
    Read potential targets from multiple common shapes in options. Returns (raw, extras_dropped).
    """
    accept = tuple(accept_keys or ())
    raw: List[str] = []
    # direct buckets
    for k in accept:
        v = options.get(k)
        raw.extend(_coerce_lines(v))
    # common fields used by your UI
    raw.extend(_coerce_lines(options.get("targets")))
    raw.extend(_coerce_lines(options.get("value")))
    raw.extend(_coerce_lines(options.get("input_text")))
    # file handle
    if "targets_file" in options and options["targets_file"]:
        try:
            txt = Path(str(options["targets_file"])).read_text("utf-8", errors="ignore")
            raw.extend(_coerce_lines(txt))
        except Exception:
            pass

    # dedupe, preserve order
    seen = set()
    uniq: List[str] = []
    for s in raw:
        if s not in seen:
            seen.add(s); uniq.append(s)
    extras = []
    if cap and len(uniq) > cap:
        extras = uniq[cap:]
        uniq = uniq[:cap]
    return uniq, extras

# ---------- Simple classifiers ----------
def classify_domains(items: Iterable[str]) -> Tuple[List[str], List[str]]:
    good, bad = [], []
    for s in items or []:
        s = (s or "").strip().lower()
        if not s:
            continue
        (good if DOMAIN_RE.match(s) else bad).append(s)
    return good, bad

# ---------- Shell ----------
def run_cmd(args: List[str], *, timeout_s: int, cwd: Path) -> Tuple[int, str, int]:
    t0 = now_ms()
    try:
        res = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout_s)
        out = (res.stdout or "")
        if res.stderr:
            out = out + ("\n" + res.stderr)
        return res.returncode, out, now_ms() - t0
    except subprocess.TimeoutExpired as e:
        raise ValidationError("Timed out while running the tool", "TIMEOUT", str(e))

# ---------- Merge / finalize ----------
def _merge_dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        # normalize domains/urls/endpoints to lowercase
        key = s.lower() if (s.startswith("http") or DOMAIN_RE.match(s)) else s
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out

def finalize(status: str,
             message: str,
             options: dict,
             command: str,
             t0_ms: int,
             raw_out: str,
             output_file: Optional[str] = None,
             error_reason: Optional[str] = None,
             error_detail: Optional[str] = None,
             **buckets) -> dict:
    """
    Standard tool manifest for your runner.
    Buckets should be lists using keys from BUCKET_KEYS.
    """
    out: Dict[str, Any] = {
        "status": status,
        "message": message,
        "options": {k:v for k,v in (options or {}).items() if k not in ("_policy","_meta")},
        "command": command,
        "started_at": t0_ms,
        "duration_ms": max(0, now_ms() - t0_ms),
        "stdout": raw_out or "",
    }
    if output_file:
        out["output_file"] = output_file
    if error_reason:
        out["error_reason"] = error_reason
    if error_detail:
        out["error_detail"] = error_detail

    counts: Dict[str,int] = {}
    for k in BUCKET_KEYS:
        vals = buckets.get(k)
        if vals:
            uniq = _merge_dedupe(vals)
            out[k] = uniq
            counts[k] = len(uniq)
    if counts:
        out["counts"] = counts
    return out
