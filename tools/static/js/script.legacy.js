// Reconnecting SSE with one silent refresh attempt via requesting.js
function connectRunSSE(runId, { onEvent, onError } = {}) {
  let es = null;
  let triedRefresh = false;

  const open = () => {
    es = new EventSource(`/tools/api/runs/${runId}/events`);
    // backend emits named events: "snapshot" and "update"
    es.addEventListener("snapshot", (e) => {
      try {
        onEvent && onEvent("snapshot", JSON.parse(e.data));
      } catch {}
    });
    es.addEventListener("update", (e) => {
      try {
        onEvent && onEvent("update", JSON.parse(e.data));
      } catch {}
    });
    es.onerror = async (e) => {
      try {
        es.close();
      } catch {}
      if (!triedRefresh) {
        triedRefresh = true;
        try {
          const r = await refreshTokens?.({ silent: true });
          if (r && r.ok) return open();
        } catch {}
      }
      onError && onError(e);
      // bubble a login-needed signal if your app listens for it
      window.dispatchEvent(
        new CustomEvent("auth:required", { detail: { url: location.pathname } })
      );
    };
  };

  open();
  return () => {
    try {
      es && es.close();
    } catch {}
  };
}

// --- Response shape normalizers ---------------------------------
function pickWorkflow(obj) {
  // Try common nests first
  if (obj?.workflow?.id) return obj.workflow;
  if (obj?.data?.workflow?.id) return obj.data.workflow;

  // Flat object with id is likely the workflow itself
  if (obj?.id) return obj;

  // Other common wrappers
  if (obj?.data?.id) return obj.data;
  if (obj?.item?.id) return obj.item;

  return null; // unknown shape
}

function pickWorkflowList(obj) {
  // Try typical lists
  if (Array.isArray(obj?.items)) return obj.items;
  if (Array.isArray(obj?.workflows)) return obj.workflows;
  if (Array.isArray(obj?.data)) return obj.data;

  // Sometimes APIs return {items:{data:[...]}} etc. Add more if needed
  return Array.isArray(obj) ? obj : [];
}

class WorkflowEditor {
  constructor() {
    this.tools = [];
    this.catalog = {};
    this.nodes = [];
    this.connections = [];
    this.selectedNode = null;
    this.draggedTool = null;
    this.draggedNode = null;
    this.connectionStart = null;
    this.nodeCounter = 0;
    this.API = {
      tools: () => getJSON("/tools/api/tools"),
      workflows: {
        list: () => getJSON("/tools/api/workflows"),
        get: (id) => getJSON(`/tools/api/workflows/${id}`),
        create: (payload) => postJSON("/tools/api/workflows", payload),
        update: (id, payload) => putJSON(`/tools/api/workflows/${id}`, payload),
        remove: (id) => delJSON(`/tools/api/workflows/${id}`),
        run: (id) => postJSON(`/tools/api/workflows/${id}/run`, {}), // body optional
      },
      scan: (payload) => postJSON("/tools/api/scan", payload),
    };
    this.globals = {};

    this.currentWorkflow = null; // { id, title, ... } after save/load
    this.currentRunId = null; // numeric id
    this.stopRunStream = null; // fn to close SSE

    window.addEventListener("resize", () => this.updateConnections());

    this.init();
  }

  init() {
    this.renderTools();
    this.loadCatalog().then(() => this.renderTools());
    this.setupEventListeners();
    this.addLog("Workflow editor initialized");
  }

  // Map backend tool meta to our node type
  inferNodeType(meta) {
    const t = (meta.type || "").toLowerCase();
    if (t === "start") return "start";
    if (t === "end" || t === "output" || t === "sink") return "end";
    return "process";
  }

  // Minimal, generic defaults every tool understands
  defaultConfigFor(meta) {
    return { input_method: "manual", value: "" };
  }
  // Turn canvas into the graph the backend expects
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

  // Simple UI helpers
  askTitle(defaultTitle = "My workflow") {
    return window.prompt("Preset title:", defaultTitle)?.trim();
  }
  setBusy(on) {
    document.body.classList.toggle("is-busy", !!on);
  }

