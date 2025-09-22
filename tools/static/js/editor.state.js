export class WorkflowEditor {
  constructor({ API, connectRunSSE }) {
    this.API = API;
    this.connectRunSSE = connectRunSSE;

    // state
    this.tools = [];
    this.catalog = {};
    this.toolMetaBySlug = {};
    this.nodes = [];
    this.connections = [];
    this.selectedNode = null;
    this.draggedTool = null;
    this.draggedNode = null;
    this.connectionStart = null;
    this.nodeCounter = 0;
    this.globals = {};
    this.currentWorkflow = null;
    this.currentRunId = null;
    this.stopRunStream = null;
  }

  init() {
    this.addLog?.("Workflow editor initializing…");
    this.renderTools?.();
    this.loadCatalog?.().then(() => this.renderTools?.());
    this.setupEventListeners?.();
    window.addEventListener("beforeunload", () => {
      try {
        this.stopRunStream?.();
      } catch {}
    });
    this.addLog?.("Workflow editor ready");
  }

  // ————— data mapping & defaults —————
  inferNodeType(meta) {
    const t = (meta.type || "").toLowerCase();
    if (t === "start") return "start";
    if (t === "end" || t === "output" || t === "sink") return "end";
    return "process";
  }
  defaultConfigFor(meta) {
    return { input_method: "manual", value: "" };
  }

  buildGraph() {
    const nodes = this.nodes.map((n) => ({
      id: n.id,
      tool_slug: n.tool_slug || n.toolId,
      config: n.config || {},
      x: n.x,
      y: n.y,
    }));
    const edges = this.connections.map((c) => ({ from: c.from, to: c.to }));
    return { nodes, edges, globals: this.globals || {} };
  }
  // -- UI helper: enable/disable toolbar buttons while running
  setBusy(isBusy) {
    ["runBtn", "saveBtn", "loadBtn", "globalConfigBtn", "clearBtn"].forEach(
      (id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = !!isBusy;
      }
    );
  }

  // -- Main Task 3 entrypoint: save if needed, start run, attach SSE/poll
  async runWorkflow() {
    try {
      // 1) Basic guards
      if (!Array.isArray(this.nodes) || this.nodes.length === 0) {
        this.addLog?.("Nothing to run — add at least one tool");
        return;
      }
      this.validateWorkflow?.();
      const banner = document.getElementById("warningBanner");
      if (banner && !banner.classList.contains("hidden")) {
        this.addLog?.("Fix validation errors before running");
        return;
      }

      // 2) Ensure we have a saved workflow (auto-save if needed)
      if (!this.currentWorkflow?.id) {
        this.addLog?.("No preset yet — saving before run…");
        await this.savePreset?.();
        if (!this.currentWorkflow?.id) {
          this.addLog?.("Unable to save preset; aborting run");
          return;
        }
      }

      // 3) Fire the run
      this.setBusy(true);
      this.addLog?.("Starting run…");
      const res = await this.API.workflows.run(this.currentWorkflow.id);
      if (!res?.ok)
        throw new Error(res?.error?.message || "Failed to start run");

      const run = res.data?.run || res.run || res.data || res;
      const runId = run.id;
      if (!runId) throw new Error("Run id missing from response");

      this.currentRunId = runId;
      this.addLog?.(`Run started (#${runId})`);

      // clear & paint initial summary view
      try {
        await this.renderRunSummary?.(runId);
      } catch {}

      // 4) Attach SSE (with automatic fallback to polling via attachRunStream)
      this.attachRunStream?.(runId);
    } catch (e) {
      console.error(e);
      this.addLog?.(`Run error: ${e.message || e}`);
      this.setBusy(false);
    }
  }
}

// ——— response normalizers ———
export function pickWorkflow(obj) {
  if (obj?.workflow?.id) return obj.workflow;
  if (obj?.data?.workflow?.id) return obj.data.workflow;
  if (obj?.id) return obj;
  if (obj?.data?.id) return obj.data;
  if (obj?.item?.id) return obj.item;
  return null;
}
export function pickWorkflowList(obj) {
  if (Array.isArray(obj?.items)) return obj.items;
  if (Array.isArray(obj?.workflows)) return obj.workflows;
  if (Array.isArray(obj?.data)) return obj.data;
  return Array.isArray(obj) ? obj : [];
}
