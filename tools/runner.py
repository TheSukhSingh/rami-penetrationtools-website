from __future__ import annotations
from typing import List, Optional
from extensions import db
from .models import (
    WorkflowDefinition, WorkflowRun, WorkflowRunStep,
    WorkflowRunStatus, WorkflowStepStatus, Tool
)
from datetime import datetime, timezone
from tools.policies import get_effective_policy

utcnow = lambda: datetime.now(timezone.utc)

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