  async loadCatalog() {
    try {
      const { ok, data } = await this.API.tools(); // GET /tools/api/tools
      if (!ok) throw new Error("catalog request not ok");
      this.catalog = data?.categories || {};

      // flatten to this.tools so existing renderTools() keeps working
      this.tools = [];
      Object.values(this.catalog).forEach((items) => {
        (items || []).forEach((it) => {
          this.tools.push({
            id: it.slug, // used by UI
            tool_slug: it.slug, // needed when we build the graph
            name: it.name || it.slug,
            type: this.inferNodeType(it),
            icon: (it.slug?.[0] || "T").toUpperCase(),
            config: this.defaultConfigFor(it),
          });
        });
      });
    } catch (e) {
      console.error(e);
      this.addLog("Error loading tool catalog");
    }
  }

  renderTools() {
    const toolsList = document.getElementById("toolsList");
    toolsList.innerHTML = "";

    this.tools.forEach((tool) => {
      const toolElement = document.createElement("div");
      toolElement.className = "tool-item";
      toolElement.draggable = true;
      toolElement.dataset.toolId = tool.id;

      toolElement.innerHTML = `
                <div class="tool-icon">${tool.icon}</div>
                <div class="tool-name">${tool.name}</div>
            `;

      toolElement.addEventListener("dragstart", (e) => {
        this.draggedTool = tool;
        toolElement.classList.add("dragging");
        e.dataTransfer.effectAllowed = "copy";
      });

      toolElement.addEventListener("dragend", () => {
        toolElement.classList.remove("dragging");
        this.draggedTool = null;
      });

      toolsList.appendChild(toolElement);
    });
  }

