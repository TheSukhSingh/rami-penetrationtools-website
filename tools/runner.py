from __future__ import annotations
from typing import List, Optional
from extensions import db
from .models import (
    WorkflowDefinition, WorkflowRun, WorkflowRunStep,
    WorkflowRunStatus, WorkflowStepStatus, Tool
)
from datetime import datetime, timezone
from tools.policies import get_effective_policy, IO_BASELINE, get_tool_stage  # IO matrix for stage gating

ALL_BUCKETS = (
    "domains","hosts","ips","ports","services",
    "urls","endpoints","params",
    "tech_stack","vulns","exploit_results","screenshots"
)
utcnow = lambda: datetime.now(timezone.utc)

from tools.policies import (
    STAGE_DISCOVERY, STAGE_VALIDATION, STAGE_ENRICHMENT, STAGE_PREP,
    STAGE_SCANNING, STAGE_EXPLOIT, STAGE_REPORTING, get_tool_stage
)

STAGE_NAME = {
    STAGE_DISCOVERY: "Discovery",
    STAGE_VALIDATION: "Validation",
    STAGE_ENRICHMENT: "Enrichment",
    STAGE_PREP: "Prep",
    STAGE_SCANNING: "Scanning",
    STAGE_EXPLOIT: "Exploitation",
    STAGE_REPORTING: "Reporting",
}

def preflight_validate_workflow(run, steps):
    """
    Enforce canonical stage order and basic readiness before scheduling.
    - Blocks obviously invalid order (e.g., Scanning before Validation).
    - Records soft warnings for borderline cases (e.g., Prep before Enrichment).
    """
    violations = []
    last_stage = 0
    for s in steps:
        stage = get_tool_stage(s.tool_name)
        if stage < last_stage:
            violations.append(
                f"Stage order violation: {s.tool_name} ({STAGE_NAME[stage]}) appears "
                f"after a later stage ({STAGE_NAME[last_stage]})."
            )
        last_stage = max(last_stage, stage)

    if violations:
        run.status_note = "\n".join(violations)
        # Hard-fail preflight; UI should surface run.status_note
        return False
    return True

def has_required_inputs_for_step(run, step):
    """
    If step consumes certain buckets, ensure the run context (rollup) has them.
    If missing, the step will be marked SKIPPED with reason 'no_input'.
    """
    consumes = (step.policy or {}).get("consumes", [])
    if not consumes:
        return True
    rollup = (run.context or {})
    for bucket in consumes:
        if rollup.get(bucket):
            return True
    return False
def _order_nodes_linear(graph: dict) -> List[str]:
    """
    Given graph {"nodes":[{id,...}], "edges":[{"from":A,"to":B},...]}
    return a linear ordering of node ids following the single path.
    Assumes v1 rule: exactly one start (no incoming edge) and a linear chain.
    """
    nodes = [n["id"] for n in (graph.get("nodes") or [])]
    edges = graph.get("edges") or []
    incoming = {nid: 0 for nid in nodes}
    forward = {}
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a is None or b is None:
            continue
        incoming[b] = incoming.get(b, 0) + 1
        forward[a] = b
        incoming.setdefault(a, incoming.get(a, 0))
        incoming.setdefault(b, incoming.get(b, 0))
    # start is the node with no incoming edge; fallback to left-most by x
    start = next((nid for nid, deg in incoming.items() if deg == 0), None)
    if start is None:
        byx = sorted(((n.get("x", 0), n["id"]) for n in (graph.get("nodes") or [])))
        start = byx[0][1] if byx else None
    order, seen, cur = [], set(), start
    while cur and cur not in seen:
        order.append(cur); seen.add(cur); cur = forward.get(cur)
    # append any isolated nodes (shouldn’t happen under linear rule)
    for n in nodes:
        if n not in order:
            order.append(n)
    return order

def create_run_from_definition(workflow_id: int, user_id: Optional[int]) -> WorkflowRun:
    wf = db.session.get(WorkflowDefinition, workflow_id)
    if not wf:
        raise ValueError("workflow not found")
    graph = wf.graph_json or {"nodes": [], "edges": []}
    order = _order_nodes_linear(graph)

    # slug → Tool
    tools_by_slug = {
        t.slug: t for t in db.session.query(Tool).filter(Tool.enabled.is_(True)).all()
    }

    # keep nodes in execution order
    id_to_node = {n["id"]: n for n in (graph.get("nodes") or [])}
    ordered_nodes = [id_to_node[nid] for nid in order if nid in id_to_node]

    run = WorkflowRun(
        workflow_id=wf.id,
        user_id=user_id,
        status=WorkflowRunStatus.QUEUED,
        current_step_index=0,
        total_steps=len(ordered_nodes),
        progress_pct=0.0,
    )
    db.session.add(run); db.session.flush()

    run.run_manifest = {
        "buckets": {k: {"count": 0, "items": []} for k in ALL_BUCKETS},
        "provenance": {k: {} for k in ALL_BUCKETS},   # e.g., {"urls": {"httpx":[...], "katana":[...]}}
        "steps": {},                                   # per-step snapshots/notes if you want
        "last_updated": utcnow().isoformat(),
    }

    for idx, node in enumerate(ordered_nodes):
        # Resolve tool
        tool_slug = node.get("tool_slug") or node.get("slug")
        tool = Tool.query.filter_by(slug=tool_slug, enabled=True).first()
        # Build per-step options (copy node config) and SNAPSHOT policy
        node_cfg = (node.get("config") or {}).copy()
        node_cfg["tool_slug"] = tool_slug

        # SNAPSHOT POLICY HERE (from ToolConfigField-derived policies)
        policy_ss = get_effective_policy(tool_slug)
        node_cfg["_policy"] = policy_ss
        io_snapshot = (policy_ss.get("io_policy") or IO_BASELINE.get(tool_slug) or {})
        node_cfg["_io_policy"] = io_snapshot
        node_cfg["io_bucket_consumes"] = (io_snapshot.get("consumes") or [])

        # Store the snapshot with options in the step's input_manifest (or wherever you keep per-step opts)
        step = WorkflowRunStep(
            run_id=run.id,
            step_index=idx,
            tool_id=tool.id if tool else None,
            status=WorkflowStepStatus.QUEUED,
            input_manifest={"options": node_cfg},  # <--- policy snapshot lives here
        )
        db.session.add(step)

    run.total_steps = len(ordered_nodes)
    run.current_step_index = 0
    run.progress_pct = 0.0

    db.session.commit()
    return run
