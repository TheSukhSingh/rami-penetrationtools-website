from datetime import datetime, timezone
import os
from flask import current_app, render_template, request, jsonify, abort, Response, send_from_directory, stream_with_context
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_
from tools.alltools.envcheck import check_env
from tools.alltools.tools._common import active_decr
from tools.models import (
    ToolCategory,
    ToolScanHistory, 
    ScanDiagnostics, 
    ScanStatus, 
    ErrorReason, 
    Tool,
    ToolCategoryLink, ToolConfigField, ToolConfigFieldType, ToolUsageDaily,
    UserToolConfig,
    WorkflowDefinition, WorkflowRun, WorkflowRunStep,
    WorkflowRunStatus, WorkflowStepStatus,
)
from extensions import db, limiter
from tools.policies import IO_BASELINE, TOOL_STAGE, get_effective_policy, get_global_specs
from . import tools_bp
from importlib import import_module
from sqlalchemy.orm import joinedload, selectinload
import json, time
from .events import _redis, _chan, publish_run_event
from .tasks import advance_run
from .runner import create_run_from_definition
from celery_app import celery
from sqlalchemy.exc import IntegrityError
from .settings import get_setting, get_rate_limit
from .validation import validate_step_input

utcnow = lambda: datetime.now(timezone.utc)

from .events import _redis

def _quota_key(kind: str, user_id: int) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    return f"tools:quota:{today}:{kind}:u{user_id}"

def _quota_allowed(kind: str, user_id: int, limit: int) -> tuple[bool, int]:
    r = _redis(); cur = int(r.get(_quota_key(kind, user_id)) or 0)
    return (cur < limit, cur)

def _quota_incr(kind: str, user_id: int, by: int = 1) -> None:
    r = _redis(); k = _quota_key(kind, user_id)
    p = r.pipeline(); p.incrby(k, by); p.expire(k, 172800); p.execute()

def _usage_bump(kind: str, user_id: int, tool_id: int | None = None):
    # kind: "scan" | "run" | "error"
    # NOTE: ToolUsageDaily already exists in models.
    day = datetime.utcnow().date()
    row = (db.session.query(ToolUsageDaily)
           .filter_by(user_id=user_id, tool_id=tool_id, day=day)
           .with_for_update(of=ToolUsageDaily, nowait=False)
           .first())
    if not row:
        row = ToolUsageDaily(user_id=user_id, tool_id=tool_id, day=day, scans=0, runs=0, errors=0)
        db.session.add(row)
    if kind == "scan":
        row.scans = (row.scans or 0) + 1
    elif kind == "run":
        row.runs = (row.runs or 0) + 1
    elif kind == "error":
        row.errors = (row.errors or 0) + 1

def _current_user_id():
    """Return the JWT identity; cast to int when possible, else keep as string."""
    ident = get_jwt_identity()
    try:
        return int(ident)
    except (TypeError, ValueError):
        return ident

def _same_user(a, b):
    """True if a and b represent the same id, tolerant to str/int."""
    return (a is not None) and (b is not None) and (str(a) == str(b))


@tools_bp.get("/")
def tools_index():
    return render_template("tools/index.html")

@tools_bp.get("/api/tools")
def api_tools():
    # Prefetch links -> tool -> config_fields to avoid N+1 queries
    cats = (
        db.session.query(ToolCategory)
        .options(
            selectinload(ToolCategory.tool_links)
                .selectinload(ToolCategoryLink.tool)
                .selectinload(Tool.config_fields)
        )
        .filter(ToolCategory.enabled.is_(True))
        .order_by(ToolCategory.sort_order.asc(), ToolCategory.name.asc())
        .all()
    )

    payload = {"categories": {}}

    for c in cats:
        rows = []
        # sort by per-category order then tool name
        links = sorted(c.tool_links, key=lambda l: ((l.sort_order or 100), (l.tool.name or "")))
        for link in links:
            t = link.tool
            if not t or not t.enabled:
                continue

            meta = t.meta_info or {}
            pol = get_effective_policy(t.slug)  # <- all from ToolConfigField (visible + hidden)

            schema = pol.get("schema_fields", [])              # fields for the modal
            runtime_constraints = pol.get("runtime_constraints", {})  # per-field min/max/etc
            input_policy = pol.get("input_policy", {})        # accepts/max_targets/file_max_bytes
            io_policy = pol.get("io_policy", {})              # consumes/emits (typed buckets)
            binaries = pol.get("binaries", {})                # {"names": ["dnsx"]}

            # Build FE-friendly defaults from schema (fallback to legacy meta.defaults if present)
            defaults = {f["name"]: f.get("default") for f in schema if f.get("default") is not None}
            legacy_defaults = (meta.get("defaults") or {})
            defaults.setdefault("input_method", legacy_defaults.get("input_method", "manual"))
            if "value" in legacy_defaults:
                defaults.setdefault("value", legacy_defaults["value"])

            rows.append({
                "slug": t.slug,
                "name": t.name,
                "desc": meta.get("desc") or "",
                "type": meta.get("type") or "",     # e.g., "recon", "crawler" (optional)
                "time": meta.get("time") or "",     # e.g., "fast", "medium" (optional)
                "defaults": defaults,

                # NEW for Step 4:
                "schema": schema,
                "runtime_constraints": runtime_constraints,
                "input_policy": input_policy,
                "io_policy": io_policy,
                "binaries": binaries,
            })
        payload["categories"][c.name] = rows

    return jsonify(payload)

