from importlib import import_module
import os
import tempfile
from celery.utils.log import get_task_logger
from celery_app import celery
from extensions import db
from tools.policies import get_effective_policy
from .models import (
    ErrorReason, ScanDiagnostics, ScanStatus, Tool, WorkflowRun, WorkflowRunStatus,
    WorkflowRunStep, WorkflowStepStatus,
    ToolScanHistory,  # existing audit trail for each tool exec
)
from pathlib import Path
from datetime import datetime, timedelta, timezone
from .runner import create_run_from_definition, preflight_validate_workflow
from flask import current_app
from .events import publish_run_event
from tools import ingest
from tools.alltools.tools._common import active_decr, active_incr, active_can_start, ops_redis
import shutil

utcnow = lambda: datetime.now(timezone.utc)
log = get_task_logger(__name__)

# --- Global normalization for buckets (lightweight) -------------
def _norm_domain(s): 
    s = (s or "").strip().lower()
    if s.startswith("*."): s = s[2:]
    return s.strip(".")
def _norm_url(u): return (u or "").strip()
def _norm_endpoint(p):
    p = (p or "").strip()
    return p if p.startswith("/") else ("/" + p) if p else p
def _norm_param(p): return (p or "").strip()
def _norm_ip(ip):   return (ip or "").strip()
def _norm_service(s): return (s or "").strip().lower()
def _norm_text(t):  return (t or "").strip()

NORMALIZERS = {
    "domains": _norm_domain,
    "urls": _norm_url,
    "endpoints": _norm_endpoint,
    "params": _norm_param,
    "ips": _norm_ip,
    "services": _norm_service,
    "tech_stack": _norm_text,
    "vulns": _norm_text,
    "exploit_results": _norm_text,
    "screenshots": _norm_text,
    "ports": _norm_text,
    "hosts": _norm_text,
}

def _can_run_step_by_inputs(run, step) -> tuple[bool, str]:
    """Stage gate: if ALL required buckets empty, skip."""
    cfg = (step.input_manifest or {}).get("options") or {}
    consumes = cfg.get("io_bucket_consumes") or []
    if not consumes:
        return True, "no inputs required"
    manifest = run.run_manifest or {}
    buckets = manifest.get("buckets") or {}
    for b in consumes:
        bstate = buckets.get(b) or {}
        if (bstate.get("count") or 0) > 0:
            return True, f"has {b}"
    return False, f"missing inputs: {consumes}"

def _merge_outputs_into_manifest(run, step, result: dict):
    """Normalize + dedupe outputs into run.run_manifest and record provenance."""
    manifest = run.run_manifest or {
        "buckets": {}, "provenance": {}, "steps": {}, "last_updated": None
    }
    buckets = manifest.setdefault("buckets", {})
    prov    = manifest.setdefault("provenance", {})
    step_slug = (step.input_manifest or {}).get("options", {}).get("tool_slug") or "unknown"

    for bucket, normalizer in NORMALIZERS.items():
        vals = result.get(bucket)
        if not vals: 
            continue
        b = buckets.setdefault(bucket, {"count": 0, "items": []})
        existing = b["items"]
        seen = set(existing)
        pv = prov.setdefault(bucket, {})
        per_tool = pv.setdefault(step_slug, [])

        for v in vals:
            nv = normalizer(v)
            if not nv or nv in seen:
                continue
            seen.add(nv)
            existing.append(nv)
            per_tool.append(nv)

        b["count"] = len(existing)

    manifest["last_updated"] = datetime.utcnow().isoformat()
    run.run_manifest = manifest

@celery.task(name='tools.tasks.ping')
def ping(msg='ok'):
    log.info(f'[ping] {msg}')
    return {'pong': msg}

