from celery.utils.log import get_task_logger
from celery_app import celery
from extensions import db
from .models import (
    WorkflowRun, WorkflowRunStatus,
    WorkflowRunStep, WorkflowStepStatus,
    ToolScanHistory,  # existing audit trail for each tool exec
)
from datetime import datetime, timezone

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
    Executes a single step. In Task 5 we'll plug real tool adapters and
    wire outputs -> inputs. For now: mark RUNNING -> COMPLETED to validate flow.
    """
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        log.warning(f'run_step: run {run_id} not found')
        return {'status': 'not_found'}

    step = None
    for s in run.steps:
        if s.step_index == step_index:
            step = s
            break
    if not step:
        log.warning(f'run_step: step {step_index} not found for run {run_id}')
        return {'status': 'not_found'}

    # mark running
    step.status = WorkflowStepStatus.RUNNING
    step.started_at = utcnow()
    db.session.commit()

    try:
        # TODO (Task 5): Call your real tool adapter, capture ToolScanHistory id etc.
        # For now, simulate success:
        # step.tool_scan_history_id = <real id after /api/scan integration>
        step.output_manifest = step.output_manifest or {}
        step.status = WorkflowStepStatus.COMPLETED
        step.finished_at = utcnow()
        db.session.commit()

        # progress: completed steps / total
        total = max(1, run.total_steps or len(run.steps))
        done = sum(1 for x in run.steps if x.status == WorkflowStepStatus.COMPLETED)
        run.current_step_index = step_index + 1 if step_index + 1 < total else step_index
        run.progress_pct = round(100.0 * done / total, 2)
        db.session.commit()

        log.info(f'run_step: completed step {step_index} on run {run_id} [{run.progress_pct}%]')

    except Exception as e:
        db.session.rollback()
        step.status = WorkflowStepStatus.FAILED
        step.finished_at = utcnow()
        db.session.commit()
        run.status = WorkflowRunStatus.FAILED
        db.session.commit()
        log.exception(f'run_step: failed step {step_index} on run {run_id}: {e}')
        return {'status': 'failed', 'error': str(e)}

    # hand control back to coordinator to advance next step
    advance_run.delay(run_id)
    return {'status': 'ok'}