@tools_bp.get("/api/specs")
def api_specs():
    specs = get_global_specs()
    return jsonify({
        **specs,
        "io_baseline": IO_BASELINE,
        "tool_stage_map": TOOL_STAGE,
    })

@tools_bp.patch("/api/tools/<slug>/enabled")
@jwt_required()
@limiter.limit("20/minute")
def set_tool_enabled(slug):
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    data = request.get_json(silent=True) or {}
    if "enabled" not in data:
        return jsonify({"error":"enabled required"}), 400
    tool.enabled = bool(data["enabled"])
    db.session.commit()
    return jsonify({"ok": True, "slug": tool.slug, "enabled": tool.enabled})

@tools_bp.patch("/api/tools/<slug>/meta")
@jwt_required()
@limiter.limit("10/minute")
def set_tool_meta(slug):
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    data = request.get_json(silent=True) or {}

    meta = tool.meta_info or {}
    # Allow basic presentation fields (optional)
    for k in ("desc","time","type"):
        if k in data:
            meta[k] = data[k]

    # Policy overlays
    if "policy_overrides" in data:
        po = data["policy_overrides"] or {}
        # only accept safe keys
        allowed = {"input_policy","binaries","runtime_constraints","io_policy","wordlist_default"}
        meta.setdefault("policy_overrides", {})
        for k, v in po.items():
            if k in allowed:
                meta["policy_overrides"][k] = v

    tool.meta_info = meta
    db.session.commit()

    # Echo the effective policy so Admin can see the merge result immediately
    pol = get_effective_policy(tool.slug)
    return jsonify({"ok": True, "tool": {"slug": tool.slug, "enabled": tool.enabled, "meta_info": tool.meta_info}, "effective_policy": pol})