@celery.task(name='tools.tasks.advance_run', bind=True)
def advance_run(self, run_id: int):
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        log.warning(f'advance_run: run {run_id} not found')
        return {'status': 'not_found'}

    # Respect paused/canceled immediately
    if run.status == WorkflowRunStatus.CANCELED:
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })
        return {'status': 'canceled'}

    if run.status == WorkflowRunStatus.PAUSED:
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })
        return {'status': 'paused'}

    if run.status == WorkflowRunStatus.QUEUED:
        # validate stage ordering of current steps
        if not preflight_validate_workflow(run, list(run.steps)):
            run.status = WorkflowRunStatus.FAILED
            run.finished_at = utcnow()
            db.session.commit()
            publish_run_event(run.id, "run", {
                "status": run.status.name,
                "progress_pct": run.progress_pct,
                "current_step_index": run.current_step_index,
                "note": getattr(run, "status_note", None),
            })
            return {'status': 'preflight_failed', 'note': run.status_note}

        run.status = WorkflowRunStatus.RUNNING
        run.started_at = run.started_at or utcnow()
        db.session.commit()
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })

    # Helper to recompute progress (count COMPLETED + SKIPPED as "done")
    def _recompute_progress():
        done = sum(1 for s in run.steps if s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED))
        total = max(1, run.total_steps or len(run.steps))
        run.progress_pct = round(100.0 * done / total, 2)

    # Find next queued step and apply stage gating.
    # If a step has no required inputs (per IO policy), mark SKIPPED and move on.
    advanced_any = False
    while True:
        steps = list(run.steps)  # ordered
        next_step = next((s for s in steps if s.status == WorkflowStepStatus.QUEUED), None)

        if not next_step:
            # No more queued steps -> complete the run
            run.status = WorkflowRunStatus.COMPLETED
            run.finished_at = utcnow()
            run.progress_pct = 100.0
            db.session.commit()
            publish_run_event(run.id, "run", {
                "status": run.status.name, "progress_pct": run.progress_pct,
                "current_step_index": run.current_step_index
            })
            log.info(f'advance_run: run {run_id} completed')
            try:
                active_decr(run.user_id)
            except Exception:
                pass
            try:
                _promote_queued()
            except Exception:
                pass
            return {'status': 'completed'}

        # ---- Stage gate (requires helper _can_run_step_by_inputs) ----
        ok, why = _can_run_step_by_inputs(run, next_step)
        if ok:
            # Dispatch this step to Celery worker
            publish_run_event(run.id, "dispatch", {"step_index": next_step.step_index})
            queue_name = current_app.config.get("CELERY_QUEUE", "tools_default")
            res = run_step.apply_async(args=[run_id, next_step.step_index], queue=queue_name)
            # record Celery task id for cancel/revoke
            next_step.celery_task_id = res.id
            # Set current step index for UI
            run.current_step_index = next_step.step_index
            db.session.commit()
            return {'status': 'dispatched', 'task_id': res.id}

        # Gate says "skip": mark step SKIPPED and loop to the next one
        next_step.status = WorkflowStepStatus.SKIPPED
        next_step.started_at = utcnow()
        next_step.finished_at = utcnow()
        # Keep a small note for debugging/UX
        next_step.output_manifest = {"status": "skipped", "message": why}
        advanced_any = True

        # Advance the pointer and progress
        run.current_step_index = next_step.step_index + 1
        _recompute_progress()
        db.session.commit()

        # Notify FE about this step & run status
        publish_run_event(run.id, "step", {
            "index": next_step.step_index,
            "status": "SKIPPED",
            "message": why
        })
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })
        # continue the while-loop to evaluate the next queued step

BUCKET_KEYS = (
    "domains", "hosts", "ips", "ports", "services",
    "urls", "endpoints", "params",
    "tech_stack", "vulns", "exploit_results",
    "screenshots"
)

def _ensure_run_manifest(run):
    """
    Ensure a consistent dict structure on run.run_manifest.
    """
    base = {
        "buckets": {k: {"count": 0, "items": []} for k in BUCKET_KEYS},
        "provenance": {k: {} for k in BUCKET_KEYS},   # item -> [ {step, tool} ]
        "steps": {},                                   # step_index -> summary
        "last_updated": None,
    }
    return run.run_manifest or base

def _merge_items(dst_list, new_items):
    out = list(dst_list) if dst_list else []
    seen = set(out)
    for v in (new_items or []):
        v = (v or "").strip()
        if not v or v in seen:
            continue
        out.append(v)
        seen.add(v)
    return out

