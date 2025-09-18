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
from datetime import datetime, timezone
from .runner import create_run_from_definition
from flask import current_app

utcnow = lambda: datetime.now(timezone.utc)
log = get_task_logger(__name__)

@celery.task(name='tools.tasks.ping')
def ping(msg='ok'):
    log.info(f'[ping] {msg}')
    return {'pong': msg}

@celery.task(name='tools.tasks.advance_run', bind=True)
def advance_run(self, run_id: int):
    """
    Coordinator: picks next QUEUED step, dispatches run_step, updates run status.
    v1: sequential, linear chains.
    """
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        log.warning(f'advance_run: run {run_id} not found')
        return {'status': 'not_found'}

    # if first time, mark running
    if run.status in (WorkflowRunStatus.QUEUED, WorkflowRunStatus.PAUSED):
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = run.started_at or utcnow()
        db.session.commit()

    # find next step
    steps = list(run.steps)  # ordered by step_index (see model)
    next_step = None
    for s in steps:
        if s.status in (WorkflowStepStatus.QUEUED, WorkflowStepStatus.FAILED, WorkflowStepStatus.CANCELED):
            next_step = s
            break

    if not next_step:
        # all done
        run.status = WorkflowRunStatus.COMPLETED
        run.finished_at = utcnow()
        run.progress_pct = 100.0
        db.session.commit()
        log.info(f'advance_run: run {run_id} completed')
        return {'status': 'completed'}

    # dispatch the concrete step
    log.info(f'advance_run: dispatch step {next_step.step_index} for run {run_id}')
    res = run_step.delay(run_id, next_step.step_index)
    return {'status': 'dispatched', 'task_id': res.id}

@celery.task(name='tools.tasks.run_step', bind=True)
def run_step(self, run_id: int, step_index: int):
    """
    Executes a single step using the real tool adapter.
    """
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        log.warning(f'run_step: run {run_id} not found')
        return {'status': 'not_found'}

    step = next((s for s in run.steps if s.step_index == step_index), None)
    if not step:
        log.warning(f'run_step: step {step_index} not found for run {run_id}')
        return {'status': 'not_found'}

    # mark running
    step.status = WorkflowStepStatus.RUNNING
    step.started_at = utcnow()
    db.session.commit()

    prev_output = {}
    if step_index > 0:
        prev = next((ps for ps in run.steps if ps.step_index == step_index - 1), None)
        prev_output = (prev.output_manifest or {}) if prev else {}

    try:
        tool = step.tool
        if not tool or not tool.enabled:
            raise RuntimeError("tool disabled or missing")
        slug = tool.slug
        adapter = _load_adapter_for_slug(slug)

        options = _prep_options_for_tool(step, prev_output, run.user_id, current_app.config)

        # Execute tool
        result = adapter.run_scan(options) or {}
        success = (result.get("status") in ("success","ok"))

        # Persist scan history + diagnostics
        command_hint = f"{slug} (workflow step {step_index})"
        from .models import ToolScanHistory  # avoid circulars at import time
        scan = _persist_scan_result(db, ToolScanHistory, ScanDiagnostics, ScanStatus, ErrorReason,
                                    tool=tool, user_id=run.user_id, result=result, command_hint=command_hint)

        # Link step to the scan, save output manifest for the next step
        step.tool_scan_history_id = scan.id
        step.output_manifest = result

        if success:
            step.status = WorkflowStepStatus.COMPLETED
        else:
            step.status = WorkflowStepStatus.FAILED
            run.status = WorkflowRunStatus.FAILED

        step.finished_at = utcnow()
        db.session.commit()

        # progress: completed steps / total
        total = max(1, run.total_steps or len(run.steps))
        done = sum(1 for x in run.steps if x.status == WorkflowStepStatus.COMPLETED)
        run.current_step_index = step_index + 1 if step_index + 1 < total else step_index
        run.progress_pct = round(100.0 * done / total, 2)
        db.session.commit()

        log.info(f'run_step: {"completed" if success else "failed"} step {step_index} on run {run_id} [{run.progress_pct}%]')

    except Exception as e:
        db.session.rollback()
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = utcnow()
        db.session.commit()
        run.status = WorkflowRunStatus.FAILED
        db.session.commit()
        log.exception(f'run_step: failed step {step_index} on run {run_id}: {e}')
        return {'status': 'failed', 'error': str(e)}

    # If success, advance; if failed, coordinator will mark run end on next tick
    if step.status == WorkflowStepStatus.COMPLETED:
        advance_run.delay(run.id)
    return {'status': 'ok' if step.status == WorkflowStepStatus.COMPLETED else 'failed'}


def _load_adapter_for_slug(slug: str):
    """Slug 'github-subdomains' -> module tools.alltools.github_subdomains"""
    mod_name = slug.replace('-', '_')
    return import_module(f".alltools.{mod_name}", package="tools")

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
