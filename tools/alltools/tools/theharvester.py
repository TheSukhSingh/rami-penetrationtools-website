# tools/alltools/tools/theharvester.py
from __future__ import annotations
from pathlib import Path
from typing import List
import json
import glob

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets, DOMAIN_RE,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

HARD_TIMEOUT = 3600

def _collect_domains_from_json(fp: Path) -> List[str]:
    doms: List[str] = []
    try:
        data = json.loads(fp.read_text("utf-8", errors="ignore"))
    except Exception:
        return doms
    # TheHarvester JSON structure varies by version; collect 'hosts' or 'domains' keys
    stack = [data]
    seen = set()
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k in ("hosts","domains") and isinstance(v, list):
                    for it in v:
                        if isinstance(it, dict):
                            h = it.get("host") or it.get("ip") or it.get("domain")
                            if h:
                                s = str(h).strip().lower()
                                if DOMAIN_RE.match(s) and s not in seen:
                                    seen.add(s); doms.append(s)
                        elif isinstance(it, str):
                            s = it.strip().lower()
                            if DOMAIN_RE.match(s) and s not in seen:
                                seen.add(s); doms.append(s)
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    return doms

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "theharvester")
    slug = options.get("tool_slug", "theharvester")
    policy = options.get("_policy") or get_effective_policy(slug)

    exe = resolve_bin("theHarvester", "theharvester")
    if not exe:
        return finalize("error", "theHarvester not installed", options, "theharvester", t0, "", error_reason="NOT_INSTALLED")

    domains, _ = read_targets(options, accept_keys=("domains",), cap=50)
    if not domains:
        raise ValidationError("Provide root domain(s) for theHarvester.", "INVALID_PARAMS", "no input")

    out_all = []
    found: List[str] = []
    used_cmd = ""

    for d in domains:
        # -b all; -f basename (theharvester creates basename.json & .html)
        base = Path(work_dir) / f"harvest_{abs(hash(d))}"
        args = [exe, "-d", d, "-b", "all", "-f", str(base)]
        used_cmd = " ".join(args[:3] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work_dir)
        out_all.append(out or "")
        # look for the JSON it wrote
        for jf in glob.glob(str(base) + "*.json"):
            found.extend(_collect_domains_from_json(Path(jf)))

    raw = "\n".join(out_all)
    outfile = write_output_file(work_dir, "theharvester_output.txt", raw or "")

    # de-dup
    seen = set(); found = [x for x in found if not (x in seen or seen.add(x))]

    status = "ok"
    msg = f"{len(found)} subdomains"
    return finalize(status, msg, options, used_cmd or "theharvester", t0, raw, output_file=outfile,
                    domains=found)
