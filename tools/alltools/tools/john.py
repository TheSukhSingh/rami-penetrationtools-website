# tools/alltools/tools/john.py
from __future__ import annotations
from pathlib import Path
from typing import List

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import *

HARD_TIMEOUT = 7200

def run_scan(options: dict) -> dict:
    from ._common import resolve_wordlist_path
    wordlist = (options.get("wordlist") or "").strip()
    if not wordlist:
        wl_tier = options.get("wordlist_tier") or "large"
        wordlist = resolve_wordlist_path(wl_tier)
    if wordlist:
        args += ["--wordlist=" + str(wordlist)]

    t0 = now_ms()
    work_dir = ensure_work_dir(options, "john")
    slug = options.get("tool_slug", "john")

    exe = resolve_bin("john")
    if not exe:
        return finalize("error", "john not installed", options, "john", t0, "", error_reason="NOT_INSTALLED")

    # Expect a prepared hashes file; optionally a wordlist
    hashes_file = options.get("hashes_file")
    if not hashes_file or not Path(hashes_file).exists():
        raise ValidationError("Provide 'hashes_file' path for john.", "INVALID_PARAMS", "missing hashes_file")

    wordlist = options.get("wordlist")  # optional

    args = [exe, str(hashes_file)]
    if wordlist:
        args += ["--wordlist=" + str(wordlist)]
    used_cmd = " ".join(args[:2] + ["..."])

    rc, out, _ms = run_cmd(args, timeout_s=HARD_TIMEOUT, cwd=work_dir)
    # Show cracked passwords
    show_args = [exe, "--show", str(hashes_file)]
    rc2, out2, _ms2 = run_cmd(show_args, timeout_s=600, cwd=work_dir)

    raw = (out or "") + "\n" + (out2 or "")
    outfile = write_output_file(work_dir, "john_output.txt", raw or "")

    results: List[str] = []
    for ln in (out2 or "").splitlines():
        s = (ln or "").strip()
        # john --show outputs lines like: user:password:...
        if ":" in s and not s.startswith("Loaded "):
            user, pwd = s.split(":", 1)[0], s.split(":", 2)[1].split(":",1)[0]
            results.append(f"{user}:{pwd}")

    # de-dup
    seen = set()
    results = [x for x in results if not (x in seen or seen.add(x))]

    status = "ok"
    msg = f"{len(results)} credential(s)"
    return finalize(status, msg, options, used_cmd or "john", t0, raw, output_file=outfile,
                    exploit_results=results)
