from importlib import import_module
import os
import tempfile
from celery.utils.log import get_task_logger
from celery_app import celery
from extensions import db
from .models import (
    ErrorReason, ScanDiagnostics, ScanStatus, WorkflowRun, WorkflowRunStatus,
    WorkflowRunStep, WorkflowStepStatus,
    ToolScanHistory,  # existing audit trail for each tool exec
)
from pathlib import Path
from datetime import datetime, timedelta, timezone
from .runner import create_run_from_definition
from flask import current_app
from .events import publish_run_event
from tools import ingest
from tools.alltools.tools._common import active_decr, active_incr, active_can_start, ops_redis
import shutil

utcnow = lambda: datetime.now(timezone.utc)
log = get_task_logger(__name__)



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

    # Only QUEUED can transition to RUNNING here
    if run.status == WorkflowRunStatus.QUEUED:
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = run.started_at or utcnow()
        db.session.commit()
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })

    # Next step: ONLY QUEUED (no auto-retry of FAILED/CANCELED)
    steps = list(run.steps)  # ordered
    next_step = next((s for s in steps if s.status == WorkflowStepStatus.QUEUED), None)

    if not next_step:
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
        # (Optional) try to promote a queued run now; see helper below
        try:
            _promote_queued()
        except Exception:
            pass
        return {'status': 'completed'}

    publish_run_event(run.id, "dispatch", {"step_index": next_step.step_index})
    queue_name = current_app.config.get("CELERY_QUEUE", "tools_default")
    res = run_step.apply_async(args=[run_id, next_step.step_index], queue=queue_name)
    # record Celery task id for cancel/revoke
    next_step.celery_task_id = res.id
    db.session.commit()
    return {'status': 'dispatched', 'task_id': res.id}

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
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        log.warning(f'run_step: run {run_id} not found')
        return {'status': 'not_found'}

    step = next((s for s in run.steps if s.step_index == step_index), None)
    if not step:
        log.warning(f'run_step: step {step_index} not found for run {run_id}')
        return {'status': 'not_found'}

    # If run paused/canceled while we were queued, don't run
    if run.status == WorkflowRunStatus.CANCELED:
        step.status = WorkflowStepStatus.CANCELED
        step.finished_at = utcnow()
        db.session.commit()
        publish_run_event(run.id, "step", {"step_index": step_index, "status": "CANCELED"})
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })
        return {'status': 'canceled'}

    if run.status == WorkflowRunStatus.PAUSED:
        # put it back to QUEUED and exit; coordinator won't dispatch while paused
        step.status = WorkflowStepStatus.QUEUED
        db.session.commit()
        publish_run_event(run.id, "step", {"step_index": step_index, "status": "QUEUED"})
        return {'status': 'paused'}

    # mark running and publish
    step.status = WorkflowStepStatus.RUNNING
    step.started_at = utcnow()
    db.session.commit()
    publish_run_event(run.id, "step", {
        "step_index": step_index, "status": "RUNNING"
    })

    if run.status == WorkflowRunStatus.QUEUED:
        run.status = WorkflowRunStatus.RUNNING
        if not run.started_at:
            run.started_at = utcnow()
        db.session.commit()
        publish_run_event(run.id, "run", {
            "status": run.status.name,
            "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })

    prev_output = {}
    if step_index > 0:
        prev = next((ps for ps in run.steps if ps.step_index == step_index - 1), None)
        prev_output = (prev.output_manifest or {}) if prev else {}

    try:
        tool = step.tool
        if not tool or not tool.enabled:
            raise RuntimeError("tool disabled or missing")
        slug = tool.slug

        # load adapter + prepare options
        mod_name = slug.replace('-', '_')
        adapter = import_module(f".alltools.tools.{mod_name}", package="tools")

        # Create step work dir FIRST (so ingest can write inbox file if needed)
        base = current_app.config.get(
            "TOOLS_WORK_DIR",
            current_app.config.get("ARTIFACTS_DIR", "/tmp/hackr_runs"),
        )
        step_dir = Path(base) / f"run_{run.id}" / f"step_{step_index:02d}_{tool.slug}"
        step_dir.mkdir(parents=True, exist_ok=True)

        # Build options via ingest (DB-driven; upstream + config + seeds; normalize/dedupe/cap)
        options = ingest.build_inputs_for_step(run, step, step_dir, current_app.config, slug=slug)
        
        # Inject the per-step policy snapshot captured by the runner
        base_opts = ((step.input_manifest or {}).get("options") or {})
        snap = base_opts.get("_policy")
        if snap:
            options["_policy"] = snap

        # Always provide tool_slug for adapters that rely on it
        options.setdefault("tool_slug", slug)
        options["work_dir"] = str(step_dir)

        # Execute tool
        result = adapter.run_scan(options) or {}
        # Normalize/stage artifact(s) for download
        try:
            of = result.get("output_file")
            if of and os.path.isfile(of):
                rel = _stage_artifact(run.id, step_index, slug, of)
                if rel:
                    result["artifact_relpath"] = rel
                    result["download_url"] = f"/tools/api/runs/{run.id}/artifacts/{rel}"
        except Exception:
            pass

        success = (result.get("status") in ("success","ok"))

        # Persist scan + diagnostics
        command_hint = f"{slug} (workflow step {step_index})"
        scan = _persist_scan_result(db, ToolScanHistory, ScanDiagnostics, ScanStatus, ErrorReason,
                                    tool=tool, user_id=run.user_id, result=result, command_hint=command_hint)

        step.tool_scan_history_id = scan.id
        step.output_manifest = result
        step.status = WorkflowStepStatus.COMPLETED if success else WorkflowStepStatus.FAILED
        step.finished_at = utcnow()
        db.session.commit()
        # Update the run-level manifest with typed buckets for the summary panel
        try:
            _aggregate_run_manifest(db, run, step_index, slug, result)
        except Exception as e:
            log.warning("aggregate failed for run %s step %s: %r", run.id, step_index, e)

        # progress
        total = max(1, run.total_steps or len(run.steps))
        done = sum(1 for x in run.steps if x.status == WorkflowStepStatus.COMPLETED)
        run.current_step_index = min(step_index + 1, total - 1)
        if not success:
            run.status = WorkflowRunStatus.FAILED
        run.progress_pct = round(100.0 * done / total, 2)
        db.session.commit()
        # If the run failed, free the user's active slot and try to promote a queued run
        if not success:
            try:
                active_decr(run.user_id)
                _promote_queued()
            except Exception:
                pass
        # publish state after commit
        publish_run_event(run.id, "step", {
            "step_index": step_index,
            "status": step.status.name,
            "tool_id": step.tool_id,
            "tool_scan_history_id": step.tool_scan_history_id,
        })
        publish_run_event(run.id, "run", {
            "status": run.status.name,
            "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })

    except Exception as e:
        db.session.rollback()
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = utcnow()
        db.session.commit()
        run.status = WorkflowRunStatus.FAILED
        db.session.commit()
        publish_run_event(run.id, "step", {"step_index": step_index, "status": "FAILED"})
        publish_run_event(run.id, "run", {
            "status": run.status.name, "progress_pct": run.progress_pct,
            "current_step_index": run.current_step_index
        })
        log.exception(f'run_step: failed step {step_index} on run {run_id}: {e}')
        return {'status': 'failed', 'error': str(e)}

    # guard re-advance if paused/canceled right after commit
    db.session.refresh(run)
    if run.status in (WorkflowRunStatus.PAUSED, WorkflowRunStatus.CANCELED):
        log.info(f'run_step: not advancing (run {run_id} is {run.status.name})')
        return {'status': 'ok'}

    if step.status == WorkflowStepStatus.COMPLETED:
        advance_run.delay(run.id)
    return {'status': 'ok' if step.status == WorkflowStepStatus.COMPLETED else 'failed'}


def _load_adapter_for_slug(slug: str):
    """Slug 'github-subdomains' -> module tools.alltools.github_subdomains"""
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
