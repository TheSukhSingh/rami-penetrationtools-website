from __future__ import annotations
from pathlib import Path
from typing import List
import os
import glob

try:
    from ._common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )
except ImportError:
    from _common import (
        resolve_bin, ensure_work_dir, read_targets,
        run_cmd, write_output_file, finalize, ValidationError, now_ms
    )

try:
    from tools.policies import get_effective_policy, clamp_from_constraints
except ImportError:
    from policies import get_effective_policy, clamp_from_constraints

HARD_TIMEOUT = 900

def _list_pngs(root: Path) -> List[str]:
    pngs = []
    for p in root.rglob("*.png"):
        try:
            pngs.append(str(p))
        except Exception:
            continue
    return pngs

def run_scan(options: dict) -> dict:
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "gowitness")
    slug = options.get("tool_slug", "gowitness")
    policy = options.get("_policy") or get_effective_policy(slug)
    ipol = policy.get("input_policy", {}) or {}

    exe = resolve_bin("gowitness")
    if not exe:
        return finalize("error", "gowitness not installed", options, "gowitness", t0, "", error_reason="NOT_INSTALLED")

    urls, _ = read_targets(options, accept_keys=("urls",), cap=ipol.get("max_targets") or 10000)
    if not urls:
        raise ValidationError("Provide URLs to screenshot.", "INVALID_PARAMS", "no input")

    timeout_s = clamp_from_constraints(options, "timeout_s", policy.get("runtime_constraints", {}).get("timeout_s"), default=30, kind="int") or 30

    # write list
    fp = Path(work_dir) / "urls.txt"
    fp.write_text("\n".join(urls), encoding="utf-8")
    outdir = Path(work_dir) / "screens"
    outdir.mkdir(parents=True, exist_ok=True)

    # try a few flag variants to be robust across versions
    variants = [
        [exe, "file", "-f", str(fp), "--disable-db", "--screenshot-path", str(outdir)],
        [exe, "file", "-f", str(fp), "--disable-db", "--destination", str(outdir)],
        [exe, "file", "-f", str(fp), "--disable-db"],
    ]
    last_args = variants[-1]
    for args in variants:
        last_args = args
        rc, out, _ms = run_cmd(args, timeout_s=min(HARD_TIMEOUT, timeout_s + 180), cwd=work_dir)
        # check if any pngs exist; if yes, stop trying
        if _list_pngs(outdir) or _list_pngs(work_dir):
            raw = out or ""
            break
    else:
        raw = out if 'out' in locals() else ""

    # collect screenshots under outdir or work_dir
    pngs = _list_pngs(outdir) or _list_pngs(work_dir)
    txt = "\n".join(pngs)
    outfile = write_output_file(work_dir, "gowitness_files.txt", txt)

    status = "ok"
    msg = f"{len(pngs)} screenshots"
    return finalize(status, msg, options, " ".join(last_args), t0, raw, output_file=outfile,
                    screenshots=pngs)