def _aggregate_run_manifest(db, run, step_index, tool_slug, step_manifest):
    """
    Merge a step's typed buckets (domains/hosts/ips/ports/urls/endpoints/findings)
    into the run-level summary with provenance.
    """
    manifest = _ensure_run_manifest(run)
    step_counts = {}

    for key in BUCKET_KEYS:
        vals = step_manifest.get(key)
        if not vals:
            # also accept *_count, but don't need to recalc
            continue
        
        # Merge items
        bucket = manifest["buckets"].get(key, {"count": 0, "items": []})
        merged = _merge_items(bucket.get("items", []), vals)
        bucket["items"] = merged
        bucket["count"] = len(merged)
        manifest["buckets"][key] = bucket
        step_counts[key] = len(vals)

        # Provenance: item -> [{step, tool}]
        prov_map = manifest["provenance"].setdefault(key, {})
        for v in vals:
            arr = prov_map.get(v, [])
            arr.append({"step": int(step_index), "tool": tool_slug})
            prov_map[v] = arr

    # Record per-step summary
    manifest["steps"][str(step_index)] = {
        "tool": tool_slug,
        "counts": step_counts,
        "execution_ms": step_manifest.get("execution_ms"),
        "status": step_manifest.get("status", "success"),
    }
    manifest["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Persist on the run row
    run.run_manifest = manifest
    db.session.add(run)
    db.session.commit()
    return manifest

def _stage_artifact(run_id: int, step_index: int, slug: str, source_path: str) -> str | None:
    """
    Copy the adapter's output_file into ARTIFACTS_DIR/<run_id>/step-XX-<slug>/,
    return the relpath (relative to ARTIFACTS_DIR/<run_id>) suitable for download endpoint.
    """
    if not source_path or not os.path.isfile(source_path):
        return None
    base_dir = current_app.config.get("ARTIFACTS_DIR", os.path.join("instance", "tools_artifacts"))
    dest_dir = os.path.join(base_dir, str(run_id), f"step-{step_index:02d}-{slug}")
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(source_path)
    dest = os.path.join(dest_dir, name)
    try:
        if os.path.abspath(source_path) != os.path.abspath(dest):
            shutil.copy2(source_path, dest)
    except Exception:
        # don't fail the run on copy issues
        return None
    rel = os.path.relpath(dest, os.path.join(base_dir, str(run_id))).replace("\\", "/")
    return rel

@celery.task(name='tools.tasks.run_step', bind=True)
def run_step(self, run_id: int, step_index: int):
    from importlib import import_module
    import os, shutil, time
    from flask import current_app

    run = db.session.get(WorkflowRun, run_id)
    if not run:
        log.warning(f'run_step: run {run_id} not found')
        return {'status': 'not_found'}

    step = next((s for s in run.steps if s.step_index == step_index), None)
    if not step:
        log.warning(f'run_step: step {step_index} not found in run {run_id}')
        return {'status': 'step_not_found'}

    # Only run from QUEUED
    if step.status != WorkflowStepStatus.QUEUED:
        return {'status': 'ignored', 'reason': f'step status is {step.status.name}'}

    # Flip status → RUNNING
    step.status = WorkflowStepStatus.RUNNING
    step.started_at = utcnow()
    run.current_step_index = step.step_index
    db.session.commit()
    publish_run_event(run.id, "step", {
        "index": step.step_index,
        "status": "RUNNING",
    })

    # ---------- Compose adapter options ----------
    options = ((step.input_manifest or {}).get("options") or {}).copy()
    tool_slug = options.get("tool_slug")
    tool = db.session.get(Tool, step.tool_id) if step.tool_id else None
    if not tool_slug and tool:
        tool_slug = tool.slug
        options["tool_slug"] = tool_slug

    # Ensure policy snapshot
    policy = options.get("_policy") or get_effective_policy(tool_slug or "")
    options["_policy"] = policy

    # Attach a snapshot of current buckets (typed inputs) from run.run_manifest
    manifest = run.run_manifest or {}
    buckets = manifest.get("buckets") or {}
    ALL_BUCKETS = (
        "domains","hosts","ips","ports","services",
        "urls","endpoints","params",
        "tech_stack","vulns","exploit_results","screenshots"
    )
    for b in ALL_BUCKETS:
        options[b] = (buckets.get(b) or {}).get("items") or []

    # ---------- Call adapter ----------
    mod_name = (tool_slug or "").replace('-', '_').replace('.', '_')
    try:
        adapter = import_module(f"tools.alltools.tools.{mod_name}")
    except Exception as e:
        # Adapter import failure
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = utcnow()
        step.output_manifest = {"status": "error", "message": f"import failed: {e}"}
        db.session.commit()
        publish_run_event(run.id, "step", {"index": step.step_index, "status": "FAILED"})
        # Promote next step
        advance_run.delay(run.id)
        return {'status': 'error', 'message': f'import failed: {e}'}

    start = time.time()
    try:
        result = adapter.run_scan(options) or {}
    except Exception as e:
        result = {"status": "error", "message": "adapter_crash", "error_reason": "ADAPTER_CRASH", "output": str(e)}
    duration_ms = int((time.time() - start) * 1000)

    success = (result.get("status") in ("ok", "success"))
    message = result.get("message") or result.get("output") or ""

    # ---------- Persist ToolScanHistory (+ diagnostics) ----------
    # (Mirrors your /api/scan path so all usage metrics stay consistent.)
    scan = None
    try:
        tool_rec = db.session.query(Tool).filter_by(slug=tool_slug).first() if tool_slug else None
        scan = ToolScanHistory(
            user_id            = run.user_id,
            tool_id            = (tool_rec.id if tool_rec else None),
            parameters         = (options or {}),
            command            = None,
            raw_output         = (result.get('output') or result.get('message') or ''),
            scan_success_state = bool(success),
            filename_by_user   = None,
            filename_by_be     = None,
        )
        db.session.add(scan); db.session.flush()

        er_val  = (result.get('error_reason') or '')
        er_enum = ErrorReason[er_val] if er_val in ErrorReason.__members__ else None

        diag = ScanDiagnostics(
            scan_id                = scan.id,
            status                 = (ScanStatus.SUCCESS if success else ScanStatus.FAILURE),
            total_domain_count     = result.get('total_domain_count'),
            valid_domain_count     = result.get('valid_domain_count'),
            invalid_domain_count   = result.get('invalid_domain_count'),
            duplicate_domain_count = result.get('duplicate_domain_count'),
            file_size_b            = result.get('file_size_b'),
            execution_ms           = duration_ms,
            error_reason           = er_enum,
            error_detail           = result.get('error_detail'),
            value_entered          = result.get('value_entered'),
        )
        db.session.add(diag)
    except Exception as e:
        log.warning(f'run_step: failed to record ToolScanHistory for run {run_id} step {step_index}: {e}')

    # ---------- Save artifact copy (if adapter produced one) ----------
    artifact_rel = None
    try:
        out_file = result.get("output_file")
        if out_file and os.path.isfile(out_file):
            base_dir = current_app.config.get(
                "ARTIFACTS_DIR",
                os.path.join(current_app.instance_path, "tools_artifacts"),
            )
            run_dir = os.path.join(base_dir, str(run.id))
            os.makedirs(run_dir, exist_ok=True)
            fname = os.path.basename(out_file)
            # Prefix with step & tool for clarity
            dest_name = f"{step_index:02d}_{(tool_slug or 'tool')}_{fname}"
            dest = os.path.join(run_dir, dest_name)
            shutil.copy2(out_file, dest)
            artifact_rel = dest_name  # download via /api/runs/<run_id>/artifacts/<relpath>
    except Exception as e:
        log.warning(f'run_step: artifact copy failed for run {run_id} step {step_index}: {e}')

    # ---------- Global merge: normalize + dedupe + provenance ----------
    try:
        _merge_outputs_into_manifest(run, step, result or {})
    except Exception as e:
        # Do not fail the step for merge issues—just note it
        result = {**(result or {}), "merge_warning": str(e)}

    # ---------- Finalize step ----------
    step.output_manifest = {
        "status": result.get("status"),
        "message": message,
        "artifact": artifact_rel,
        "counts": {k: len(result.get(k) or []) for k in (
            "domains","hosts","ips","ports","services","urls","endpoints","params",
            "tech_stack","vulns","exploit_results","screenshots"
        )},
        "raw_tail": (result.get("output") or "")[-5000:],  # small tail for UI
        "error_reason": result.get("error_reason"),
    }
    if scan:
        step.tool_scan_history_id = scan.id

    step.finished_at = utcnow()
    step.status = WorkflowStepStatus.COMPLETED if success else WorkflowStepStatus.FAILED

    # Recompute progress (COMPLETED + SKIPPED are “done”)
    done = sum(1 for s in run.steps if s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED))
    total = max(1, run.total_steps or len(run.steps))
    run.progress_pct = round(100.0 * done / total, 2)

    db.session.commit()

    # ---------- Events ----------
    publish_run_event(run.id, "step", {
        "index": step.step_index,
        "status": step.status.name,
        "artifact": artifact_rel,
        "message": message[:300],
    })
    publish_run_event(run.id, "run", {
        "status": run.status.name,
        "progress_pct": run.progress_pct,
        "current_step_index": run.current_step_index,
    })

    # Kick the coordinator to move to the next queued step (stage gating already handled there)
    advance_run.delay(run.id)

    return {
        "status": step.status.name.lower(),
        "duration_ms": duration_ms,
        "success": bool(success),
        "artifact": artifact_rel,
    }

