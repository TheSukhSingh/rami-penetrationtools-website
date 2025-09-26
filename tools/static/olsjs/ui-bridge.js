(function () {
  let catalog = [];
  const ToolsAPI = {
    addNode: (meta, pos) => (window.Tools && window.Tools.addNode) ? window.Tools.addNode(meta, pos) : document.dispatchEvent(new CustomEvent("bridge:add-node", { detail: { meta, x: pos?.x, y: pos?.y } })),
    startRun: () => (window.Tools && window.Tools.startRun) ? window.Tools.startRun() : document.dispatchEvent(new Event("bridge:start-run")),
    toGlobal: () => (window.Tools && window.Tools.toGlobalConfig) ? window.Tools.toGlobalConfig() : document.dispatchEvent(new Event("bridge:global-config")),
    setCatalog: (groups) => (window.Tools && window.Tools.setCatalog) ? window.Tools.setCatalog(groups) : null,
    getCatalog: () => (window.Tools && window.Tools.getCatalog) ? window.Tools.getCatalog() : []
  };

  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }
function hydrateCatalogDraggables(groups) {
  // Index tools by both slug and name for flexible matching
  const byKey = new Map();
  (groups || []).forEach((g) =>
    (g.tools || []).forEach((t) => {
      if (!t) return;
      byKey.set(String(t.slug || "").toLowerCase(), t);
      byKey.set(String(t.name || "").toLowerCase(), t);
    })
  );

  // Target common catalog elements; adjust selectors if your markup differs
  const candidates = document.querySelectorAll(
    '#toolCategories [data-slug], #toolCategories [data-tool-slug], #toolCategories .tool-item, #toolCategories button, #toolCategories a'
  );

  candidates.forEach((el) => {
    // Figure out which tool this element represents
    const key =
      (el.dataset.slug ||
        el.dataset.toolSlug ||
        el.textContent ||
        ""
      ).trim().toLowerCase();

    const meta = byKey.get(key);
    if (!meta) return;

    // Only wire once
    if (el.dataset.dndWired === "1") return;
    el.dataset.dndWired = "1";

    el.setAttribute("draggable", "true");
    el.addEventListener(
      "dragstart",
      (e) => {
        try {
          e.dataTransfer.setData("application/json", JSON.stringify(meta));
          e.dataTransfer.effectAllowed = "copy";
        } catch (_) {}
      },
      { passive: true }
    );
  });
}

  function logBridge(msg) {
    const el = document.getElementById("logsPanel") || qs("#logs pre") || qs("#logs");
    if (!el) return;
    const now = new Date().toLocaleTimeString();
    el.textContent += `[${now}] ${msg}\n`;
    if (el.scrollTo) el.scrollTo(0, el.scrollHeight);
  }

  async function fetchCatalog() {
    try {
      const res = await fetch("/tools/api/tools");
      const groups = await res.json();
      catalog = groups || [];
      ToolsAPI.setCatalog(catalog);
      hydrateCatalogDraggables(catalog);

      logBridge("Loaded tools catalog from /tools/api/tools");
      annotateExistingButtons();
      enableDragSources();
    } catch {
      logBridge("Failed to load tools catalog.");
    }
  }

  function annotateExistingButtons() {
    const nameToTool = {};
    catalog.forEach(g => (g.tools || []).forEach(t => {
      nameToTool[(t.name || "").trim().toLowerCase()] = t;
      nameToTool[(t.slug || "").trim().toLowerCase()] = t;
    }));
    qsa("button, .btn, .tool, .tool-item, .tool-btn, .capsule, .chip").forEach(el => {
      const txt = (el.getAttribute("data-label") || el.textContent || "").trim().toLowerCase();
      const t = nameToTool[txt];
      if (t) {
        el.setAttribute("data-tool-slug", t.slug);
        el.setAttribute("draggable", "true");
      }
    });
  }

  function enableDragSources() {
    qsa("[data-tool-slug]").forEach(el => {
      el.addEventListener("dragstart", ev => {
        const slug = el.getAttribute("data-tool-slug");
        ev.dataTransfer.setData("application/x-tool", slug);
        ev.dataTransfer.effectAllowed = "copy";
      });
      el.addEventListener("dblclick", () => {
        const slug = el.getAttribute("data-tool-slug");
        const meta = findTool(slug) || { slug, name: slug };
        ToolsAPI.addNode(meta, { x: 220, y: 200 });
      });
    });
  }

  function findTool(slug) {
    for (const g of catalog) {
      for (const t of (g.tools || [])) {
        if (t.slug === slug) return t;
      }
    }
    const fromAPI = (ToolsAPI.getCatalog() || []).find(t => t.slug === slug);
    return fromAPI || null;
  }

  function findCanvas() {
    return document.getElementById("canvas") || document.getElementById("canvasArea") || qs("[data-canvas]") || qs(".canvas-root") || qs(".canvas");
  }

  function hookCanvasClickAdd() {
    const canvas = findCanvas();
    if (!canvas) return;
    canvas.addEventListener("drop", () => {});
    canvas.addEventListener("click", e => {
      const paletteHover = document.querySelector("[data-tool-hover]");
      if (!paletteHover) return;
      const slug = paletteHover.getAttribute("data-tool-hover");
      const meta = findTool(slug) || { slug, name: slug };
      const rect = canvas.getBoundingClientRect();
      ToolsAPI.addNode(meta, { x: e.clientX - rect.left, y: e.clientY - rect.top });
    });
  }

  function wireRunAndGlobal() {
    const runBtn = document.getElementById("runBtn") || Array.from(qsa("button")).find(b => (b.textContent || "").trim().toLowerCase() === "run");
    const globalBtn = document.getElementById("globalConfigBtn") || Array.from(qsa("button")).find(b => (b.textContent || "").trim().toLowerCase() === "global config");
    if (runBtn) runBtn.addEventListener("click", () => ToolsAPI.startRun());
    if (globalBtn) globalBtn.addEventListener("click", () => ToolsAPI.toGlobal());
  }

  function init() {
    fetchCatalog();
    hookCanvasClickAdd();
    wireRunAndGlobal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
