# tools/alltools/tools/_common.py
from __future__ import annotations
import os, sys, shutil, time, re, subprocess
from pathlib import Path
from typing import List, Tuple, Iterable, Dict, Any, Optional

import redis
_redis_client = None

def ops_redis():
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
        _redis_client = redis.Redis.from_url(url, decode_responses=True)
    return _redis_client

RUNS_MAX_ACTIVE_PER_USER = int(os.environ.get("RUNS_MAX_ACTIVE_PER_USER", "1"))
RUN_START_DEDUP_TTL      = int(os.environ.get("RUN_START_DEDUP_TTL", "10"))  # seconds

def dedupe_run_key(user_id, workflow_id):
    return f"tools:dedupe:run:{user_id}:{workflow_id}"

def active_runs_key(user_id):
    return f"tools:active_runs:{user_id}"

def active_can_start(user_id: str | int) -> bool:
    r = ops_redis()
    cur = int(r.get(active_runs_key(user_id)) or 0)
    return cur < RUNS_MAX_ACTIVE_PER_USER

def active_incr(user_id: str | int, ttl_seconds: int = 6*3600):
    r = ops_redis()
    k = active_runs_key(user_id)
    pipe = r.pipeline()
    pipe.incr(k)
    pipe.expire(k, ttl_seconds)
    pipe.execute()

def active_decr(user_id: str | int):
    r = ops_redis()
    k = active_runs_key(user_id)
    try:
        if int(r.decr(k)) <= 0:
            r.delete(k)
    except Exception:
        pass
# ---- What buckets every adapter may emit (typed chaining relies on these) ----
BUCKET_KEYS = (
    "domains", "hosts", "ips", "ports", "services",
    "urls", "endpoints", "params",
    "tech_stack", "vulns", "exploit_results",
    "screenshots"
    # keep "findings" if you want as a generic catch-all, but it's cleaner to prefer typed keys
)
WORDLIST_DIR = os.environ.get("WORDLIST_DIR", os.path.join(os.getcwd(), "wordlists"))

def resolve_wordlist_path(tier: str) -> str:
    """
    Map tier -> on-disk list. Caller should verify existence and fall back to default.
    """
    mapping = {
        "small":  os.path.join(WORDLIST_DIR, "small.txt"),
        "medium": os.path.join(WORDLIST_DIR, "medium.txt"),
        "large":  os.path.join(WORDLIST_DIR, "large.txt"),
        "ultra":  os.path.join(WORDLIST_DIR, "ultra.txt"),
    }
    path = mapping.get((tier or "medium").lower(), mapping["medium"])
    return path

# ---- Regex helpers ----
URL_RE  = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b")
IPV6_RE = re.compile(r"\b(?:[A-F0-9]{1,4}:){1,7}[A-F0-9]{1,4}\b", re.IGNORECASE)
try:
    # Prefer a shared definition if present
    from tools.alltools._manifest_utils import PORT_RE as _PORT_RE
    PORT_RE = _PORT_RE
except Exception:
    # Fallback: host:port or host:port/proto
    PORT_RE = re.compile(r"^([A-Za-z0-9\.\-]+):(\d+)(?:/[A-Za-z0-9\-\+]+)?$")

# Common HTTP(S) ports for URL guessing
HTTP_PORTS  = {80, 8080, 8000, 8008, 3000, 8888}
HTTPS_PORTS = {443, 8443, 9443, 444}
# Optional domain classifier: use your existing helper if available
try:
    # adjust path if your module lives elsewhere
    from tools.utils.domain_classification import classify_lines as classify_domains
except Exception:
    def classify_domains(lines: List[str]) -> Tuple[List[str], List[str], int]:
        """Fallback: very simple 'looks like a domain' filter; returns (valid, invalid, dup_count)."""
        seen, dups, valid, invalid = set(), 0, [], []
        dom_re = re.compile(r"^(?=.{1,253}$)(?!-)([a-z0-9-]{1,63}\.)+[a-z]{2,63}$", re.IGNORECASE)
        for s in lines:
            if s in seen: dups += 1; continue
            seen.add(s)
            (valid if dom_re.match(s) else invalid).append(s)
        return valid, invalid, dups

