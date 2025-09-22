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

    this.currentWorkflow = null; // { id, title, ... } after save/load
    this.currentRunId = null; // numeric id
    this.stopRunStream = null; // fn to close SSE

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
      tool_slug: n.tool_slug || n.toolId, // we stored tool_slug when creating nodes
      config: n.config || {},
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

  // Log to the right container
  addLog(message) {
    const wrap = document.getElementById("outputLogs");
    if (!wrap) return;
    const row = document.createElement("div");
    row.className = "output-item";
    row.innerHTML = `
    <span class="status-indicator idle"></span>
    ${new Date().toLocaleTimeString()}: ${message}
  `;
    wrap.appendChild(row);
    wrap.scrollTop = wrap.scrollHeight;
  }

  async loadCatalog() {
    try {
      const { ok, data } = await ToolsAPI.get("/tools"); // GET /tools/api/tools
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
    ToolsAPI.get("/tools")
      .then(({ ok, data }) => console.log("catalog ✓", ok, data))
      .catch((e) => console.error("catalog ✗", e));

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
    const config = node.config;
    switch (node.toolId) {
      case "input":
        return `Source: ${config.source}`;
      case "filter":
        return `Filter by: ${config.field || "field"}`;
      case "transform":
        return `Operation: ${config.operation}`;
      case "output":
        return `Destination: ${config.destination}`;
      default:
        return "Click gear to configure";
    }
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

  startNodeDrag(e, node) {
    this.draggedNode = node;
    const nodeElement = document.getElementById(node.id);
    nodeElement.classList.add("dragging");

    const startX = e.clientX - node.x;
    const startY = e.clientY - node.y;

    const handleMouseMove = (e) => {
      node.x = e.clientX - startX;
      node.y = e.clientY - startY;
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

    // Check for multiple start nodes
    const startNodes = this.nodes.filter((node) => node.type === "start");
    if (startNodes.length > 1) {
      warnings.push(
        "Multiple starting tools detected. Only one start tool is allowed."
      );
    }

    // Check for multiple end nodes
    const endNodes = this.nodes.filter((node) => node.type === "end");
    if (endNodes.length > 1) {
      warnings.push(
        "Multiple output tools detected. Only one output tool is allowed."
      );
    }

    // Update node styles based on validation
    this.nodes.forEach((node) => {
      const element = document.getElementById(node.id);
      if (element) {
        element.classList.remove("error");
        if (
          (node.type === "start" && startNodes.length > 1) ||
          (node.type === "end" && endNodes.length > 1)
        ) {
          element.classList.add("error");
        }
      }
    });

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
      const res = await ToolsAPI.post(
        `/workflows/${this.currentWorkflow.id}/run`,
        {}
      );
      if (!res.ok) throw new Error(res.error?.message || "Failed to start run");
      const run = res.data?.run;
      this.currentRunId = run?.id;
      this.addLog(`Run started (#${this.currentRunId})`);

      // Attach SSE
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
    if (this.stopRunStream)
      try {
        this.stopRunStream();
      } catch (_) {}
    const stop = sse(`/tools/api/runs/${runId}/events`, {
      onEvent: (type, payload) => {
        if (type === "snapshot") {
          const run = payload.run;
          this.addLog(`Status: ${run.status} (${run.progress_pct}%)`);
        }
        if (type === "update") {
          if (payload.type === "step") {
            this.addLog(`Step ${payload.step_index}: ${payload.status}`);
          } else if (payload.type === "run") {
            this.addLog(`Run: ${payload.status} (${payload.progress_pct}%)`);
            // when finished, fetch summary
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
    this.stopRunStream = stop;
  }

  async renderRunSummary(runId) {
    try {
      const res = await ToolsAPI.get(`/runs/${runId}/summary`);
      if (!res.ok)
        throw new Error(res.error?.message || "Failed to fetch summary");
      const { counters, manifest } = res.data || {};
      const out = document.getElementById("outputResults");
      if (!out) return;
      out.innerHTML = ""; // clear

      // Top counters
      const header = document.createElement("div");
      header.className = "output-item";
      header.textContent = `Summary — domains:${counters.domains} hosts:${counters.hosts} urls:${counters.urls} findings:${counters.findings}`;
      out.appendChild(header);

      // Bucket lists (limit 50 to keep UI snappy)
      Object.entries(manifest.buckets || {}).forEach(([k, v]) => {
        if (!v?.items?.length) return;
        const sec = document.createElement("div");
        sec.className = "output-item";
        const list = v.items
          .slice(0, 50)
          .map((x) => (typeof x === "string" ? x : JSON.stringify(x)));
        sec.innerHTML = `<strong>${k}</strong><br>${list.join("<br>")}${
          v.items.length > 50 ? "<br>…" : ""
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
        const { ok, data, error } = await ToolsAPI.post("/workflows", {
          title,
          description: "",
          is_shared: false,
          graph,
        });
        if (!ok) throw new Error(error?.message || "Failed to create workflow");
        this.currentWorkflow = data?.workflow || null;
        this.addLog(
          `Preset created: ${this.currentWorkflow?.title} (#${this.currentWorkflow?.id})`
        );
      } else {
        const { ok, data, error } = await ToolsAPI.put(
          `/workflows/${this.currentWorkflow.id}`,
          {
            graph,
          }
        );
        if (!ok) throw new Error(error?.message || "Failed to update workflow");
        this.currentWorkflow = data?.workflow || this.currentWorkflow;
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
      const { ok, data, error } = await ToolsAPI.get(
        "/workflows?mine=true&shared=true&page=1&per_page=50"
      );
      if (!ok) throw new Error(error?.message || "Failed to list presets");
      const items = data?.items || [];
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

      const res = await ToolsAPI.get(`/workflows/${id}`);
      if (!res.ok)
        throw new Error(res.error?.message || "Failed to load preset");
      const wf = res.data?.workflow;
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
        const x = 100 + idx * 180,
          y = 100;
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
