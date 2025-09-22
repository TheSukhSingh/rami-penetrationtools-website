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
    this.addLog?.('Workflow editor initializing…');
    this.renderTools?.();
    this.loadCatalog?.().then(() => this.renderTools?.());
    this.setupEventListeners?.();
    window.addEventListener('beforeunload', () => { try { this.stopRunStream?.(); } catch {} });
    this.addLog?.('Workflow editor ready');
  }

  // ————— data mapping & defaults —————
  inferNodeType(meta) {
    const t = (meta.type || '').toLowerCase();
    if (t === 'start') return 'start';
    if (t === 'end' || t === 'output' || t === 'sink') return 'end';
    return 'process';
  }
  defaultConfigFor(meta) { return { input_method: 'manual', value: '' }; }

  buildGraph() {
    const nodes = this.nodes.map(n => ({
      id: n.id,
      tool_slug: n.tool_slug || n.toolId,
      config: n.config || {},
      x: n.x, y: n.y,
    }));
    const edges = this.connections.map(c => ({ from: c.from, to: c.to }));
    return { nodes, edges, globals: this.globals || {} };
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