def services_to_urls(services: Iterable[str]) -> List[str]:
    """
    Accepts items like 'host:port' or 'host:port/proto'.
    Guesses scheme from common ports and omits default port in URL.
    """
    out: List[str] = []
    seen = set()
    for s in services or []:
        s = str(s).strip()
        if not s:
            continue
        m = PORT_RE.match(s)
        if not m:
            continue
        host, port = m.group(1), int(m.group(2))
        url = None
        if port in HTTPS_PORTS:
            url = f"https://{host}" if port == 443 else f"https://{host}:{port}"
        elif port in HTTP_PORTS:
            url = f"http://{host}" if port == 80 else f"http://{host}:{port}"
        if url and url not in seen:
            seen.add(url); out.append(url)
    return out


# ---- Small error class for parameter issues ----
class ValidationError(Exception):
    def __init__(self, message: str, reason: str = "INVALID_PARAMS", detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.reason = reason
        self.detail = detail

# ---- Common utilities ----
def resolve_bin(*names: str) -> Optional[str]:
    """Return first resolvable binary from names; try .exe on Windows too."""
    for name in names:
        p = shutil.which(name)
        if p: return p
        if sys.platform.startswith("win") and not name.lower().endswith(".exe"):
            p = shutil.which(name + ".exe")
            if p: return p
    return None

def now_ms() -> int:
    return int(time.time() * 1000)

from typing import Optional
def ensure_work_dir(options: dict, subdir: Optional[str] = None) -> Path:
    base = Path(options.get("work_dir") or Path(os.getenv("TEMP", "/tmp")) / "hackr_runs")
    wd = (base / subdir) if subdir else base
    wd = wd.resolve()
    wd.mkdir(parents=True, exist_ok=True)
    return wd

def write_output_file(work_dir: Path, name: str, content: str) -> str:
    out_path = work_dir / name
    out_path.write_text(content, encoding="utf-8", errors="ignore")
    return str(out_path)

def merge_dedupe(items: Iterable[str], max_items: Optional[int] = None) -> List[str]:
    seen, out = set(), []
    for it in items or []:
        it = str(it).strip()
        if not it: continue
        if it in seen: continue
        seen.add(it); out.append(it)
        if max_items and len(out) >= max_items:
            break
    return out

def ensure_file_limits(path: str, max_bytes: int) -> None:
    if not path or not os.path.exists(path):
        raise ValidationError("Upload file not found.", "INVALID_PARAMS", "Missing or inaccessible file")
    try:
        size = os.path.getsize(path)
    except Exception:
        raise ValidationError("Unable to read uploaded file.", "INVALID_PARAMS", "stat() failed")
    if size > max_bytes:
        raise ValidationError(f"Uploaded file too large ({size} bytes)", "FILE_TOO_LARGE", f"{size} > {max_bytes}")

def coerce_int_range(options: dict, key: str, default: int, min_v: int, max_v: int) -> int:
    raw = options.get(key, default)
    try:
        val = int(raw)
    except Exception:
        raise ValidationError(f"{key} must be an integer", "INVALID_PARAMS", f"got {raw!r}")
    if not (min_v <= val <= max_v):
        raise ValidationError(f"{key} must be between {min_v}-{max_v}", "INVALID_PARAMS", f"got {val}")
    return val

def read_injected(options: dict, accept_keys: Iterable[str]) -> List[str]:
    buf: List[str] = []
    for key in accept_keys:
        v = options.get(key)
        if isinstance(v, list) and v:
            buf.extend(str(x).strip() for x in v if str(x).strip())
    return merge_dedupe(buf)

def read_targets(options: dict,
                 accept_keys: Iterable[str],
                 file_max_bytes: int = 200_000,
                 manual_split_re: str = r"[\s,]+",
                 cap: Optional[int] = None) -> Tuple[List[str], str]:
    """
    Prefer injected typed lists; else file (validated); else manual 'value'.
    Returns (targets, source) where source is 'injected' | 'file:<path>' | 'value' | 'empty'
    """
    # 1) injected lists from previous steps
    inj = read_injected(options, accept_keys)
    if inj:
        return (merge_dedupe(inj, cap), "injected")
    # 2) file method
    im = (options or {}).get("input_method", "").lower()
    if im == "file" and options.get("file_path"):
        ensure_file_limits(options["file_path"], file_max_bytes)
        with open(options["file_path"], "r", encoding="utf-8", errors="ignore") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        return (merge_dedupe(lines, cap), f"file:{options['file_path']}")
    # 3) manual value
    val = (options or {}).get("value", "")
    if isinstance(val, str) and val.strip():
        parts = re.split(manual_split_re, val.strip())
        return (merge_dedupe(parts, cap), "value")
    return ([], "empty")

def run_cmd(args: List[str], timeout_s: int, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, int]:
    if not args or not args[0]:
        raise ValidationError("Executable not resolved", "NOT_INSTALLED", "args[0] missing")
    t0 = now_ms()
    try:
        res = subprocess.run(
            args, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout_s, cwd=str(cwd) if cwd else None, env=env
        )
        return res.returncode, (res.stdout or ""), now_ms() - t0
    except subprocess.TimeoutExpired as e:
        raise ValidationError("Timed out while running the tool", "TIMEOUT", str(e))

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
    Standardize manifest shape. Buckets are lists keyed by BUCKET_KEYS.
    Adds counts{} and optional error_reason/error_detail.
    """
    out: Dict[str, Any] = {
        "status": status,
        "message": message,
        "parameters": {k: options.get(k) for k in sorted(options.keys())},
        "command": command,
        "execution_ms": max(0, now_ms() - t0_ms),
        "output": raw_out or "",
    }
    if output_file:
        out["output_file"] = output_file
    if error_reason:
        out["error_reason"] = error_reason
    if error_detail:
        out["error_detail"] = error_detail

    counts: Dict[str, int] = {}
    for k in BUCKET_KEYS:
        v = buckets.get(k)
        if v:
            uniq = merge_dedupe(v)
            out[k] = uniq
            counts[k] = len(uniq)
    if counts:
        out["counts"] = counts
    return out


IP_RE = re.compile(rf"(?:{IPV4_RE.pattern})|(?:{IPV6_RE.pattern})")

def read_targets_from_options(options: dict, *, cap: Optional[int] = None):
    # default acceptable keys; adapters can still call read_targets(...) directly if they need custom sets
    return read_targets(options, accept_keys=("domains","hosts","urls"), cap=cap)
# in _common.py
def read_domains_validated(options: dict, *, cap:int=50, file_max_bytes:int=100_000):
    """
    Returns (domains, diag) or raises ValidationError with error_reason set.
    diag includes the same counters old adapters used to return.
    """
    targets, src = read_targets(options, accept_keys=("domains","hosts"), file_max_bytes=file_max_bytes, cap=None)

    # old behavior: require something
    if not targets:
        raise ValidationError("At least one domain is required.", "INVALID_PARAMS", "No domains submitted")

    # classify + dedupe
    try:
        from tools.utils.domain_classification import classify_lines
        valid, invalid, dup_count = classify_lines(targets)
    except Exception:
        # fallback: accept everything & no dup count
        valid, invalid, dup_count = (list(dict.fromkeys(targets)), [], 0)

    if invalid:
        raise ValidationError(f"{len(invalid)} invalid domains found", "INVALID_PARAMS", ", ".join(invalid[:10]))
    if len(valid) > cap:
        raise ValidationError(f"Too many domains: {len(valid)} (max {cap})", "TOO_MANY_DOMAINS", f"{len(valid)} > {cap} limit")

    diag = {
        "total_domain_count": len(targets),
        "valid_domain_count": len(valid),
        "invalid_domain_count": len(invalid),
        "duplicate_domain_count": dup_count,
        "file_size_b": (os.path.getsize(options["file_path"]) if (options.get("input_method")=="file" and options.get("file_path") and os.path.exists(options["file_path"])) else None),
    }
    return (valid, diag)