def _load_adapter_for_slug(slug: str):
    """Slug 'github_subdomains' -> module tools.alltools.github_subdomains"""
    mod_name = slug.replace('-', '_')
    return import_module(f".alltools.tools.{mod_name}", package="tools")

def _prep_options_for_tool(step, prev_output: dict, user_id: int, app_config: dict):
    """
    Build the 'options' dict expected by your adapters' run_scan().
    v1 strategy:
      - Prefer file input if previous step produced an output file path.
      - Else, if previous output includes a list (domains/urls/hosts), write it to a temp file and pass as file input.
      - Else, fall back to any manual 'value' present in the node config saved in step.input_manifest.
    """
    options = {}
    if isinstance(step.input_manifest, dict):
        options.update(step.input_manifest)
        inner = step.input_manifest.get("options")
        if isinstance(inner, dict):
            for k, v in inner.items():
                # keep any explicit top-level value; otherwise copy from inner
                options.setdefault(k, v)
                
    # previous file?
    file_path = None
    for key in ("output_file", "file_path", "list_path"):
        if isinstance(prev_output, dict) and prev_output.get(key):
            file_path = prev_output.get(key); break

    # list fallback
    lines = None
    for key in ("domains", "urls", "hosts"):
        if isinstance(prev_output, dict) and isinstance(prev_output.get(key), list) and prev_output[key]:
            lines = prev_output[key]; break

    upload_base = app_config.get("UPLOAD_INPUT_FOLDER")
    user_folder = os.path.join(upload_base, str(user_id)) if upload_base else None
    if user_folder:
        os.makedirs(user_folder, exist_ok=True)

    if file_path and os.path.exists(file_path):
        options["input_method"] = "file"
        options["file_path"] = file_path
    elif lines:
        tmp_name = f"wf_{step.run_id}_{step.step_index}.txt"
        tmp_path = os.path.join(user_folder or tempfile.gettempdir(), tmp_name)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(str(x).strip() for x in lines if str(x).strip()))
        options["input_method"] = "file"
        options["file_path"] = tmp_path
    else:
        # leave as manual if 'value' present in config; adapters already handle 'input_method'
        if options.get("value"):
            options["input_method"] = options.get("input_method", "manual")
    log.info(
        "prep_options: step=%s opts_keys=%s input_method=%r value=%r file=%r",
        step.step_index,
        sorted(list(options.keys()))[:12],
        options.get("input_method"),
        options.get("value"),
        options.get("file_path"),
    )

    return options