@tools_bp.route('/api/scan', methods=['POST'])
@jwt_required()
@limiter.limit(lambda: get_rate_limit("SCAN_RATE_LIMIT", "5/minute"))
def api_scan():
    user_id = _current_user_id()

    # --- DB-backed upload cap (early reject) --------------------
    max_bytes = int(get_setting("MAX_UPLOAD_BYTES", 2_000_000, int))
    content_len = request.content_length or 0
    if content_len and content_len > max_bytes:
        return jsonify({
            "status": "error",
            "message": f"Upload too large (>{max_bytes} bytes)",
            "error_reason": "FILE_TOO_LARGE",
        }), 413

    # --- Daily scan quota ---------------------------------------
    scan_limit = int(get_setting("DAILY_SCAN_QUOTA", 200, int))
    ok, used = _quota_allowed("scan", user_id, scan_limit)
    if not ok:
        return jsonify({
            "status": "error",
            "message": "Daily scan quota exceeded",
            "error": "quota_exceeded",
            "limit": scan_limit,
            "used": used,
        }), 429

    tool    = request.form.get('tool') or (request.json or {}).get('tool')
    cmd     = request.form.get('cmd')

    base_name = ''
    filename  = ''

    # gather options (form/json tolerant)
    options = {}
    if request.form:
        for key, vals in request.form.lists():
            if key in ('tool', 'cmd', 'options'):
                continue
            options[key] = vals if len(vals) > 1 else vals[0]
        # optional JSON options in a form field
        if request.form.get("options"):
            try:
                options.update(json.loads(request.form.get("options")))
            except:
                pass
    elif request.is_json:
        options = (request.json or {}).get("options") or {}

    # accept either "file" or "<tool>-file" field names
    uploaded = None
    if request.files:
        uploaded = request.files.get("file") or request.files.get(f"{tool}-file")

    # --- resolve tool + server-side schema validation ------------
    tool_rec = db.session.query(Tool).filter_by(slug=tool).first()
    if not tool_rec or not tool_rec.enabled:
        return jsonify({"status": "error", "message": "Unknown or disabled tool"}), 404

    errs = validate_step_input(tool_rec, options)
    if errs:
        return jsonify({
            "status": "error",
            "message": "validation_failed",
            "error_reason": "INVALID_PARAMS",
            "errors": errs
        }), 400

    # --- save upload (if any) -----------------------------------
    if uploaded and uploaded.filename:
        from werkzeug.utils import secure_filename
        base = current_app.config['UPLOAD_INPUT_FOLDER']
        user_folder = os.path.join(base, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        base_name = secure_filename(uploaded.filename)
        timestamp = utcnow().strftime('%Y%m%d%H%M%S%f')
        filename = f"{timestamp}_{base_name}"
        filepath = os.path.join(user_folder, filename)
        uploaded.save(filepath)
        options['input_method'] = 'file'
        options['file_path'] = filepath

    # --- call adapter -------------------------------------------
    start_req = time.time()
    try:
        if tool == 'debug-echo':
            adapter = import_module("tools.alltools.tools.debug_echo")
        else:
            mod_name = tool.replace('-', '_')
            adapter = import_module(f"tools.alltools.tools.{mod_name}")
        result = adapter.run_scan(options) or {}
        success = (result.get("status") in ("success", "ok"))
    except Exception as e:
        result = {"status": "error", "message": "adapter_crash", "error_reason": "ADAPTER_CRASH", "output": str(e)}
        success = False

    if success:
        result.setdefault('status', 'success')
        result.setdefault('output', '')

    tool_rec = db.session.query(Tool).filter_by(slug=tool).first()

    scan = ToolScanHistory(
        user_id            = user_id,
        tool_id            = (tool_rec.id if tool_rec else None),
        parameters         = options,
        command            = cmd,
        raw_output         = (result.get('output') or result.get('message') or ''),
        scan_success_state = bool(success),
        filename_by_user   = base_name or None,
        filename_by_be     = filename or None,
    )
    db.session.add(scan)
    db.session.flush()

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
        execution_ms           = result.get('execution_ms'),
        error_reason           = er_enum,
        error_detail           = result.get('error_detail'),
        value_entered          = result.get('value_entered'),
    )
    db.session.add(diag)

    # usage counters
    try:
        _usage_bump("scan", user_id, tool_rec.id if tool_rec else None)
        if not success:
            _usage_bump("error", user_id, tool_rec.id if tool_rec else None)
    except Exception:
        pass

    db.session.commit()

    # --- quota increment ----------------------------------------
    try:
        _quota_incr("scan", user_id, by=1)
    except:
        pass

    # --- HTTP status mapping ------------------------------------
    status_code = 200
    if (result or {}).get("status") == "error":
        er = (result or {}).get("error_reason") or ""
        status_code = 400
        if er == "FILE_TOO_LARGE": status_code = 413
        elif er in ("INVALID_PARAMS", "TOO_MANY_DOMAINS"): status_code = 400
        elif er == "TIMEOUT": status_code = 504
        elif er == "NOT_INSTALLED": status_code = 503

    return jsonify(result), status_code
# ─────────────────────────────────────────────────────────
# Workflows CRUD (definitions / presets)
# ─────────────────────────────────────────────────────────

def _serialize_workflow(wf: WorkflowDefinition):
    return {
        "id": wf.id,
        "pretty_id": getattr(wf, "pretty_id", None),
        "owner_id": wf.owner_id,
        "title": wf.title,
        "description": wf.description,
        "version": wf.version,
        "is_shared": wf.is_shared,
        "is_archived": wf.is_archived,
        "forked_from_id": wf.forked_from_id,
        "graph": wf.graph_json or {},
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }

def _require_owner(wf: WorkflowDefinition, user_id):
    if (wf.owner_id is not None) and (not _same_user(wf.owner_id, user_id)):
        return jsonify({"error": "forbidden"}), 403

def _validate_graph(graph: dict):
    if not isinstance(graph, dict):
        return jsonify({"error":"graph must be an object"}), 400
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return jsonify({"error":"graph must contain arrays: nodes[], edges[]"}), 400
    for n in nodes:
        if not isinstance(n, dict) or "tool_slug" not in n:
            return jsonify({"error":"each node must include tool_slug"}), 400
    for e in edges:
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            return jsonify({"error":"each edge must include from/to"}), 400

@tools_bp.post("/api/workflows")
@jwt_required()
# @limiter.limit("15/minute")
def create_workflow():
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    graph = data.get("graph") or {}
    is_shared = bool(data.get("is_shared") or False)

    if not title:
        return jsonify({"error": "title is required"}), 400
    err = _validate_graph(graph)
    if err:
        return err

    wf = WorkflowDefinition(
        owner_id=user_id,
        title=title,
        description=description or None,
        version=1,
        is_shared=is_shared,
        is_archived=False,
        graph_json=graph,
    )
    db.session.add(wf)
    db.session.commit()
    return jsonify({"workflow": _serialize_workflow(wf)}), 201

