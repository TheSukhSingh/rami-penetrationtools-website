// tools/static/js/editor.presets.js
// Preset management: save/load/rename/duplicate/archive + global config editor
export function attachPresets(editor) {
editor.markClean = function () {
  this.isDirty = false;
  this.dirtyAt = null;
  const btn = document.getElementById("saveBtn");
  if (btn) { btn.classList.remove("dirty"); btn.textContent = "Save Preset"; }
  this.addLog?.("Preset state is clean");
};
editor.markDirty = function () {
  this.isDirty = true;
  this.dirtyAt = Date.now();
  const btn = document.getElementById("saveBtn");
  if (btn && !btn.classList.contains("dirty")) {
    btn.classList.add("dirty");
    btn.textContent = "Save Preset *";
  }
};
  // --- Save (create or update) -----------------------------------------------
  editor.savePreset = async function () {
    try {
      const graph = this.buildGraph?.() || {
        nodes: [],
        edges: [],
        globals: {},
      };

      // Update existing
      if (this.currentWorkflow?.id) {
        const res = await this.API.workflows.update(this.currentWorkflow.id, {
          title: this.currentWorkflow.title ?? "Untitled Workflow",
          graph,
        });
        if (!res?.ok)
          throw new Error(res?.error?.message || "Failed to save preset");
        this.currentWorkflow =
          res.data?.workflow || res.data || this.currentWorkflow;
        this.addLog?.("Preset saved");
        this.markClean();
        return this.currentWorkflow;
      }

      // Create new
      const title =
        prompt("Preset name", "Untitled Workflow") || "Untitled Workflow";
      const res = await this.API.workflows.create({ title, graph });
      if (!res?.ok)
        throw new Error(res?.error?.message || "Failed to create preset");
      this.currentWorkflow = res.data?.workflow || res.data || res;
      this.addLog?.(
        `Preset created: ${
          this.currentWorkflow.title || this.currentWorkflow.id
        }`
      );
      this.markClean();
      return this.currentWorkflow;
    } catch (e) {
      console.error(e);
      this.addLog?.(`Save error: ${e.message || e}`);
      alert(`Save failed: ${e.message || e}`);
      throw e;
    }
  };

  // --- Load modal ------------------------------------------------------------
  editor.loadPreset = async function () {
    if (this.isBusy) return;

    // Optional unsaved guard
    if (this.isDirty) {
      const ok = confirm(
        "You have unsaved changes. Load another preset anyway?"
      );
      if (!ok) return;
    }

    try {
      const res = await this.API.workflows.list();
      if (!res?.ok)
        throw new Error(res?.error?.message || "Failed to fetch presets");
      const list = normalizeList(res.data);

      const wrap = document.createElement("div");
      wrap.className = "presets-modal";
      wrap.innerHTML = `
        <div class="presets-toolbar">
          <input type="search" class="input" id="presetSearch" placeholder="Search presets…" aria-label="Search presets"/>
          <button class="btn xs" id="newPresetBtn">New</button>
        </div>
        <div class="presets-list" id="presetsList"></div>
        <div class="muted" id="presetsEmpty" style="display:none">No presets found.</div>
      `;

      const listEl = wrap.querySelector("#presetsList");
      const emptyEl = wrap.querySelector("#presetsEmpty");
      const searchEl = wrap.querySelector("#presetSearch");
      const newBtn = wrap.querySelector("#newPresetBtn");

      const render = (q = "") => {
        const ql = q.trim().toLowerCase();
        listEl.innerHTML = "";
        let shown = 0;
        list
          .filter((it) => !ql || (it.title || "").toLowerCase().includes(ql))
          .sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0))
          .forEach((it) => {
            const div = document.createElement("div");
            div.className = "preset-row";
            div.innerHTML = `
              <div class="preset-main">
                <div class="preset-title" title="${escapeHtml(
                  it.title || ""
                )}">${escapeHtml(it.title || "Untitled")}</div>
                <div class="preset-meta">
                  <span>#${it.id}</span>
                  <span>·</span>
                  <span>${fmtDate(it.updated_at) || "—"}</span>
                  <span>·</span>
                  <span>${it.step_count ?? "?"} steps</span>
                </div>
              </div>
              <div class="preset-actions">
                <button class="btn xs" data-act="load">Load</button>
                <button class="btn xs" data-act="rename">Rename</button>
                <button class="btn xs" data-act="duplicate">Duplicate</button>
                <button class="btn xs danger" data-act="delete">Delete</button>
              </div>
            `;
            div
              .querySelector('[data-act="load"]')
              .addEventListener("click", () => this._loadPresetById(it.id));
            div
              .querySelector('[data-act="rename"]')
              .addEventListener("click", async () => {
                const newTitle = prompt("New title", it.title || "Untitled");
                if (!newTitle) return;
                await this._renamePreset(it.id, newTitle);
                this.loadPreset(); // refresh modal
              });
            div
              .querySelector('[data-act="duplicate"]')
              .addEventListener("click", async () => {
                await this._duplicatePreset(it.id);
                this.loadPreset(); // refresh modal
              });
            div
              .querySelector('[data-act="delete"]')
              .addEventListener("click", async () => {
                const ok = confirm(`Delete preset "${it.title || it.id}"?`);
                if (!ok) return;
                await this._deleteOrArchivePreset(it.id);
                this.loadPreset(); // refresh modal
              });

            listEl.appendChild(div);
            shown++;
          });

        emptyEl.style.display = shown ? "none" : "block";
      };

      searchEl.addEventListener("input", () => render(searchEl.value));
      newBtn.addEventListener("click", async () => {
        await this.savePreset?.();
        this.closeModal?.();
      });

      render();

      // Open modal
      this.openModal?.("Load Preset", wrap);
    } catch (e) {
      console.error(e);
      this.addLog?.(`Load list error: ${e.message || e}`);
      alert(`Failed to open presets: ${e.message || e}`);
    }
  };

  editor._loadPresetById = async function (id) {
    try {
      const res = await this.API.workflows.get(id);
      if (!res?.ok)
        throw new Error(res?.error?.message || "Failed to fetch preset");
      const wf = normalizeWorkflow(res.data);
      await this._hydrateFromWorkflow(wf);
      this.closeModal?.();
      this.addLog?.(`Loaded preset: ${wf.title || wf.id}`);
    } catch (e) {
      console.error(e);
      alert(`Load failed: ${e.message || e}`);
    }
  };

  // --- Hydration: paint canvas from workflow ---------------------------------
  editor._hydrateFromWorkflow = async function (wf) {
    if (!this.toolMetaBySlug || !Object.keys(this.toolMetaBySlug).length) {
      try {
        await this.loadCatalog?.();
      } catch {}
    }
    // Clear canvas DOM
    document.querySelectorAll(".canvas-node").forEach((n) => n.remove());
    // Reset state
    this.nodes = [];
    this.connections = [];
    this.selectedNode = null;

    // adopt globals + currentWorkflow
    const graph = wf.graph || {};
    this.currentWorkflow = wf;
    this.globals = graph.globals || wf.globals || {};

    // Nodes
    const nodes = graph.nodes || wf.nodes || [];
    nodes.forEach((n) => {
      const meta = this.toolMetaBySlug?.[n.tool_slug] || {};
      const node = {
        id: n.id,
        toolId: n.tool_slug,
        tool_slug: n.tool_slug,
        name: meta.name || n.tool_slug,
        type: this.inferNodeType?.(meta) || "process",
        icon: (meta.slug?.[0] || n.tool_slug?.[0] || "T").toUpperCase(),
        x: Number.isFinite(n.x) ? n.x : 40,
        y: Number.isFinite(n.y) ? n.y : 40,
        config: n.config || {},
        connections: [],
      };
      this.nodes.push(node);
      this.renderNode?.(node);
    });

    // Edges
    const edges = graph.edges || wf.edges || [];
    this.connections = edges.map((e) => ({
      id: `conn_${e.from}_${e.to}`,
      from: e.from,
      to: e.to,
    }));
    this.updateConnections?.();

    // Validate & mark clean
    this.validateWorkflow?.();
    this.markClean();
    this._checkInFlightForWorkflow?.(this.currentWorkflow?.id);
  };

  // --- Global Config ----------------------------------------------------------
  editor.showGlobalConfig = function () {
    const wrap = document.createElement("div");
    wrap.className = "globals-modal";
    wrap.innerHTML = `
      <div class="form-row">
        <div class="muted">Edit global key/value pairs that apply to all steps (timeouts, caps, etc.).</div>
      </div>
      <div id="globalsRows"></div>
      <div class="form-row" style="margin-top:8px">
        <button class="btn xs" id="addGlobal">Add Row</button>
      </div>
      <div class="modal-actions" style="margin-top:12px">
        <button class="btn primary" id="globalsSave">Save</button>
        <button class="btn" id="globalsCancel">Cancel</button>
      </div>
    `;

    const rowsEl = wrap.querySelector("#globalsRows");
    const addRowBtn = wrap.querySelector("#addGlobal");
    const saveBtn = wrap.querySelector("#globalsSave");
    const cancelBtn = wrap.querySelector("#globalsCancel");

    const drawRows = () => {
      rowsEl.innerHTML = "";
      const entries = Object.entries(this.globals || {});
      if (!entries.length) {
        const m = document.createElement("div");
        m.className = "muted";
        m.textContent = "No globals yet.";
        rowsEl.appendChild(m);
      }
      entries.forEach(([k, v]) => rowsEl.appendChild(row(k, v)));
    };

    const row = (k = "", v = "") => {
      const r = document.createElement("div");
      r.className = "form-row";
      r.innerHTML = `
        <input class="input" type="text" placeholder="key" value="${escapeHtml(
          k
        )}" style="width:40%">
        <input class="input" type="text" placeholder="value" value="${escapeHtml(
          String(v)
        )}" style="width:50%; margin-left:8px">
        <button class="btn xs danger" style="margin-left:8px">Remove</button>
      `;
      const [kEl, vEl, rm] = r.querySelectorAll("input,button");
      rm.addEventListener("click", () => r.remove());
      return r;
    };

    addRowBtn.addEventListener("click", () => {
      rowsEl.appendChild(row());
    });

    saveBtn.addEventListener("click", async () => {
      const kv = {};
      rowsEl.querySelectorAll(".form-row").forEach((fr) => {
        const inputs = fr.querySelectorAll("input");
        if (inputs.length >= 2) {
          const k = inputs[0].value.trim();
          const v = inputs[1].value.trim();
          if (k) kv[k] = v;
        }
      });
      this.globals = kv;
      this.addLog?.(`Globals set (${Object.keys(kv).length})`);

      // persist to workflow if exists
      if (this.currentWorkflow?.id) {
        try {
          const graph = this.buildGraph?.();
          const res = await this.API.workflows.update(this.currentWorkflow.id, {
            title: this.currentWorkflow.title ?? "Untitled Workflow",
            graph,
          });
          if (!res?.ok)
            throw new Error(res?.error?.message || "Failed to save globals");
          this.addLog?.("Globals saved to preset");
          this.markClean();
        } catch (e) {
          console.error(e);
          alert(`Failed to save globals: ${e.message || e}`);
        }
      }
      this.closeModal?.();
    });

    cancelBtn.addEventListener("click", () => this.closeModal?.());

    drawRows();
    this.openModal?.("Global Config", wrap);
  };

  // --- Item actions -----------------------------------------------------------
  editor._renamePreset = async function (id, newTitle) {
    const res = await this.API.workflows.update(id, { title: newTitle });
    if (!res?.ok) throw new Error(res?.error?.message || "Rename failed");
    this.addLog?.("Preset renamed");
  };

  editor._duplicatePreset = async function (id) {
    // Fetch source wf and create new with same graph
    const g = await this.API.workflows.get(id);
    if (!g?.ok) throw new Error(g?.error?.message || "Failed to fetch source");
    const wf = normalizeWorkflow(g.data);
    const title = `Copy of ${wf.title || wf.id}`;
    const res = await this.API.workflows.create({
      title,
      graph: wf.graph || {
        nodes: wf.nodes || [],
        edges: wf.edges || [],
        globals: wf.globals || {},
      },
    });
    if (!res?.ok) throw new Error(res?.error?.message || "Duplicate failed");
    this.addLog?.("Preset duplicated");
  };

  editor._deleteOrArchivePreset = async function (id) {
    // Prefer DELETE, fall back to archive if server uses soft-delete
    const del = await this.API.workflows.remove(id);
    if (del?.ok) {
      this.addLog?.("Preset deleted");
      return;
    }
    const arch = await (this.API.workflows.archive?.(id) ||
      Promise.resolve({ ok: false }));
    if (!arch.ok)
      throw new Error(
        del?.error?.message || arch?.error?.message || "Delete/Archive failed"
      );
    this.addLog?.("Preset archived");
  };

  // --- Helpers ---------------------------------------------------------------
  function normalizeList(data) {
    // Accept multiple shapes: {items:[..]} or [..]
    const items = Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data)
      ? data
      : [];
    return items
      .map((it) => ({
        id: it.id || it.workflow_id || it.pk || it.uuid,
        title: it.title || it.name || `Workflow ${it.id}`,
        updated_at: ts(
          it.updated_at || it.modified || it.updated || it.created
        ),
        step_count:
          it.step_count ??
          it.steps ??
          (it.graph?.nodes?.length || it.nodes?.length || 0),
      }))
      .filter((it) => it.id != null);
  }
  function normalizeWorkflow(data) {
    const wf = data?.workflow || data || {};
    const graph = wf.graph || {};
    return {
      id: wf.id,
      title: wf.title || wf.name || `Workflow ${wf.id}`,
      graph: {
        nodes: graph.nodes || wf.nodes || [],
        edges: graph.edges || wf.edges || [],
        globals: graph.globals || wf.globals || {},
      },
    };
  }
  function ts(x) {
    if (!x) return null;
    try {
      return new Date(x).getTime();
    } catch {
      return null;
    }
  }
  function fmtDate(ms) {
    if (!ms) return "";
    try {
      return new Date(ms).toLocaleString();
    } catch {
      return "";
    }
  }
  function escapeHtml(s) {
    return String(s).replace(
      /[&<>"']/g,
      (m) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[m])
    );
  }

  // Optional: stub to keep older code happy if it expects this method
  if (!editor.saveNodeConfig) {
    editor.saveNodeConfig = function () {
      /* handled in editor.view config form via API directly */
    };
  }
}