def _persist_scan_result(db, ToolScanHistory, ScanDiagnostics, ScanStatus, ErrorReason, *,
                         tool, user_id, result: dict, command_hint: str,
                         base_name: str = "", be_filename: str = ""):
    success = (result.get("status") in ("success", "ok"))

    scan = ToolScanHistory(
        user_id = user_id,
        tool_id = tool.id if tool else None,
        parameters = result.get("parameters") or {},  # adapters may echo inputs
        command    = result.get("command") or command_hint,
        raw_output = result.get("output") or result.get("message") or "",
        scan_success_state = bool(success),
        filename_by_user = base_name or None,
        filename_by_be   = be_filename or None,
    )
    db.session.add(scan); db.session.flush()

    er_val = result.get("error_reason")
    er_enum = ErrorReason[er_val] if er_val in ErrorReason.__members__ else None

    diag = ScanDiagnostics(
        scan_id                = scan.id,
        status                 = ScanStatus.SUCCESS if success else ScanStatus.FAILURE,
        total_domain_count     = result.get("total_domain_count"),
        valid_domain_count     = result.get("valid_domain_count"),
        invalid_domain_count   = result.get("invalid_domain_count"),
        duplicate_domain_count = result.get("duplicate_domain_count"),
        file_size_b            = result.get("file_size_b"),
        execution_ms           = result.get("execution_ms"),
        error_reason           = er_enum,
        error_detail           = result.get("error_detail"),
        value_entered          = result.get("value_entered"),
    )
    db.session.add(diag); db.session.flush()
    return scan