@tools_bp.get("/api/workflows")
@jwt_required()
def list_workflows():
    user_id = _current_user_id()
    q = (request.args.get("q") or "").strip()
    mine = request.args.get("mine", "true").lower() in ("1", "true", "yes")
    shared = request.args.get("shared", "false").lower() in ("1", "true", "yes")
    include_archived = request.args.get("include_archived", "false").lower() in ("1", "true", "yes")

    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)

    qry = db.session.query(WorkflowDefinition)
    filters = []
    if mine:
        filters.append(WorkflowDefinition.owner_id == user_id)
    if shared:
        filters.append(WorkflowDefinition.is_shared.is_(True))
    if filters:
        qry = qry.filter(or_(*filters))
    else:
        qry = qry.filter(WorkflowDefinition.owner_id == user_id)

    if not include_archived:
        qry = qry.filter(WorkflowDefinition.is_archived.is_(False))

    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(WorkflowDefinition.title.ilike(like),
                             WorkflowDefinition.description.ilike(like)))

    qry = qry.order_by(WorkflowDefinition.updated_at.desc(), WorkflowDefinition.id.desc())
    page_obj = qry.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [_serialize_workflow(w) for w in page_obj.items],
        "page": page_obj.page, "per_page": page_obj.per_page,
        "total": page_obj.total, "pages": page_obj.pages
    })

@tools_bp.get("/api/workflows/<int:wf_id>")
@jwt_required()
def get_workflow(wf_id: int):
    user_id = _current_user_id()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    if (not _same_user(wf.owner_id, user_id)) and not wf.is_shared:
        return jsonify({"error":"forbidden"}), 403
    return jsonify({"workflow": _serialize_workflow(wf)})

@tools_bp.put("/api/workflows/<int:wf_id>")
@jwt_required()
@limiter.limit("20/minute")
def update_workflow(wf_id: int):
    user_id = _current_user_id()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    err = _require_owner(wf, user_id)
    if err: return err

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        wf.title = title
    if "description" in data:
        wf.description = (data.get("description") or "").strip() or None
    if "is_shared" in data:
        wf.is_shared = bool(data.get("is_shared"))
    if "graph" in data:
        graph = data.get("graph") or {}
        err = _validate_graph(graph)
        if err: return err
        if (wf.graph_json or {}) != graph:
            wf.graph_json = graph
            wf.version = (wf.version or 1) + 1

    db.session.commit()
    return jsonify({"workflow": _serialize_workflow(wf)})

@tools_bp.post("/api/workflows/<int:wf_id>/clone")
@jwt_required()
@limiter.limit("10/minute")
def clone_workflow(wf_id: int):
    user_id = _current_user_id()
    src = db.session.get(WorkflowDefinition, wf_id)
    if not src:
        return jsonify({"error": "not found"}), 404
    if (not _same_user(src.owner_id, user_id)) and not src.is_shared:
        return jsonify({"error":"forbidden"}), 403

    data = request.get_json(silent=True) or {}
    new_title = (data.get("title") or f"{src.title} (Copy)").strip()
    clone = WorkflowDefinition(
        owner_id=user_id,
        title=new_title,
        description=src.description,
        version=1,
        is_shared=False,
        is_archived=False,
        forked_from_id=src.id,
        graph_json=src.graph_json or {}
    )
    db.session.add(clone)
    db.session.commit()
    return jsonify({"workflow": _serialize_workflow(clone)}), 201

@tools_bp.delete("/api/workflows/<int:wf_id>")
@jwt_required()
@limiter.limit("10/minute")
def delete_workflow(wf_id: int):
    user_id = _current_user_id()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    err = _require_owner(wf, user_id)
    if err: return err

    wf.is_archived = True
    db.session.commit()
    return ("", 204)

# ─────────────────────────────────────────────────────────
# SSE: live run events (reattach-safe)
# ─────────────────────────────────────────────────────────
def _serialize_step(s: WorkflowRunStep):
    return {
        "step_index": s.step_index,
        "tool_id": s.tool_id,
        "status": s.status.name if s.status else None,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        "tool_scan_history_id": s.tool_scan_history_id,
    }

def _serialize_run(run: WorkflowRun):
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "user_id": run.user_id,
        "status": run.status.name if run.status else None,
        "current_step_index": run.current_step_index,
        "total_steps": run.total_steps,
        "progress_pct": run.progress_pct,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "steps": [_serialize_step(s) for s in run.steps],
    }


