# tools/alltools/tools/hydra.py
from __future__ import annotations
from pathlib import Path
from typing import List
import re

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets, PORT_RE,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints


HARD_TIMEOUT = 7200
RE_LOGIN = re.compile(r"(?i)login:\s*([^\s]+)\s+password:\s*([^\s]+)")

def _parse_hydra(text: str) -> List[str]:
    creds: List[str] = []
    for ln in (text or "").splitlines():
        m = RE_LOGIN.search(ln or "")
        if m:
            u, p = m.group(1), m.group(2)
            creds.append(f"{u}:{p}")
    # dedupe
    seen = set()
    return [x for x in creds if not (x in seen or seen.add(x))]

def run_scan(options: dict) -> dict:
    from ._common import resolve_wordlist_path
    passw = (options.get("passlist") or options.get("P") or options.get("passwords") or "").strip()
    if not passw:
        wl_tier = (options.get("wordlist_tier")
                or (policy.get("runtime_constraints",{}).get("_hints",{}) or {}).get("wordlist_default")
                or "small")
        passw = resolve_wordlist_path(wl_tier)
    # later include: (["-P", passw] if passw else [])

    t0 = now_ms()
    work_dir = ensure_work_dir(options, "hydra")
    slug = options.get("tool_slug", "hydra")
    policy = options.get("_policy") or get_effective_policy(slug)

    exe = resolve_bin("hydra")
    if not exe:
        return finalize("error", "hydra not installed", options, "hydra", t0, "", error_reason="NOT_INSTALLED")

    # targets: services (host:port) or urls
    services, _ = read_targets(options, accept_keys=("services",), cap=5000)
    urls, _     = read_targets(options, accept_keys=("urls",),     cap=5000)
    targets = services or urls
    if not targets:
        raise ValidationError("Provide services (host:port) or URLs for hydra.", "INVALID_PARAMS", "no input")

    service = options.get("service")  # e.g., ssh, ftp, http-get, http-post-form, etc.
    if not service:
        raise ValidationError("hydra requires 'service' (e.g., ssh, ftp, http-get-form).", "INVALID_PARAMS", "no service")

    user = options.get("username")
    pass_ = options.get("password")
    users = options.get("userlist")
    passw = options.get("passlist")
    if not ((user or users) and (pass_ or passw)):
        raise ValidationError("Provide username or userlist AND password or passlist.", "INVALID_PARAMS", "missing creds")

    args_base = [exe, "-t", str(options.get("threads") or 4), "-e", "nsr"]  # try null/username/reverse if applicable
    results: List[str] = []
    all_raw = []
    used_cmd = ""

    for t in targets:
        # hydra target form: protocol://host[:port]/path for http modules; host port service for generic
        tgt = t
        if ":" in t and not t.startswith("http"):
            # host:port
            host, port = t.split(":", 1)
            tgt_args = [host, port, service]
            args = args_base + (["-l", user] if user else []) + (["-L", users] if users else []) \
                             + (["-p", pass_] if pass_ else []) + (["-P", passw] if passw else []) \
                             + tgt_args
        else:
            # URL form
            args = args_base + (["-l", user] if user else []) + (["-L", users] if users else []) \
                             + (["-p", pass_] if pass_ else []) + (["-P", passw] if passw else []) \
                             + ["-s", str(options.get("port") or ""), service, tgt]

        used_cmd = " ".join(args[:4] + ["..."])
        rc, out, _ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work_dir)
        all_raw.append(out or "")
        results.extend(_parse_hydra(out or ""))

    raw = "\n".join(all_raw)
    outfile = write_output_file(work_dir, "hydra_output.txt", raw or "")

    status = "ok"
    msg = f"{len(results)} credential(s)"
    return finalize(status, msg, options, used_cmd or "hydra", t0, raw, output_file=outfile,
                    exploit_results=results)
