(function () {
  const state = {
    nodes: [],
    selectedId: null,
    catalogBySlug: {},
    dirty: false,
    catalogGroups: [],
  };

  function qs(sel) {
    return document.querySelector(sel);
  }
  function qsa(sel) {
    return Array.from(document.querySelectorAll(sel));
  }
  function uid() {
    return "n" + Math.random().toString(36).slice(2, 10);
  }

  const els = {
    canvas:
      document.getElementById("canvas") ||
      document.getElementById("canvasArea") ||
      qs("[data-canvas]") ||
      qs(".canvas-root") ||
      qs(".canvas"),
    library: document.getElementById("toolsList") || qs("#toolsList"),
    logs:
      document.getElementById("logsPanel") || qs("#logs pre") || qs("#logs"),
    results:
      document.getElementById("resultsPanel") ||
      qs("#results pre") ||
      qs("#results"),
    runBtn:
      document.getElementById("runBtn") ||
      Array.from(qsa("button")).find(
        (b) => (b.textContent || "").trim().toLowerCase() === "run"
      ),
    globalBtn:
      document.getElementById("globalConfigBtn") ||
      Array.from(qsa("button")).find(
        (b) => (b.textContent || "").trim().toLowerCase() === "global config"
      ),
    drawer:
      document.getElementById("configDrawer") ||
      document.getElementById("configPanel"),
    drawerTitle:
      document.getElementById("configNodeTitle") ||
      qs("#configDrawer .drawer-header strong") ||
      qs("#configPanel .title"),
    drawerClose:
      document.getElementById("closeConfigDrawer") ||
      qs("#configDrawer .drawer-header button"),
    cfgText: document.getElementById("configJson"),
  };
window.Tools = window.Tools || {};

/** HTML-bound drop handler for both #canvasContent and #workflowBoxes */
window.Tools.__onCanvasDrop = function (e) {
  e.preventDefault();
  e.stopPropagation();

  const slug =
    (e.dataTransfer && (e.dataTransfer.getData("application/x-tool") ||
                        e.dataTransfer.getData("text/plain"))) || "";
  if (!slug) return;

  const rect = (els.canvas || e.currentTarget).getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  const meta = (window.Tools.getCatalog
                  ? (window.Tools.getCatalog() || []).find(t => t.slug === slug)
                  : null) || { slug, name: slug };

  if (typeof window.Tools.addNode === "function") {
    window.Tools.addNode(meta, { x, y });
  }
};


  function log(line) {
    if (!els.logs) return;
    const now = new Date().toLocaleTimeString();
    els.logs.textContent += `[${now}] ${line}\n`;
    if (els.logs.scrollTo) els.logs.scrollTo(0, els.logs.scrollHeight);
  }
// === Single, global DnD for the canvas (captures before overlays) ===========
(function enableGlobalCanvasDnD() {
  const canvas = document.getElementById("canvas");

  if (!canvas) return;

  function pointInsideCanvas(e) {
    const r = canvas.getBoundingClientRect();
    return e.clientX >= r.left && e.clientX <= r.right &&
           e.clientY >= r.top  && e.clientY <= r.bottom;
  }

  // 1) Always allow dragging when pointer is anywhere over the canvas.
  document.addEventListener("dragover", (e) => {
    if (!pointInsideCanvas(e)) return;
    e.preventDefault();               // <-- critical: turns off the 🚫 cursor
    e.stopPropagation();              // <-- bypass overlay listeners
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
  }, { capture: true, passive: false });

  // 2) Handle the drop globally and place node at pointer.
  document.addEventListener("drop", (e) => {
    if (!pointInsideCanvas(e)) return;
    e.preventDefault();
    e.stopPropagation();

    const slug = (e.dataTransfer &&
                 (e.dataTransfer.getData("application/x-tool") ||
                  e.dataTransfer.getData("text/plain"))) || "";
    if (!slug) return;

    // look up tool meta
    const bySlug = (window.Tools && typeof window.Tools.getCatalog === "function")
      ? (window.Tools.getCatalog() || []).reduce((acc, t) => { acc[t.slug] = t; return acc; }, {})
      : {};
    const meta = bySlug[slug] || { slug, name: slug };

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (window.Tools && typeof window.Tools.addNode === "function") {
      window.Tools.addNode(meta, { x, y });
    }
  }, { capture: true, passive: false });
})();


function enableCanvasDnD() {
  const canvas = document.getElementById("canvas");
  if (!canvas) return;

  // Let the canvas accept drops (otherwise you get the 🚫 cursor)
  ["dragenter", "dragover"].forEach((ev) => {
    canvas.addEventListener(ev, (e) => {
      e.preventDefault();
      try { e.dataTransfer.dropEffect = "copy"; } catch (_) {}
    });
  });

  canvas.addEventListener("drop", (e) => {
    e.preventDefault();

    // Try multiple types so we work across browsers/implementations
    const raw =
      e.dataTransfer.getData("application/json") ||
      e.dataTransfer.getData("application/x-tool") ||
      e.dataTransfer.getData("text/plain");

    if (!raw) return;

    let meta;
    try {
      meta = typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch {
      return; // not valid JSON; ignore
    }

    // Drop position relative to canvas
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Prefer your existing add-node entry point:
    if (window.Tools && typeof window.Tools.addNode === "function") {
      window.Tools.addNode(meta, { x, y });
    } else {
      // Fallback to bridge event if your app uses ui-bridge.js
      document.dispatchEvent(
        new CustomEvent("bridge:add-node", { detail: { meta, x, y } })
      );
    }
  });
}

  function normalizeGroups(payload) {
    if (!payload) return [];
    if (Array.isArray(payload)) return payload; // already groups
    if (payload.categories && typeof payload.categories === "object") {
      return Object.entries(payload.categories).map(([name, tools]) => ({
        name,
        tools,
      }));
    }
    return [];
  }
  function renderLibrary(groups) {
    if (!els.library) return;
    els.library.innerHTML = "";
    const frag = document.createDocumentFragment();

    (groups || []).forEach((g) => {
      const sec = document.createElement("section");
      sec.className = "tool-group";

      const h = document.createElement("h4");
      h.textContent = g.name || "Tools";
      h.style.margin = "8px 0";
      sec.appendChild(h);

      const box = document.createElement("div");
      (g.tools || []).forEach((t) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tool-item";
        btn.textContent = t.name || t.slug;
        btn.setAttribute("data-tool-slug", t.slug);
        btn.draggable = true;

        btn.addEventListener("dragstart", (ev) => {
  try {
    // Primary custom type
    ev.dataTransfer.setData("application/x-tool", t.slug);
    // Fallback for picky browsers
    ev.dataTransfer.setData("text/plain", t.slug);
    ev.dataTransfer.effectAllowed = "copy";
  } catch (e) {
    console.warn("dragstart setData failed", e);
  }
        });
        btn.addEventListener("dblclick", () => {
          window.Tools.addNode(t, { x: 220, y: 200 });
        });

        box.appendChild(btn);
      });

      sec.appendChild(box);
      frag.appendChild(sec);
    });

    els.library.appendChild(frag);
  }

  function openConfigPanel(node) {
    if (!els.drawer || !els.cfgText) return;
    if (els.drawerTitle) els.drawerTitle.textContent = node.name || node.slug;
    els.cfgText.value = JSON.stringify(node.config || {}, null, 2);
    if (els.drawer.classList.contains("open")) return;
    if (els.drawer.id === "configDrawer") els.drawer.classList.add("open");
    else els.drawer.style.display = "block";
  }

  function closeConfigPanel() {
    if (!els.drawer) return;
    if (els.drawer.id === "configDrawer") els.drawer.classList.remove("open");
    else els.drawer.style.display = "none";
  }

  function getNodeById(id) {
    return state.nodes.find((n) => n.id === id);
  }

  function selectNode(id) {
    state.selectedId = id;
    qsa(".node.selected").forEach((n) => n.classList.remove("selected"));
    const el = qs(`.node[data-id="${id}"]`);
    if (el) el.classList.add("selected");
    const node = getNodeById(id);
    if (node) openConfigPanel(node);
  }

  function updateNodePos(id, x, y) {
    const n = getNodeById(id);
    if (!n) return;
    n.x = x;
    n.y = y;
    const el = qs(`.node[data-id="${id}"]`);
    if (!el) return;
    el.style.transform = `translate(${x}px, ${y}px)`;
    state.dirty = true;
  }

  function removeNode(id) {
    const idx = state.nodes.findIndex((n) => n.id === id);
    if (idx >= 0) state.nodes.splice(idx, 1);
    const el = qs(`.node[data-id="${id}"]`);
    if (el && el.parentNode) el.parentNode.removeChild(el);
    if (state.selectedId === id) state.selectedId = null;
    state.dirty = true;
  }

  function createNodeEl(node) {
    const el = document.createElement("div");
    el.className = "node";
    el.dataset.id = node.id;
    el.style.position = "absolute";
    el.style.transform = `translate(${node.x}px, ${node.y}px)`;
    el.style.userSelect = "none";

    const badge = document.createElement("div");
    badge.className = "node-badge";
    badge.textContent = (node.name || node.slug || "?")
      .slice(0, 1)
      .toUpperCase();
    badge.style.position = "absolute";
    badge.style.top = "-18px";
    badge.style.left = "-18px";
    badge.style.width = "24px";
    badge.style.height = "24px";
    badge.style.borderRadius = "999px";
    badge.style.display = "grid";
    badge.style.placeItems = "center";
    badge.style.fontSize = "12px";
    badge.style.background = "rgba(0,255,200,.14)";
    badge.style.border = "1px solid rgba(0,255,200,.25)";

    const title = document.createElement("div");
    title.className = "node-title";
    title.textContent = node.name || node.slug;
    title.style.fontSize = "12px";
    title.style.color = "#cbd5e1";

    const close = document.createElement("button");
    close.type = "button";
    close.className = "remove-btn";
    close.textContent = "✕";
    close.style.position = "absolute";
    close.style.top = "-10px";
    close.style.right = "-10px";
    close.style.height = "22px";
    close.style.width = "22px";
    close.style.borderRadius = "999px";
    close.style.border = "0";
    close.style.background = "#1f2937";
    close.style.color = "#cbd5e1";
    close.style.cursor = "pointer";
    close.style.zIndex = "5";

    el.appendChild(badge);
    el.appendChild(title);
    el.appendChild(close);

    el.addEventListener("mousedown", onDragStart);
    el.addEventListener("click", function (e) {
      e.stopPropagation();
      selectNode(node.id);
    });
    close.addEventListener("click", function (e) {
      e.stopPropagation();
      removeNode(node.id);
    });

    return el;
  }

  function createNodeFromTool(meta, x, y) {
    if (!els.canvas) return;
    const node = {
      id: uid(),
      slug: meta.slug,
      name: meta.name || meta.slug,
      category: meta.category || "",
      x: x || 200,
      y: y || 200,
      config: {},
    };
    state.nodes.push(node);
    const el = createNodeEl(node);
    els.canvas.appendChild(el);
    selectNode(node.id);
    state.dirty = true;
    log(`Added node: ${node.slug}`);
  }

  function onDragStart(e) {
    const t = e.currentTarget;
    const id = t.dataset.id;
    const startX = e.clientX;
    const startY = e.clientY;
    const rect = t.getBoundingClientRect();
    const offX = startX - rect.left;
    const offY = startY - rect.top;

    function move(ev) {
      const cx =
        ev.clientX -
        offX -
        (els.canvas ? els.canvas.getBoundingClientRect().left : 0);
      const cy =
        ev.clientY -
        offY -
        (els.canvas ? els.canvas.getBoundingClientRect().top : 0);
      updateNodePos(id, Math.max(0, cx), Math.max(0, cy));
    }

    function up() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    }

    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  }

  function readJsonSafe(txt) {
    try {
      if (!txt || !txt.trim()) return {};
      return JSON.parse(txt);
    } catch {
      return null;
    }
  }

  function getChainLinearOrder() {
    const nodes = [...state.nodes];
    nodes.sort((a, b) => a.y - b.y || a.x - b.x);
    return nodes;
  }

  async function startRun() {
    if (!state.nodes.length) {
      log("No nodes on canvas.");
      return;
    }
    if (!state.selectedId) {
      log("Select a node on the canvas first.");
      return;
    }
    if (els.cfgText && state.selectedId) {
      const n = getNodeById(state.selectedId);
      const parsed = readJsonSafe(els.cfgText.value);
      if (parsed === null) {
        log("Invalid JSON in config.");
        return;
      }
      n.config = parsed;
    }
    const chain = getChainLinearOrder().map((n) => ({
      tool: n.slug,
      args: n.config || {},
    }));
    log("Posting workflow to /tools/api/start_run");
    try {
      const res = await fetch("/tools/api/start_run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chain }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        log("Start failed.");
        return;
      }
      const runId = data.run_id || data.id || null;
      log(runId ? `Run started: ${runId}` : "Run started.");
    } catch (e) {
      log("Network error starting run.");
    }
  }

  function hydrateCatalog(groups) {
    const bySlug = {};
    (groups || []).forEach((g) =>
      (g.tools || []).forEach((t) => {
        bySlug[t.slug] = t;
      })
    );
    state.catalogBySlug = bySlug;
  }

  async function loadCatalog() {
    try {
      const res = await fetch("/tools/api/tools");
      const payload = await res.json();
      const groups = normalizeGroups(payload);
      state.catalogGroups = groups;
      hydrateCatalog(groups);
      renderLibrary(groups);
      log("Loaded tools catalog from /tools/api/tools");
    } catch {
      log("Failed to load tools catalog.");
    }
  }

  function attachDrawerHandlers() {
    if (!els.drawer) return;
    if (els.drawerClose)
      els.drawerClose.addEventListener("click", closeConfigPanel);
    if (els.cfgText) {
      els.cfgText.addEventListener("change", () => {
        if (!state.selectedId) return;
        const n = getNodeById(state.selectedId);
        const parsed = readJsonSafe(els.cfgText.value);
        if (parsed !== null) n.config = parsed;
      });
    }
  }


document.addEventListener("dragover", (e) => {
  const root = document.getElementById("canvas");
  if (root && root.contains(e.target)) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
  }
}, { passive: false });


  function attachRunButtons() {
    if (els.runBtn) els.runBtn.addEventListener("click", startRun);
    if (els.globalBtn)
      els.globalBtn.addEventListener("click", () => {
        openConfigPanel({ id: "global", name: "Global Config", config: {} });
      });
  }

  window.Tools = window.Tools || {};
  window.Tools.addNode = function (meta, pos) {
    const x = pos && typeof pos.x === "number" ? pos.x : 200;
    const y = pos && typeof pos.y === "number" ? pos.y : 200;
    createNodeFromTool(meta, x, y);
  };
  window.Tools.startRun = function () {
    startRun();
  };
  window.Tools.toGlobalConfig = function () {
    openConfigPanel({ id: "global", name: "Global Config", config: {} });
  };
  window.Tools.getCatalog = function () {
    return Object.values(state.catalogBySlug);
  };
  window.Tools.setCatalog = function (groupsOrPayload) {
    const groups = normalizeGroups(groupsOrPayload);
    state.catalogGroups = groups;
    hydrateCatalog(groups);
    renderLibrary(groups);
  };
function findToolBySlug(slug) {
  for (const g of state.catalogGroups || []) {
    const m = (g.tools || []).find(t => t.slug === slug);
    if (m) return m;
  }
  return null;
}

  document.addEventListener("bridge:start-run", () => window.Tools.startRun());
  document.addEventListener("bridge:add-node", (ev) => {
    const d = ev.detail || {};
    if (!d.meta || !d.meta.slug) return;
    window.Tools.addNode(d.meta, { x: d.x, y: d.y });
  });
  document.addEventListener("bridge:global-config", () =>
    window.Tools.toGlobalConfig()
  );

  function init() {
    attachDrawerHandlers();
    attachRunButtons();
    enableCanvasDnD();
    // loadCatalog();
    log(
      "Chain rules: ≤1 input & ≤1 output per node, single start & end, linear path only."
    );
    log("Tip: Click an edge to select; press Delete to remove.");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