  setupEventListeners() {
    const canvasArea = document.getElementById("canvasArea");

    // Canvas drag and drop
    canvasArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer && (e.dataTransfer.dropEffect = "copy");

      canvasArea.classList.add("drag-over");
    });

    canvasArea.addEventListener("dragleave", () => {
      canvasArea.classList.remove("drag-over");
    });

    canvasArea.addEventListener("drop", (e) => {
      e.preventDefault();
      canvasArea.classList.remove("drag-over");

      if (this.draggedTool) {
        const rect = canvasArea.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        this.createNode(this.draggedTool, x, y);
      }
    });

    // Button event listeners
    document
      .getElementById("runBtn")
      .addEventListener("click", () => this.runWorkflow());
    document
      .getElementById("saveBtn")
      .addEventListener("click", () => this.savePreset());
    document
      .getElementById("loadBtn")
      .addEventListener("click", () => this.loadPreset());
    document
      .getElementById("globalConfigBtn")
      .addEventListener("click", () => this.showGlobalConfig());
    document
      .getElementById("modalClose")
      .addEventListener("click", () => this.closeModal());

    // Click outside to deselect
    canvasArea.addEventListener("click", (e) => {
      if (e.target === canvasArea) {
        this.deselectNode();
      }
    });

    document.addEventListener("keydown", (e) => {
      if ((e.key === "Delete" || e.key === "Backspace") && this.selectedNode) {
        this.addLog(`Deleted ${this.selectedNode.name}`);
        this.deleteNode(this.selectedNode.id);
        this.selectedNode = null;
      }
    });

    window.addEventListener("beforeunload", () => {
      try {
        this.stopRunStream?.();
      } catch {}
    });
  }

  createNode(tool, x, y) {
    const nodeId = `${tool.id}_${++this.nodeCounter}`;
    const node = {
      id: nodeId,
      toolId: tool.id,
      tool_slug: tool.tool_slug || tool.id,
      name: tool.name,
      type: tool.type,
      icon: tool.icon,
      x: x - 100,
      y: y - 40,
      config: { ...tool.config },
      connections: [],
    };

    this.nodes.push(node);
    this.renderNode(node);
    this.validateWorkflow();
    this.addLog(`Added ${tool.name} to canvas`);
  }

  renderNode(node) {
    const canvasArea = document.getElementById("canvasArea");
    const nodeElement = document.createElement("div");
    nodeElement.className = "canvas-node";
    nodeElement.id = node.id;
    nodeElement.style.left = `${node.x}px`;
    nodeElement.style.top = `${node.y}px`;

    nodeElement.innerHTML = `
            <div class="node-header">
                <div class="node-title">
                    <div class="tool-icon">${node.icon}</div>
                    ${node.name}
                </div>
                <div class="node-config" title="Configure">⚙️</div>
            </div>
            <div class="node-body">
                ${this.getNodeDescription(node)}
            </div>
            ${
              node.type !== "start"
                ? '<div class="connection-point input" data-type="input"></div>'
                : ""
            }
            ${
              node.type !== "end"
                ? '<div class="connection-point output" data-type="output"></div>'
                : ""
            }
        `;

    // Make node draggable
    nodeElement.addEventListener("mousedown", (e) => {
      if (e.target.classList.contains("connection-point")) return;
      if (e.target.classList.contains("node-config")) {
        this.showNodeConfig(node);
        return;
      }

      this.selectNode(node);
      this.startNodeDrag(e, node);
    });

    // Connection point events
    const connectionPoints = nodeElement.querySelectorAll(".connection-point");
    connectionPoints.forEach((point) => {
      point.addEventListener("click", (e) => {
        e.stopPropagation();
        this.handleConnectionClick(node, point.dataset.type);
      });
    });

    canvasArea.appendChild(nodeElement);
  }

  getNodeDescription(node) {
    const all = Object.values(this.catalog || {}).flat();
    const meta = all.find((m) => m.slug === node.tool_slug);
    const desc = meta?.desc || "Click gear to configure";
    // show a hint if the tool has a 'value'
    const v =
      node.config && node.config.value
        ? ` • value: ${String(node.config.value).slice(0, 60)}`
        : "";
    return desc + v;
  }

  deleteNode(nodeId) {
    // remove edges touching the node
    this.connections = this.connections.filter(
      (c) => c.from !== nodeId && c.to !== nodeId
    );
    // remove node
    this.nodes = this.nodes.filter((n) => n.id !== nodeId);
    // remove DOM
    document.getElementById(nodeId)?.remove();
    this.updateConnections();
    this.validateWorkflow();
  }

  selectNode(node) {
    this.deselectNode();
    this.selectedNode = node;
    document.getElementById(node.id).classList.add("selected");
  }

  deselectNode() {
    if (this.selectedNode) {
      const element = document.getElementById(this.selectedNode.id);
      if (element) element.classList.remove("selected");
      this.selectedNode = null;
    }
  }

  clampToCanvas(node) {
    const canvas = document.getElementById("canvasArea");
    const { width, height, left, top } = canvas.getBoundingClientRect();
    const maxX = width - 220; // ~node width
    const maxY = height - 80; // ~node height
    node.x = Math.max(0, Math.min(node.x, maxX));
    node.y = Math.max(0, Math.min(node.y, maxY));
  }

  startNodeDrag(e, node) {
    this.draggedNode = node;
    const nodeElement = document.getElementById(node.id);
    nodeElement.classList.add("dragging");
    const startX = e.clientX - node.x;
    const startY = e.clientY - node.y;

    const handleMouseMove = (e) => {
      node.x = e.clientX - startX;
      node.y = e.clientY - startY;
      this.clampToCanvas(node);
      nodeElement.style.left = `${node.x}px`;
      nodeElement.style.top = `${node.y}px`;
      this.updateConnections();
    };
    const handleMouseUp = () => {
      nodeElement.classList.remove("dragging");
      this.draggedNode = null;
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }

  handleConnectionClick(node, type) {
    if (type === "output") {
      if (this.connectionStart) {
        // Complete connection
        this.createConnection(this.connectionStart, node);
        this.connectionStart = null;
      } else {
        // Start connection
        this.connectionStart = node;
        this.addLog(`Starting connection from ${node.name}`);
      }
    } else if (type === "input" && this.connectionStart) {
      // Complete connection
      this.createConnection(this.connectionStart, node);
      this.connectionStart = null;
    }
  }

  createConnection(fromNode, toNode) {
    // Check if connection already exists
    if (fromNode.id === toNode.id) {
      this.addLog("Can't connect a node to itself");
      return;
    }
    if (this.pathWouldCreateCycle(fromNode.id, toNode.id)) {
      this.addLog("That would create a cycle; linear chains only");
      return;
    }

    const existingConnection = this.connections.find(
      (conn) => conn.from === fromNode.id && conn.to === toNode.id
    );

    if (existingConnection) {
      this.addLog("Connection already exists");
      return;
    }

    // Check if target node already has an input connection
    const existingInput = this.connections.find(
      (conn) => conn.to === toNode.id
    );
    if (existingInput) {
      this.addLog("Target node already has an input connection");
      return;
    }

    // Check if source node already has an output connection
    const existingOutput = this.connections.find(
      (conn) => conn.from === fromNode.id
    );
    if (existingOutput) {
      this.addLog("Source node already has an output connection");
      return;
    }

    const connection = {
      id: `conn_${Date.now()}`,
      from: fromNode.id,
      to: toNode.id,
    };

    this.connections.push(connection);
    this.updateConnections();
    this.validateWorkflow();
    this.addLog(`Connected ${fromNode.name} to ${toNode.name}`);
  }

  hasPath(startId, goalId) {
    const adj = {};
    this.connections.forEach((c) => (adj[c.from] ||= []).push(c.to));
    const seen = new Set([startId]);
    const q = [startId];
    while (q.length) {
      const v = q.shift();
      if (v === goalId) return true;
      (adj[v] || []).forEach((n) => {
        if (!seen.has(n)) {
          seen.add(n);
          q.push(n);
        }
      });
    }
    return false;
  }
  pathWouldCreateCycle(srcId, dstId) {
    return this.hasPath(dstId, srcId);
  }

  updateConnections() {
    const svg = document.getElementById("connectionsSvg");
    svg.innerHTML = "";

    this.connections.forEach((connection) => {
      const fromNode = this.nodes.find((n) => n.id === connection.from);
      const toNode = this.nodes.find((n) => n.id === connection.to);

      if (fromNode && toNode) {
        const fromX = fromNode.x + 200;
        const fromY = fromNode.y + 40;
        const toX = toNode.x;
        const toY = toNode.y + 40;

        const path = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "path"
        );
        const d = `M ${fromX} ${fromY} C ${fromX + 50} ${fromY} ${
          toX - 50
        } ${toY} ${toX} ${toY}`;
        path.setAttribute("d", d);
        svg.appendChild(path);
      }
    });
  }

  validateWorkflow() {
    const warnings = [];
    const ids = new Set(this.nodes.map((n) => n.id));
    const inDeg = {},
      outDeg = {};
    this.nodes.forEach((n) => ((inDeg[n.id] = 0), (outDeg[n.id] = 0)));
    this.connections.forEach((c) => {
      if (ids.has(c.from) && ids.has(c.to)) {
        outDeg[c.from]++;
        inDeg[c.to]++;
      }
    });

    const starts = this.nodes.filter((n) => inDeg[n.id] === 0);
    const ends = this.nodes.filter((n) => outDeg[n.id] === 0);
    if (starts.length !== 1)
      warnings.push("Workflow must have exactly one start (no incoming).");
    if (ends.length !== 1)
      warnings.push("Workflow must have exactly one end (no outgoing).");

    // middle nodes must have exactly 1 in / 1 out
    this.nodes.forEach((n) => {
      const indeg = inDeg[n.id],
        outdeg = outDeg[n.id];
      const ok =
        (indeg === 0 && outdeg === 1) ||
        (indeg === 1 && outdeg === 1) ||
        (indeg === 1 && outdeg === 0);
      if (!ok) warnings.push(`${n.name}: invalid degree (needs linear chain).`);
    });

    // reachability: from the start, visit all nodes
    if (starts[0]) {
      const adj = {};
      this.connections.forEach((c) => (adj[c.from] ||= []).push(c.to));
      const seen = new Set();
      const q = [starts[0].id];
      while (q.length) {
        const v = q.shift();
        if (seen.has(v)) continue;
        seen.add(v);
        (adj[v] || []).forEach((n) => q.push(n));
      }
      if (seen.size !== this.nodes.length)
        warnings.push("All nodes must form a single chain (no islands).");
    }

    // Show/hide warning banner
    const warningBanner = document.getElementById("warningBanner");
    const warningText = document.getElementById("warningText");

    if (warnings.length > 0) {
      warningText.textContent = warnings.join(" ");
      warningBanner.classList.remove("hidden");
    } else {
      warningBanner.classList.add("hidden");
    }
  }

  showNodeConfig(node) {
    const modal = document.getElementById("configModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");

    modalTitle.textContent = `Configure ${node.name}`;

    let formHTML = "";
    Object.keys(node.config).forEach((key) => {
      const value = node.config[key];
      const inputType = typeof value === "boolean" ? "checkbox" : "text";

      formHTML += `
                <div class="form-group">
                    <label class="form-label" for="${key}">${this.formatLabel(
        key
      )}</label>
                    ${
                      inputType === "checkbox"
                        ? `<input type="checkbox" id="${key}" ${
                            value ? "checked" : ""
                          }>`
                        : `<input type="text" class="form-input" id="${key}" value="${value}">`
                    }
                </div>
            `;
    });

    formHTML += `
            <div class="form-group" style="margin-top: 24px;">
                <button class="btn primary" onclick="workflowEditor.saveNodeConfig('${node.id}')">Save Configuration</button>
                <button class="btn" onclick="workflowEditor.closeModal()" style="margin-left: 8px;">Cancel</button>
            </div>
        `;

    modalBody.innerHTML = formHTML;
    modal.classList.remove("hidden");
  }

  saveNodeConfig(nodeId) {
    const node = this.nodes.find((n) => n.id === nodeId);
    if (!node) return;

    Object.keys(node.config).forEach((key) => {
      const input = document.getElementById(key);
      if (input) {
        if (input.type === "checkbox") {
          node.config[key] = input.checked;
        } else {
          node.config[key] = input.value;
        }
      }
    });

    // Update node description
    const nodeElement = document.getElementById(nodeId);
    const nodeBody = nodeElement.querySelector(".node-body");
    nodeBody.textContent = this.getNodeDescription(node);

    this.closeModal();
    this.addLog(`Updated configuration for ${node.name}`);
  }

  showGlobalConfig() {
    const modal = document.getElementById("configModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");

    modalTitle.textContent = "Global Configuration";

    let configHTML =
      '<h3 style="margin-bottom: 16px;">All Tool Parameters</h3>';

    this.nodes.forEach((node) => {
      configHTML += `
                <div style="margin-bottom: 24px; padding: 16px; background-color: var(--secondary); border-radius: var(--radius);">
                    <h4 style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                        <div class="tool-icon">${node.icon}</div>
                        ${node.name}
                    </h4>
            `;

      Object.keys(node.config).forEach((key) => {
        const value = node.config[key];
        configHTML += `
                    <div class="form-group">
                        <label class="form-label">${this.formatLabel(
                          key
                        )}</label>
                        <div style="font-size: 14px; color: var(--muted-foreground);">${value}</div>
                    </div>
                `;
      });

      configHTML += "</div>";
    });

    configHTML += `
            <div class="form-group" style="margin-top: 24px;">
                <button class="btn" onclick="workflowEditor.closeModal()">Close</button>
            </div>
        `;

    modalBody.innerHTML = configHTML;
    modal.classList.remove("hidden");
  }

  formatLabel(key) {
    return (
      key.charAt(0).toUpperCase() + key.slice(1).replace(/([A-Z])/g, " $1")
    );
  }

  closeModal() {
    document.getElementById("configModal").classList.add("hidden");
  }

  async runWorkflow() {
    try {
      if (this.nodes.length === 0) {
        this.addLog("No tools in workflow");
        return;
      }
      this.validateWorkflow();
      const warning = document.getElementById("warningBanner");
      if (!warning.classList.contains("hidden")) {
        this.addLog("Fix validation errors before running");
        return;
      }

      // Ensure we have a saved workflow id
      if (!this.currentWorkflow?.id) {
        this.addLog("Saving preset before run…");
        await this.savePreset();
        if (!this.currentWorkflow?.id) return; // save failed/cancelled
      }

      this.setBusy(true);

      // Start run
      const res = await this.API.workflows.run(this.currentWorkflow.id);
      if (!res.ok) throw new Error(res.error?.message || "Failed to start run");

      // Handle either {run: {...}} or {run_id: N} or {id: N}
      const runObj = res.data?.run || {};
      const runId = runObj.id ?? res.data?.run_id ?? res.data?.id;
      if (!runId) throw new Error("Run id missing from response");
      this.currentRunId = runId;

      this.addLog(`Run started (#${this.currentRunId})`);
      this.attachRunStream(this.currentRunId);
    } catch (e) {
      console.error(e);
      this.addLog(`Run error: ${e.message || e}`);
    } finally {
      this.setBusy(false);
    }
  }

  attachRunStream(runId) {
    // close previous stream
    if (this.stopRunStream) {
      try {
        this.stopRunStream();
      } catch (_) {}
    }
    this.stopRunStream = connectRunSSE(runId, {
      onEvent: (type, payload) => {
        if (type === "snapshot") {
          const run = payload.run;
          if (run) this.addLog(`Status: ${run.status} (${run.progress_pct}%)`);
        }
        if (type === "update") {
          if (payload.type === "step") {
            this.addLog(`Step ${payload.step_index}: ${payload.status}`);
          } else if (payload.type === "run") {
            this.addLog(`Run: ${payload.status} (${payload.progress_pct}%)`);
            if (["COMPLETED", "FAILED", "CANCELED"].includes(payload.status)) {
              this.renderRunSummary(runId);
            }
          }
        }
      },
      onError: (e) => {
        console.warn("SSE error", e);
        this.addLog(
          "Live updates disconnected; will continue with polling if needed."
        );
      },
    });
  }

  async renderRunSummary(runId) {
    try {
      const res = await getJSON(`/tools/api/runs/${runId}`);
      if (!res.ok) throw new Error(res.error?.message || "Failed to fetch run");

      const d = res.data || {};
      const run = d.run || d; // some APIs nest it
      const manifest = run.run_manifest || run.manifest || {};
      const counters = run.counters || manifest.counters || {};

      const out = document.getElementById("outputResults");
      if (!out) return;
      out.innerHTML = "";

      const header = document.createElement("div");
      header.className = "output-item";
      const countText = [
        ["domains", counters.domains],
        ["hosts", counters.hosts],
        ["ips", counters.ips],
        ["ports", counters.ports],
        ["urls", counters.urls],
        ["endpoints", counters.endpoints],
        ["findings", counters.findings],
      ]
        .filter(([, v]) => Number.isFinite(v))
        .map(([k, v]) => `${k}:${v}`)
        .join(" ");
      header.textContent = `Summary — ${countText || "no counters"}`;
      out.appendChild(header);

      const buckets = manifest.buckets || {};
      Object.entries(buckets).forEach(([k, v]) => {
        const items = v?.items || [];
        if (!items.length) return;
        const sec = document.createElement("div");
        sec.className = "output-item";
        const list = items
          .slice(0, 50)
          .map((x) => (typeof x === "string" ? x : JSON.stringify(x)));
        sec.innerHTML = `<strong>${k}</strong><br>${list.join("<br>")}${
          items.length > 50 ? "<br>…" : ""
        }`;
        out.appendChild(sec);
      });

      this.addLog("Summary loaded");
    } catch (e) {
      console.error(e);
      this.addLog(`Summary error: ${e.message || e}`);
    }
  }

  simulateWorkflowExecution() {
    const results = [];
    let currentNode = this.nodes.find((node) => node.type === "start");
    let step = 1;

    while (currentNode) {
      this.addLog(`Step ${step}: Executing ${currentNode.name}`);
      results.push({
        step: step,
        tool: currentNode.name,
        status: "completed",
        output: `Processed data through ${currentNode.name}`,
      });

      // Find next node
      const connection = this.connections.find(
        (conn) => conn.from === currentNode.id
      );
      if (connection) {
        currentNode = this.nodes.find((node) => node.id === connection.to);
        step++;
      } else {
        break;
      }
    }

    this.displayResults(results);
    this.updateStatus("Workflow completed successfully", "success");
    this.addLog("Workflow execution completed");
  }

  displayResults(results) {
    const outputResults = document.getElementById("outputResults");
    outputResults.innerHTML = "";

    results.forEach((result) => {
      const resultElement = document.createElement("div");
      resultElement.className = "output-item";
      resultElement.innerHTML = `
                <span class="status-indicator success"></span>
                Step ${result.step}: ${result.tool} - ${result.output}
            `;
      outputResults.appendChild(resultElement);
    });
  }

  updateStatus(message, type = "idle") {
    const statusSection = document.querySelector(
      ".output-section .output-item"
    );
    statusSection.innerHTML = `
            <span class="status-indicator ${type}"></span>
            ${message}
        `;
  }

  addLog(message) {
    const wrap = document.getElementById("outputLogs");
    if (!wrap) {
      // Optional: buffer logs and flush later
      console.debug("[WorkflowEditor] #outputLogs not ready yet:", message);
      return;
    }
    const row = document.createElement("div");
    row.className = "output-item";
    row.innerHTML = `
    <span class="status-indicator idle"></span>
    ${new Date().toLocaleTimeString()}: ${message}
  `;
    wrap.appendChild(row);
  }

  async savePreset() {
    try {
      if (this.nodes.length === 0) {
        this.addLog("Nothing to save — no nodes");
        return;
      }
      // Validate before save
      this.validateWorkflow();
      const warning = document.getElementById("warningBanner");
      if (!warning.classList.contains("hidden")) {
        this.addLog("Fix validation errors before saving");
        return;
      }

      this.setBusy(true);
      const graph = this.buildGraph();

      // Create or update
      if (!this.currentWorkflow?.id) {
        const title = this.askTitle();
        if (!title) {
          this.addLog("Save cancelled");
          return;
        }
        const { ok, data, error } = await this.API.workflows.create({
          title,
          description: "",
          is_shared: false,
          graph,
        });
        if (!ok) throw new Error(error?.message || "Failed to create workflow");
        const wfCreated = pickWorkflow(data);
        if (!wfCreated?.id)
          throw new Error("Create workflow: missing id in response");
        this.currentWorkflow = wfCreated;

        this.addLog(
          `Preset created: ${this.currentWorkflow?.title} (#${this.currentWorkflow?.id})`
        );
      } else {
        const { ok, data, error } = await this.API.workflows.update(
          this.currentWorkflow.id,
          { graph }
        );
        if (!ok) throw new Error(error?.message || "Failed to update workflow");
        const wfUpdated = pickWorkflow(data);
        this.currentWorkflow = wfUpdated || this.currentWorkflow;

        this.addLog(`Preset updated: #${this.currentWorkflow?.id}`);
      }
    } catch (e) {
      console.error(e);
      this.addLog(`Save error: ${e.message || e}`);
    } finally {
      this.setBusy(false);
    }
  }

  async loadPreset() {
    try {
      this.setBusy(true);
      // list mine + shared
      const { ok, data, error } = await this.API.workflows.list();
      if (!ok) throw new Error(error?.message || "Failed to list presets");
      const items = pickWorkflowList(data);

      if (!items.length) {
        this.addLog("No presets found");
        return;
      }

      // very simple picker (id list prompt)
      const choices = items
        .map((w) => `#${w.id} — ${w.title || "(untitled)"}`)
        .join("\n");
      const pick = window.prompt(
        `Enter preset id to load:\n${choices}\n\nPreset id:`
      );
      const id = parseInt((pick || "").trim(), 10);
      if (!id) {
        this.addLog("Load cancelled");
        return;
      }

      const res = await this.API.workflows.get(id);
      if (!res.ok)
        throw new Error(res.error?.message || "Failed to load preset");
      const wf = pickWorkflow(res.data);

      const graph = wf?.graph_json || wf?.graph || {};

      // reset canvas
      this.nodes = [];
      this.connections = [];
      const nodeById = {};

      // re-create nodes
      (graph.nodes || []).forEach((n, idx) => {
        const tool = this.tools.find(
          (t) => t.tool_slug === n.tool_slug || t.id === n.tool_slug
        ) || {
          id: n.tool_slug,
          tool_slug: n.tool_slug,
          name: n.tool_slug,
          type: "process",
          icon: "T",
          config: {},
        };
        const x = Number.isFinite(n.x) ? n.x : 100 + idx * 180;
        const y = Number.isFinite(n.y) ? n.y : 100;
        this.createNode(tool, x, y);
        // sync config/id to created node
        const created = this.nodes[this.nodes.length - 1];
        created.id = n.id; // keep original ids
        created.config = n.config || {};
        document.getElementById(created.id)?.setAttribute("id", created.id);
        nodeById[created.id] = created;
      });

      // re-create edges
      (graph.edges || []).forEach((e) => {
        this.connections.push({ from: e.from, to: e.to });
      });

      this.updateConnections();
      this.validateWorkflow();

      this.currentWorkflow = wf;
      this.addLog(`Preset loaded: ${wf.title || "(untitled)"} (#${wf.id})`);
    } catch (e) {
      console.error(e);
      this.addLog(`Load error: ${e.message || e}`);
    } finally {
      this.setBusy(false);
    }
  }
}

// Initialize the workflow editor
const workflowEditor = new WorkflowEditor();
