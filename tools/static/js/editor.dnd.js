// Drag-drop to canvas, node dragging, connections, buttons & SSE glue
export function attachDnD(editor) {
  editor.clampToCanvas = function (node) {
    const canvas = document.getElementById("canvasArea");
    const { width, height } = canvas.getBoundingClientRect();
    const maxX = width - 220,
      maxY = height - 80;
    node.x = Math.max(0, Math.min(node.x, maxX));
    node.y = Math.max(0, Math.min(node.y, maxY));
  };

  editor.createNode = function (tool, x, y) {
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
    this.clampToCanvas(node);
    this.nodes.push(node);
    this.renderNode(node);
    this.validateWorkflow?.();
    this.addLog(`Added ${tool.name} to canvas`);
  };

  editor.renderNode = function (node) {
    const canvasArea = document.getElementById("canvasArea");
    const el = document.createElement("div");
    el.className = "canvas-node";
    el.id = node.id;
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;
    el.innerHTML = `
      <div class="node-header">
        <div class="node-title">
          <div class="tool-icon">${node.icon}</div>${node.name}
        </div>
        <div class="node-config" title="Configure">⚙️</div>
      </div>
      <div class="node-body">${this.getNodeDescription(node)}</div>
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
    el.addEventListener("mousedown", (e) => {
      if (e.target.classList.contains("connection-point")) return;
      if (e.target.classList.contains("node-config")) {
        this.showNodeConfig(node);
        return;
      }
      this.selectNode(node);
      this.startNodeDrag(e, node);
    });
    el.querySelectorAll(".connection-point").forEach((pt) => {
      pt.addEventListener("click", (e) => {
        e.stopPropagation();
        this.handleConnectionClick(node, pt.dataset.type);
      });
    });
    canvasArea.appendChild(el);
  };

  editor.selectNode = function (node) {
    this.deselectNode();
    this.selectedNode = node;
    document.getElementById(node.id)?.classList.add("selected");
  };
  editor.deselectNode = function () {
    if (this.selectedNode) {
      const el = document.getElementById(this.selectedNode.id);
      if (el) el.classList.remove("selected");
      this.selectedNode = null;
    }
  };

  editor.startNodeDrag = function (e, node) {
    this.draggedNode = node;
    const el = document.getElementById(node.id);
    el.classList.add("dragging");
    const startX = e.clientX - node.x,
      startY = e.clientY - node.y;
    const onMove = (ev) => {
      node.x = ev.clientX - startX;
      node.y = ev.clientY - startY;
      this.clampToCanvas(node);
      el.style.left = `${node.x}px`;
      el.style.top = `${node.y}px`;
      this.updateConnections();
    };
    const onUp = () => {
      el.classList.remove("dragging");
      this.draggedNode = null;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  };

  editor.handleConnectionClick = function (node, type) {
    if (type === "output") {
      if (this.connectionStart) {
        this.createConnection(this.connectionStart, node);
        this.connectionStart = null;
      } else {
        this.connectionStart = node;
        this.addLog(`Starting connection from ${node.name}`);
      }
    } else if (type === "input" && this.connectionStart) {
      this.createConnection(this.connectionStart, node);
      this.connectionStart = null;
    }
  };

  editor.createConnection = function (fromNode, toNode) {
    if (fromNode.id === toNode.id) {
      this.addLog("Can't connect a node to itself");
      return;
    }
    if (this.pathWouldCreateCycle?.(fromNode.id, toNode.id)) {
      this.addLog("That would create a cycle; linear chains only");
      return;
    }
    if (
      this.connections.find((c) => c.from === fromNode.id && c.to === toNode.id)
    ) {
      this.addLog("Connection already exists");
      return;
    }
    if (this.connections.find((c) => c.to === toNode.id)) {
      this.addLog("Target node already has an input connection");
      return;
    }
    if (this.connections.find((c) => c.from === fromNode.id)) {
      this.addLog("Source node already has an output connection");
      return;
    }
    this.connections.push({
      id: `conn_${Date.now()}`,
      from: fromNode.id,
      to: toNode.id,
    });
    this.updateConnections();
    this.validateWorkflow?.();
    this.addLog(`Connected ${fromNode.name} to ${toNode.name}`);
  };

  editor.updateConnections = function () {
    const svg = document.getElementById("connectionsSvg");
    svg.innerHTML = "";

    this.connections.forEach((connection, idx) => {
      const from = this.nodes.find((n) => n.id === connection.from);
      const to = this.nodes.find((n) => n.id === connection.to);
      if (!from || !to) return;

      const fromEl = document.getElementById(from.id);
      const toEl = document.getElementById(to.id);
      const fromW = fromEl ? fromEl.offsetWidth : 200;
      const toW = toEl ? toEl.offsetWidth : 200; // not used here but handy if you want right-side padding

      const fromX = from.x + fromW;
      const fromY = from.y + 40;
      const toX = to.x;
      const toY = to.y + 40;

      const path = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "path"
      );
      const d = `M ${fromX} ${fromY} C ${fromX + 50} ${fromY} ${
        toX - 50
      } ${toY} ${toX} ${toY}`;
      path.setAttribute("d", d);
      path.classList.add("conn-path");
      path.dataset.connIndex = String(idx);
      svg.appendChild(path);
    });
  };

  editor.setupEventListeners = function () {
    const canvas = document.getElementById("canvasArea");

    const svg = document.getElementById("connectionsSvg");

    // Edge delete mode: toggle pointer events only when needed
    this.edgeDeleteMode = false;
    const setEdgeDeleteMode = (on) => {
      this.edgeDeleteMode = !!on;
      // override the inline pointer-events from index.html
      svg.style.pointerEvents = on ? "auto" : "none";
      svg.classList.toggle("edge-delete-mode", !!on);
      this.addLog(
        on
          ? "Edge delete mode ON (click a line to remove)"
          : "Edge delete mode OFF"
      );
    };

    // start OFF
    setEdgeDeleteMode(false);

    // keyboard toggle: press "E"
    document.addEventListener("keydown", (e) => {
      if (e.key.toLowerCase() === "e" && !e.repeat) {
        setEdgeDeleteMode(!this.edgeDeleteMode);
      }
    });

    // any canvas interaction disables edge-delete mode
    canvas.addEventListener("mousedown", () => setEdgeDeleteMode(false));

    // existing: click on a path to delete
    svg.addEventListener("click", (e) => {
      const target = e.target;
      if (!(target instanceof SVGPathElement)) return;
      if (!target.classList.contains("conn-path")) return;
      const idx = Number(target.dataset.connIndex);
      if (!Number.isFinite(idx)) return;

      const removed = this.connections.splice(idx, 1)[0];
      this.updateConnections();
      this.validateWorkflow?.();
      this.addLog(`Removed connection ${removed?.from} → ${removed?.to}`);
    });

    document.getElementById("clearBtn")?.addEventListener("click", () => {
      // remove node DOMs
      document.querySelectorAll(".canvas-node").forEach((n) => n.remove());
      // reset state
      this.nodes = [];
      this.connections = [];
      this.selectedNode = null;
      this.updateConnections();
      this.validateWorkflow?.();
      this.addLog("Canvas cleared");
    });

    canvas.addEventListener("dragover", (e) => {
      e.preventDefault();
      canvas.classList.add("drag-over");
      e.dataTransfer && (e.dataTransfer.dropEffect = "copy");
    });
    canvas.addEventListener("dragleave", () =>
      canvas.classList.remove("drag-over")
    );
    canvas.addEventListener("drop", (e) => {
      e.preventDefault();
      canvas.classList.remove("drag-over");
      if (this.draggedTool) {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left,
          y = e.clientY - rect.top;
        this.createNode(this.draggedTool, x, y);
      }
    });
    canvas.addEventListener("click", (e) => {
      if (e.target === canvas) this.deselectNode();
    });
    window.addEventListener("resize", () => this.updateConnections());

    document
      .getElementById("runBtn")
      ?.addEventListener("click", () => this.runWorkflow?.());
    document
      .getElementById("saveBtn")
      ?.addEventListener("click", () => this.savePreset?.());
    document
      .getElementById("loadBtn")
      ?.addEventListener("click", () => this.loadPreset?.());
    document
      .getElementById("globalConfigBtn")
      ?.addEventListener("click", () => this.showGlobalConfig?.());
    document
      .getElementById("modalClose")
      ?.addEventListener("click", () => this.closeModal?.());

    document.addEventListener("keydown", (e) => {
      if ((e.key === "Delete" || e.key === "Backspace") && this.selectedNode) {
        this.addLog(`Deleted ${this.selectedNode.name}`);
        const id = this.selectedNode.id;
        this.connections = this.connections.filter(
          (c) => c.from !== id && c.to !== id
        );
        this.nodes = this.nodes.filter((n) => n.id !== id);
        document.getElementById(id)?.remove();
        this.updateConnections();
        this.validateWorkflow?.();
        this.selectedNode = null;
      }
    });
  };

  // Run + SSE glue (uses API + connectRunSSE)
  editor.attachRunStream = function (runId) {
    if (this.stopRunStream) {
      try {
        this.stopRunStream();
      } catch {}
    }
    this.stopRunStream = this.connectRunSSE(runId, {
      onEvent: (type, payload) => {
        if (type === "snapshot" && payload.run)
          this.addLog(
            `Status: ${payload.run.status} (${payload.run.progress_pct}%)`
          );
        if (type === "update") {
          if (payload.type === "step")
            this.addLog(`Step ${payload.step_index}: ${payload.status}`);
          if (payload.type === "run") {
            this.addLog(`Run: ${payload.status} (${payload.progress_pct}%)`);
            if (["COMPLETED", "FAILED", "CANCELED"].includes(payload.status)) {
              this.renderRunSummary?.(runId);
              try {
                this.stopRunStream?.();
              } catch {}
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
  };
}