@celery.task(name='tools.tasks.start_run', bind=True)
def start_run(self, workflow_id: int, user_id: int | None):
    """
    Create a WorkflowRun from a definition and enqueue the coordinator.
    """
    run = create_run_from_definition(workflow_id, user_id)
    advance_run.delay(run.id)
    return {'run_id': run.id}
def _promote_queued(limit: int = 10):
    """
    Promote oldest QUEUED runs to RUNNING when users are under their cap.
    """
    rows = (
        db.session.query(WorkflowRun)
        .filter(WorkflowRun.status == WorkflowRunStatus.QUEUED)
        .order_by(WorkflowRun.created_at.asc())
        .limit(limit)
        .all()
    )
    promoted = 0
    for run in rows:
        uid = run.user_id
        if active_can_start(uid):
            active_incr(uid)
            # Let the coordinator handle status transition and dispatch
            advance_run.delay(run.id)
            promoted += 1
    return promoted

@celery.task(name="tools.tasks.reconcile_zombies")
def reconcile_zombies():
    """
    Auto-fail RUNNING runs that have not updated in a long time and free slots.
    """
    horizon = utcnow() - timedelta(minutes=45)
    zombies = (
        db.session.query(WorkflowRun)
        .filter(WorkflowRun.status == WorkflowRunStatus.RUNNING,
                WorkflowRun.updated_at < horizon)
        .all()
    )
    for r in zombies:
        r.status = WorkflowRunStatus.FAILED
        r.finished_at = utcnow()
        db.session.add(r)
        try:
            active_decr(r.user_id)
        except Exception:
            pass
    if zombies:
        db.session.commit()
    try:
        _promote_queued()
    except Exception:
        pass
    return {"zombies": len(zombies)}

@celery.task(name="tools.tasks.prune_history")
def prune_history():
    """
    Delete old runs and their artifact folders to control retention.
    """
    keep_days = int(os.environ.get("RUNS_RETENTION_DAYS", "30"))
    cutoff = utcnow() - timedelta(days=keep_days)
    old = (
        db.session.query(WorkflowRun)
        .filter(WorkflowRun.created_at < cutoff)
        .all()
    )
    deleted = 0
    base_dir = os.environ.get("ARTIFACTS_DIR", os.path.join("instance","tools_artifacts"))
    for r in old:
        try:
            path = os.path.join(base_dir, str(r.id))
            if os.path.isdir(path):
                import shutil; shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
        db.session.delete(r); deleted += 1
    if deleted:
        db.session.commit()
    return {"deleted_runs": deleted}
