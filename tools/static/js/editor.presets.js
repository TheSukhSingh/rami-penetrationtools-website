// editor.presets.js
export function attachPresets(editor) {
  // ——— Dialog helpers ———
  editor.askTitle = function () {
    const d = new Date();
    const def = `Workflow ${String(d.getHours()).padStart(2, "0")}:${String(
      d.getMinutes()
    ).padStart(2, "0")}`;
    return window.prompt("Preset title", this.currentWorkflow?.title || def);
  };

  // ——— Canvas helpers ———
  editor.clearCanvas = function () {
    document.querySelectorAll(".canvas-node").forEach((n) => n.remove());
    this.nodes = [];
    this.connections = [];
    this.selectedNode = null;
    this.updateConnections?.();
    this.validateWorkflow?.();
  };

  editor.rehydrateGraph = function (graph = {}) {
    this.clearCanvas();
    const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
    const edges = Array.isArray(graph.edges) ? graph.edges : [];

    nodes.forEach((n) => {

 const meta = this.tools.find((t) => t.tool_slug === n.tool_slug) ||
   this.tools.find((t) => t.id === n.tool_slug) || {

          id: n.tool_slug,
          tool_slug: n.tool_slug,
          name: n.tool_slug,
          type: "process",
          icon: (String(n.tool_slug || "T")[0] || "T").toUpperCase(),
          config: {},
        };

      const node = {
        id: n.id,
        toolId: meta.id,
        tool_slug: n.tool_slug,
        name: meta.name || n.tool_slug,
        type:
          meta.type ||
          this.inferNodeType?.(this.toolMetaBySlug[n.tool_slug] || {}),
        icon: meta.icon || (String(n.tool_slug || "T")[0] || "T").toUpperCase(),
        x: Number.isFinite(n.x) ? n.x : 20,
        y: Number.isFinite(n.y) ? n.y : 20,
        config: { ...(meta.config || {}), ...(n.config || {}) },
      };

      this.nodes.push(node);
      this.renderNode?.(node);
    });

    this.connections = edges.map((e) => ({ from: e.from, to: e.to }));
    this.updateConnections?.();
    this.validateWorkflow?.();
    this.addLog?.("Preset loaded onto canvas");
  };

  // ——— Node config save (used by view modal) ———
  editor.saveNodeConfig = function (nodeId) {
    const node = this.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const body = document.getElementById("modalBody");
    if (!body) return;

    body.querySelectorAll("input").forEach((input) => {
      const key = input.id;
      if (!key) return;
      if (input.type === "checkbox") node.config[key] = !!input.checked;
      else node.config[key] = input.value;
    });

    // Refresh node text
    const el = document.getElementById(node.id);
    const nb = el?.querySelector(".node-body");
    if (nb) nb.textContent = this.getNodeDescription?.(node);

    this.closeModal?.();
    this.addLog?.(`Saved config for ${node.name}`);
  };

  // ——— Save preset ———
  editor.savePreset = async function () {
    try {
      if ((this.nodes || []).length === 0) {
        this.addLog?.("Nothing to save — no nodes");
        return;
      }

      // Respect validation banner
      this.validateWorkflow?.();
      const banner = document.getElementById("warningBanner");
      if (banner && !banner.classList.contains("hidden")) {
        this.addLog?.("Fix validation errors before saving");
        return;
      }

      const graph = this.buildGraph?.();
      const title =
        this.currentWorkflow?.title || (this.askTitle ? this.askTitle() : "");
      if (!title) {
        this.addLog?.("Save cancelled");
        return;
      }

      let res;
      if (this.currentWorkflow?.id) {
        res = await this.API.workflows.update(this.currentWorkflow.id, {
          title,
          graph,
        });
      } else {
        res = await this.API.workflows.create({
          title,
          description: "",
          is_shared: false,
          graph,
        });
      }

      if (!res?.ok) throw new Error(res?.error?.message || "Failed to save");
      const wf =
        res.data?.workflow || res.data || res.workflow || res.item || res;
      this.currentWorkflow = wf;
      this.addLog?.(
        `Preset saved: ${String(wf.title || "Untitled")} (#${wf.id})`
      );
    } catch (e) {
      console.error(e);
      this.addLog?.(`Save error: ${e.message || e}`);
    }
  };

  // ——— Load preset ———
  editor.loadPreset = async function () {
    try {
      const res = await this.API.workflows.list();
      if (!res?.ok) throw new Error(res?.error?.message || "Failed to list");
      const list =
        res.data?.items ??
        res.items ??
        res.data?.workflows ??
        res.workflows ??
        (Array.isArray(res.data) ? res.data : []);

      if (!Array.isArray(list) || list.length === 0) {
        this.addLog?.("No presets found");
        return;
      }
      this.addLog?.(`Found ${list.length} presets`);

      const modal = document.getElementById("configModal");
      const title = document.getElementById("modalTitle");
      const body = document.getElementById("modalBody");
      if (!modal || !title || !body) return;

      title.textContent = "Load Preset";
      body.innerHTML = list
        .map(
          (w) => `
        <div class="preset-row" style="display:flex;align-items:center;gap:8px;justify-content:space-between;padding:6px 0;border-bottom:1px solid #2223;">
          <div class="preset-title">${(w.title || "Untitled")
            .toString()
            .slice(0, 120)}</div>
          <div>
            <button class="btn xs" data-load-id="${w.id}">Load</button>
          </div>
        </div>`
        )
        .join("");

    const card = modal.querySelector(':scope > .modal-card');
  if (card) {
    card.style.background   = 'var(--panel, #151515)';
    card.style.color        = 'var(--text, #fff)';
    card.style.minWidth     = '440px';
    card.style.maxWidth     = '800px';
    card.style.maxHeight    = '80vh';
    card.style.overflow     = 'auto';
    card.style.padding      = '12px 14px';
    card.style.borderRadius = '12px';
    card.style.boxShadow    = '0 10px 30px rgba(0,0,0,.35)';
  }
  body.style.color    = 'var(--text, #ddd)';
  body.style.display  = 'block';
      body.querySelectorAll("[data-load-id]").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
          const id = ev.currentTarget.getAttribute("data-load-id");
          try {
            const r = await this.API.workflows.get(id);
            if (!r?.ok) throw new Error(r?.error?.message || "Load failed");
            const wf = r.data?.workflow || r.data || r;
            const graph = wf.graph || wf.graph_json || wf.graph_dict || {};
            this.currentWorkflow = wf;
            this.rehydrateGraph?.(graph);
            this.closeModal?.();
            this.addLog?.(
              `Loaded preset: ${String(wf.title || "Untitled")} (#${wf.id})`
            );
          } catch (ex) {
            console.error(ex);
            this.addLog?.(`Load error: ${ex.message || ex}`);
          }
        });
      });

      modal.classList.remove("hidden");
      modal.style.display = "grid";
      modal.style.visibility = "visible";
      modal.style.opacity = "1";
      modal.style.zIndex = "9999";


    } catch (e) {
      console.error(e);
      this.addLog?.(`List error: ${e.message || e}`);
    }
  };
}