@tools_bp.get("/api/runs/<int:run_id>/events")
@jwt_required()
def run_events(run_id: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403

    def gen():
        yield "retry: 3000\n\n"  # reconnection delay
        snap = json.dumps({"type":"snapshot","run": _serialize_run(run)})
        yield f"event: snapshot\ndata: {snap}\n\n"

        r = _redis()
        pubsub = r.pubsub()
        pubsub.subscribe(_chan(run_id))
        last_ping = time.time()
        try:
            for msg in pubsub.listen():
                now = time.time()
                if now - last_ping > 15:
                    last_ping = now
                    yield ": ping\n\n"
                if msg.get("type") != "message":
                    continue
                yield f"event: update\ndata: {msg['data']}\n\n"
        finally:
            try: pubsub.close()
            except: pass

    resp = Response(stream_with_context(gen()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp

# ─────────────────────────────────────────────────────────
# Runs API (start / get / list / pause / resume / cancel / step detail)
# ─────────────────────────────────────────────────────────

@tools_bp.post("/api/workflows/<int:wf_id>/run")
@jwt_required()
@limiter.limit(lambda: get_rate_limit("RUN_RATE_LIMIT", "10/minute"))
def start_run_api(wf_id: int):
    user_id = _current_user_id()

    # permission: owner or shared
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not found"}), 404
    if (not _same_user(wf.owner_id, user_id)) and not wf.is_shared:
        return jsonify({"error":"forbidden"}), 403

    # --- Daily run quota (DB) -----------------------------------
    run_limit = int(get_setting("DAILY_RUN_QUOTA", 50, int))
    ok, used = _quota_allowed("run", user_id, run_limit)
    
    if not ok:
        return jsonify({
            "status": "error",
            "error": "quota_exceeded",
            "message": "Daily workflow run quota exceeded",
            "limit": run_limit,
            "used": used,
        }), 429

    from tools.alltools.tools._common import ops_redis, dedupe_run_key, RUN_START_DEDUP_TTL, active_can_start, active_incr

    # de-dupe burst clicks
    r = ops_redis()
    dkey = dedupe_run_key(user_id, wf_id)
    if not r.set(dkey, "1", nx=True, ex=RUN_START_DEDUP_TTL):
        return jsonify({"ok": True, "deduped": True, "message": "Run already starting"}), 202

    run = create_run_from_definition(wf_id, user_id)

    if active_can_start(user_id):
        active_incr(user_id)
        queue_name = current_app.config.get("CELERY_QUEUE", "tools_default")
        advance_run.apply_async(args=[run.id], queue=queue_name)
    # else leave QUEUED for promoter

    # --- quota increment ----------------------------------------
    try:
        _quota_incr("run", user_id, by=1)
    except:
        pass

    publish_run_event(run.id, "run", {
        "status": run.status.name,
        "progress_pct": run.progress_pct,
        "current_step_index": run.current_step_index
    })

    try:
        _usage_bump("run", user_id, None)
    except Exception:
        pass

    return jsonify({"run": _serialize_run(run)}), 201

@tools_bp.get("/api/ops/health")
@jwt_required()
def ops_health():
    from tools.alltools.tools._common import ops_redis, RUNS_MAX_ACTIVE_PER_USER
    r = ops_redis()
    try:
        # For Redis broker the main queue list name is usually 'celery'
        qname = current_app.config.get("CELERY_QUEUE", "tools_default")
        q_depth = int(r.llen(qname))
    except Exception:
        q_depth = None
    return jsonify({
    "ok": True,
    "queue_depth": q_depth,
    "per_user_cap": RUNS_MAX_ACTIVE_PER_USER,
    "settings": {
        "MAX_UPLOAD_BYTES": int(get_setting("MAX_UPLOAD_BYTES", 2_000_000, int)),
        "DAILY_SCAN_QUOTA": int(get_setting("DAILY_SCAN_QUOTA", 200, int)),
        "DAILY_RUN_QUOTA":  int(get_setting("DAILY_RUN_QUOTA", 50, int)),
        "SCAN_RATE_LIMIT":  get_setting("SCAN_RATE_LIMIT", "5/minute", str),
        "RUN_RATE_LIMIT":   get_setting("RUN_RATE_LIMIT", "10/minute", str),
        "UPLOAD_RETENTION_DAYS": int(get_setting("UPLOAD_RETENTION_DAYS", 7, int)),
    },
})


@tools_bp.post("/api/workflows/<int:wf_id>/nodes/<node_id>/config")
@jwt_required()
def upsert_node_config(wf_id: int, node_id: str):
    user_id = _current_user_id()
    wf = db.session.get(WorkflowDefinition, wf_id)
    if not wf:
        return jsonify({"error": "not_found"}), 404
    # owner check (mirror whatever you use elsewhere)
    if (wf.owner_id is not None) and (not _same_user(wf.owner_id, user_id)):
        return jsonify({"error": "forbidden"}), 403


    payload = request.get_json(silent=True) or {}
    cfg = payload.get("config") or {}

    graph = wf.graph_json or {}
    nodes = graph.get("nodes") or []
    updated = False
    for n in nodes:
        if str(n.get("id")) == str(node_id):
            n["config"] = {**(n.get("config") or {}), **cfg}
            updated = True
            break
    if not updated:
        return jsonify({"error": "node_not_found"}), 404

    wf.graph_json = graph
    db.session.commit()
    return jsonify({"ok": True, "workflow": {"id": wf.id}, "node": {"id": node_id, "config": cfg}})


@tools_bp.get("/api/runs/<int:run_id>/artifacts/<path:relpath>")
@jwt_required()
def download_artifact(run_id: int, relpath: str):
    run = db.session.get(WorkflowRun, run_id)
    if not run or not _same_user(run.user_id, _current_user_id()):
        return jsonify({"error":"forbidden"}), 403
    if relpath.startswith(("/", "\\")) or ".." in relpath.split("/"):
        return jsonify({"error":"bad_path"}), 400

    from werkzeug.utils import safe_join
    base_dir = current_app.config.get(
        "ARTIFACTS_DIR",
        os.path.join(current_app.instance_path, "tools_artifacts"),
    )
    full = safe_join(base_dir, str(run_id), relpath)
    if not full or not os.path.isfile(full):
        return jsonify({"error":"not_found"}), 404

    directory, fname = os.path.dirname(full), os.path.basename(full)
    return send_from_directory(directory, fname, as_attachment=True,
                               mimetype="application/octet-stream", max_age=300)
                               
@tools_bp.get("/api/runs/<int:run_id>")
@jwt_required()
def get_run_api(run_id: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run: return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403
    return jsonify({"run": _serialize_run(run)})

@tools_bp.get("/api/runs")
@jwt_required()
def list_runs_api():
    user_id = _current_user_id()
    mine = request.args.get("mine", "true").lower() in ("1","true","yes")
    status = (request.args.get("status") or "").upper().strip()
    wf_id = request.args.get("workflow_id", type=int)
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)

    qry = db.session.query(WorkflowRun)
    if mine:
        qry = qry.filter(WorkflowRun.user_id == user_id)
    if wf_id:
        qry = qry.filter(WorkflowRun.workflow_id == wf_id)
    if status and status in WorkflowRunStatus.__members__:
        qry = qry.filter(WorkflowRun.status == WorkflowRunStatus[status])

    qry = qry.order_by(WorkflowRun.updated_at.desc(), WorkflowRun.id.desc())
    page_obj = qry.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [_serialize_run(r) for r in page_obj.items],
        "page": page_obj.page, "per_page": page_obj.per_page,
        "total": page_obj.total, "pages": page_obj.pages
    })

@tools_bp.get("/api/runs/<int:run_id>/steps/<int:step_index>")
@jwt_required()
def get_run_step_api(run_id: int, step_index: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run: return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403
    step = next((s for s in run.steps if s.step_index == step_index), None)
    if not step: return jsonify({"error":"step not found"}), 404
    data = _serialize_step(step)
    # include manifests (useful for debugging)
    data["input_manifest"] = step.input_manifest
    data["output_manifest"] = step.output_manifest
    return jsonify({"step": data})

@tools_bp.post("/api/runs/<int:run_id>/pause")
@jwt_required()
@limiter.limit("15/minute")
def pause_run_api(run_id: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run: return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403

    if run.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.CANCELED, WorkflowRunStatus.FAILED):
        return jsonify({"error":"run is already finished"}), 400

    run.status = WorkflowRunStatus.PAUSED
    db.session.commit()
    publish_run_event(run.id, "run", {
        "status": run.status.name,
        "progress_pct": run.progress_pct,
        "current_step_index": run.current_step_index
    })
    return jsonify({"run": _serialize_run(run)})

@tools_bp.post("/api/runs/<int:run_id>/resume")
@jwt_required()
@limiter.limit("15/minute")
def resume_run_api(run_id: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run: return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403

    if run.status not in (WorkflowRunStatus.PAUSED, WorkflowRunStatus.QUEUED):
        return jsonify({"error":"run is not paused/queued"}), 400

    # set QUEUED and let coordinator set RUNNING & dispatch
    run.status = WorkflowRunStatus.QUEUED
    db.session.commit()
    publish_run_event(run.id, "run", {
        "status": run.status.name,
        "progress_pct": run.progress_pct,
        "current_step_index": run.current_step_index
    })
    advance_run.delay(run.id)
    return jsonify({"run": _serialize_run(run)})

@tools_bp.post("/api/runs/<int:run_id>/cancel")
@jwt_required()
@limiter.limit("15/minute")
def cancel_run_api(run_id: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run: return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403

    if run.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.CANCELED):
        return jsonify({"error":"run already finished"}), 400

    # Revoke currently running step if any
    running_step = next((s for s in run.steps if s.status == WorkflowStepStatus.RUNNING), None)
    if running_step and running_step.celery_task_id:
        try:
            celery.control.revoke(running_step.celery_task_id, terminate=True, signal="SIGTERM")
        except Exception as e:
            current_app.logger.warning(f"cancel_run: revoke failed for task {running_step.celery_task_id}: {e}")
        # mark it canceled in DB right away
        running_step.status = WorkflowStepStatus.CANCELED
        running_step.finished_at = utcnow()

    # Mark remaining queued steps as canceled
    for s in run.steps:
        if s.status == WorkflowStepStatus.QUEUED:
            s.status = WorkflowStepStatus.CANCELED

    run.status = WorkflowRunStatus.CANCELED
    db.session.commit()

    # Free the active slot and promote a queued run if any
    try:
        from tools.tasks import _promote_queued
        active_decr(run.user_id)
        _promote_queued()
    except Exception:
        pass

    publish_run_event(run.id, "run", {
        "status": run.status.name,
        "progress_pct": run.progress_pct,
        "current_step_index": run.current_step_index
    })
    return jsonify({"run": _serialize_run(run)})

@tools_bp.post("/api/runs/<int:run_id>/retry")
@jwt_required()
@limiter.limit("10/minute")
def retry_run_api(run_id: int):
    """
    Reset a failed/canceled step (and all later steps) to QUEUED, then resume.
    Body: {"step_index": <int>}
    """
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run: return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if "step_index" not in data:
        return jsonify({"error":"step_index required"}), 400
    step_index = int(data["step_index"])

    step = next((s for s in run.steps if s.step_index == step_index), None)
    if not step: return jsonify({"error":"step not found"}), 404

    # Only allow retry from FAILED or CANCELED (or even COMPLETED to rerun intentionally)
    if step.status not in (WorkflowStepStatus.FAILED, WorkflowStepStatus.CANCELED, WorkflowStepStatus.COMPLETED):
        # If it's RUNNING, ask to cancel first
        return jsonify({"error":"step not in retryable state"}), 400

    # Reset this step and all later steps to QUEUED; clear outputs/task ids
    affected = [s for s in run.steps if s.step_index >= step_index]
    for s in affected:
        s.status = WorkflowStepStatus.QUEUED
        s.started_at = None
        s.finished_at = None
        s.output_manifest = None
        s.tool_scan_history_id = None
        s.celery_task_id = None

    run.status = WorkflowRunStatus.QUEUED
    run.current_step_index = step_index
    # recompute progress
    done = sum(1 for s in run.steps if s.status == WorkflowStepStatus.COMPLETED)
    total = max(1, run.total_steps or len(run.steps))
    run.progress_pct = round(100.0 * done / total, 2)
    db.session.commit()

    publish_run_event(run.id, "run", {
        "status": run.status.name,
        "progress_pct": run.progress_pct,
        "current_step_index": run.current_step_index
    })
    # enqueue coordinator
    advance_run.delay(run.id)
    return jsonify({"run": _serialize_run(run)})

@tools_bp.route("/api/runs/<int:run_id>/summary", methods=["GET"])
@jwt_required()
def get_run_summary(run_id: int):
    user_id = _current_user_id()
    run = db.session.get(WorkflowRun, run_id)
    if not run:
        return jsonify({"error":"not found"}), 404
    if (run.user_id is not None) and (not _same_user(run.user_id, user_id)):
        return jsonify({"error":"forbidden"}), 403
    # Ensure structure even if empty
    ALL_BUCKETS = (
        "domains","hosts","ips","ports","services",
        "urls","endpoints","params",
        "tech_stack","vulns","exploit_results","screenshots"
    )
    manifest = run.run_manifest or {
        "buckets": {k: {"count": 0, "items": []} for k in ALL_BUCKETS},
        "provenance": {k: {} for k in ALL_BUCKETS},
        "steps": {},
        "last_updated": None,
    }

    # Add top-level counters for convenience
    counters = {k: manifest["buckets"][k]["count"] for k in manifest["buckets"].keys()}
    return jsonify({
        "run_id": run_id,
        "counters": counters,
        "manifest": manifest,
    })

def _tool_to_dict(tool):
    pol = get_effective_policy(tool.slug)
    return {
        "id": tool.id,
        "slug": tool.slug,
        "name": tool.name,
        "enabled": tool.enabled,
        "meta_info": tool.meta_info or {},
        "schema_fields": pol.get("schema_fields", []),
        "input_policy": pol.get("input_policy", {}),
        "binaries": pol.get("binaries", {}),
        # you can include runtime_constraints if FE wants to render HTML min/max quickly
        "runtime_constraints": pol.get("runtime_constraints", {}),
    }

def _tool_to_dict_with_schema(t: Tool):
    meta = t.meta_info or {}
    categories = [
        link.category.name
        for link in (t.category_links or [])
        if link.category and link.category.enabled
    ]
    return {
        "id": t.id,
        "slug": t.slug,
        "name": t.name,
        "categories": categories,  # list of category names
        "description": (meta.get("desc") or meta.get("description") or ""),
        "enabled": t.enabled,
        "schema": [f.to_dict() for f in t.config_fields],
    }

@tools_bp.get("/api/tools-flat")
def list_tools():
    rows = (
        db.session.query(Tool)
        .options(
            joinedload(Tool.config_fields),
            joinedload(Tool.category_links).joinedload(ToolCategoryLink.category),
        )
        .order_by(Tool.name.asc())
        .all()
    )
    return jsonify([_tool_to_dict_with_schema(t) for t in rows])

@tools_bp.get("/api/tools/<slug>/schema")
@jwt_required()
def get_tool_schema(slug):
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    return jsonify({
        "tool": {"id": tool.id, "slug": tool.slug, "name": tool.name},
        "fields": [f.to_dict() for f in tool.config_fields],
    })

@tools_bp.post("/api/tools/<slug>/schema")
@jwt_required()
@limiter.limit("10/minute")
def set_tool_schema(slug):
    """
    Replaces the schema for a tool with the provided list of fields.
    Body:
    {
      "fields": [
         {"name":"input_method","label":"Input","type":"select","choices":[...],"default":"manual","order_index":0},
         ...
      ]
    }
    """
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    payload = request.get_json(silent=True) or {}
    fields = payload.get("fields", [])
    if not isinstance(fields, list):
        abort(400, "fields must be a list")

    # clear then re-create fields (simple first implementation)
    ToolConfigField.query.filter_by(tool_id=tool.id).delete()

    created = []
    for idx, f in enumerate(fields):
        try:
            t = f.get("type", "string")
            field = ToolConfigField(
                tool_id=tool.id,
                name=f["name"],
                label=f.get("label") or f["name"].replace("_", " ").title(),
                type=ToolConfigFieldType(t),
                required=bool(f.get("required", False)),
                help_text=f.get("help_text"),
                placeholder=f.get("placeholder"),
                default=f.get("default"),
                choices=f.get("choices") if f.get("choices") else None,
                group=f.get("group"),
                order_index=int(f.get("order_index", idx)),
                advanced=bool(f.get("advanced", False)),
                visible=bool(f.get("visible", True)),
            )
            db.session.add(field); created.append(field)
        except Exception as e:
            db.session.rollback()
            abort(400, f"invalid field #{idx}: {e}")

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        abort(400, f"unique/constraint error: {e.orig}")

    return jsonify({"ok": True, "fields": [f.to_dict() for f in created]}), 201

@tools_bp.get("/api/tools/<slug>/user-defaults")
@jwt_required()
def get_user_tool_defaults(slug):
    # get current_user.id if you have auth; here just stub user_id from request context/session
    user_id = _current_user_id()
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    row = UserToolConfig.query.filter_by(user_id=user_id, tool_id=tool.id).first()
    return jsonify({"values": (row.values if row else {})})

@tools_bp.post("/api/tools/<slug>/user-defaults")
@jwt_required()
@limiter.limit("20/minute")
def set_user_tool_defaults(slug):
    user_id = _current_user_id()
    tool = Tool.query.filter_by(slug=slug).first_or_404()
    payload = request.get_json(silent=True) or {}
    values = payload.get("values") or {}

    row = UserToolConfig.query.filter_by(user_id=user_id, tool_id=tool.id).first()
    if not row:
        row = UserToolConfig(user_id=user_id, tool_id=tool.id, values=values)
        db.session.add(row)
    else:
        row.values = values
    db.session.commit()
    return jsonify({"ok": True, "values": row.values})

@tools_bp.get("/api/envcheck")
@jwt_required()
def api_envcheck():
    return jsonify(check_env())