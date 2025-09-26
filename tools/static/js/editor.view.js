export function attachView(editor) {
  editor.searchTerm = "";
  editor._onSearchInput = function () {
    const el = document.getElementById("toolsSearch");
    editor.searchTerm = (el?.value || "").trim().toLowerCase();
    editor.renderTools();
  };
  document
    .getElementById("toolsSearch")
    ?.addEventListener("input", editor._onSearchInput);

  editor.addLog = function (message) {
    const wrap = document.getElementById("outputLogs");
    if (!wrap) return;
    const row = document.createElement("div");
    row.className = "output-item";
    row.innerHTML = `<span class="status-indicator idle"></span>${new Date().toLocaleTimeString()}: ${message}`;
    wrap.appendChild(row);
    // cap
    const maxRows = 500;
    while (wrap.children.length > maxRows) wrap.removeChild(wrap.firstChild);
    wrap.scrollTop = wrap.scrollHeight;
  };
// generic modal opener (title + Node|string body)
editor.openModal = function (title, content) {
  const modalEl = document.getElementById("configModal");
  const titleEl = document.getElementById("modalTitle");
  const bodyEl  = document.getElementById("modalBody");
  if (!modalEl || !titleEl || !bodyEl) return;

  titleEl.textContent = title || "";
  // clear previous content
  bodyEl.innerHTML = "";

  if (typeof content === "string") {
    bodyEl.innerHTML = content;
  } else if (content instanceof Node) {
    bodyEl.appendChild(content);
  }

  modalEl.classList.remove("hidden");
};

  editor.loadCatalog = async function () {
    try {
      this.catalogLoadError = false;
      const { ok, data } = await this.API.tools();
      if (!ok) throw new Error("catalog not ok");
      this.catalog = data?.categories || {};
      const flat = Object.values(this.catalog).flat();
      this.toolMetaBySlug = flat.reduce((a, m) => ((a[m.slug] = m), a), {});
      this.tools = flat.map((it) => ({
        id: it.slug,
        tool_slug: it.slug,
        name: it.name || it.slug,
        type: this.inferNodeType(it),
        icon: (it.slug?.[0] || "T").toUpperCase(),
        config: this.defaultConfigFor(it),
      }));
    } catch (e) {
      console.error(e);
      this.catalogLoadError = true;
      this.addLog("Error loading tool catalog");
    }
  };

  editor.renderTools = function () {
    const toolsList = document.getElementById("toolsList");
    if (!toolsList) return;
    toolsList.innerHTML = "";

    if (this.catalogLoadError) {
      const wrap = document.createElement("div");
      wrap.className = "muted";
      wrap.innerHTML = `
      Failed to load tools.
      <button class="btn xs" id="retryTools">Retry</button>
    `;
      toolsList.appendChild(wrap);
      document
        .getElementById("retryTools")
        ?.addEventListener("click", async () => {
          await this.loadCatalog();
          this.renderTools();
        });
      return;
    }

    const groups = this.catalog;
    if (!groups || !Object.keys(groups).length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "No tools available. Try reloading.";
      toolsList.appendChild(empty);
      return;
    }

    const matches = (it) => {
      const q = this.searchTerm;
      if (!q) return true;
      const name = (it.name || "").toLowerCase();
      const slug = (it.slug || "").toLowerCase();
      return name.includes(q) || slug.includes(q);
    };

    let anyShown = false;

    Object.entries(groups).forEach(([cat, items]) => {
      const filtered = (items || []).filter(matches);
      if (!filtered.length) return;

      // sticky header
      const head = document.createElement("div");
      head.className = "tools-category";
      head.textContent = cat;
      toolsList.appendChild(head);

      filtered.forEach((it) => {
        const tool = this.tools.find((t) => t.tool_slug === it.slug);
        if (!tool) return;

        const el = document.createElement("div");
        el.className = "tool-item";
        el.draggable = true;
        el.dataset.toolId = tool.id;
        el.setAttribute("aria-label", `Tool ${tool.name}`);
        el.setAttribute("tabindex", "0");

        el.innerHTML = `
        <div class="tool-icon">${tool.icon}</div>
        <div class="tool-name">${tool.name}</div>
        <button class="btn xs tool-add" type="button" aria-label="Add ${tool.name} to canvas">Add</button>
      `;

        // Keyboard/click “Add to canvas” at center
        const addNow = () => {
          const canvas = document.getElementById("canvasArea");
          const rect = canvas.getBoundingClientRect();
          this.createNode(tool, rect.width / 2, rect.height / 2);
        };
        el.querySelector(".tool-add")?.addEventListener("click", addNow);
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            addNow();
          }
        });

        // Drag behavior + a11y
        el.addEventListener("dragstart", (e) => {
          this.draggedTool = tool;
          el.classList.add("dragging");
          el.setAttribute("aria-grabbed", "true");
          e.dataTransfer.effectAllowed = "copy";
        });
        el.addEventListener("dragend", () => {
          el.classList.remove("dragging");
          el.setAttribute("aria-grabbed", "false");
          this.draggedTool = null;
        });

        toolsList.appendChild(el);
        anyShown = true;
      });
    });

    if (!anyShown) {
      const none = document.createElement("div");
      none.className = "muted";
      none.textContent = "No tools match your search.";
      toolsList.appendChild(none);
    }
  };

  editor.getNodeDescription = function (node) {
    const meta = this.toolMetaBySlug[node.tool_slug];
    const desc = meta?.desc || "Click gear to configure";
    const v = node.config?.value
      ? ` • value: ${String(node.config.value).slice(0, 60)}`
      : "";
    return desc + v;
  };

  // editor.view.js
  editor.showNodeConfig = function (node) {
    const modal = document.getElementById("configModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalBody = document.getElementById("modalBody");

    modalTitle.textContent = `Configure ${node.name}`;

    // Build a <form> instead of injecting inline onclick handlers
    const form = document.createElement("form");
    form.className = "config-form";

    // Create inputs for each config field
    Object.entries(node.config || {}).forEach(([key, value]) => {
      const group = document.createElement("div");
      group.className = "form-group";

      const label = document.createElement("label");
      label.className = "form-label";
      label.setAttribute("for", key);
      label.textContent = this.formatLabel(key);

      let input;
      if (typeof value === "boolean") {
        input = document.createElement("input");
        input.type = "checkbox";
        input.id = key;
        input.checked = !!value;
      } else {
        input = document.createElement("input");
        input.type = "text";
        input.className = "form-input";
        input.id = key;
        input.value = value ?? "";
      }

      group.appendChild(label);
      group.appendChild(input);
      form.appendChild(group);
    });

    // Actions row
    const actions = document.createElement("div");
    actions.className = "form-group";
    actions.style.marginTop = "24px";

    const saveBtn = document.createElement("button");
    saveBtn.type = "submit";
    saveBtn.className = "btn primary";
    saveBtn.textContent = "Save Configuration";

    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "btn";
    cancelBtn.style.marginLeft = "8px";
    cancelBtn.textContent = "Cancel";

    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
    form.appendChild(actions);

    // Mount into modal
    modalBody.innerHTML = "";
    modalBody.appendChild(form);
    modal.classList.remove("hidden");

    // Wire up behavior (no inline JS!)
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      // Uses editor.saveNodeConfig implemented in editor.presets.js
      this.saveNodeConfig?.(node.id);
    });

    cancelBtn.addEventListener("click", () => {
      this.closeModal?.();
    });
  };

  editor.closeModal = function () {
    document.getElementById("configModal")?.classList.add("hidden");
  };

  editor.formatLabel = function (key) {
    return (
      key.charAt(0).toUpperCase() + key.slice(1).replace(/([A-Z])/g, " $1")
    );
  };

  editor.renderRunSummary = async function (runId) {
    const out = document.getElementById("outputResults");
    if (!out) return;
    out.innerHTML = "";

    const paint = (runLike) => {
      const manifest = runLike.run_manifest || runLike.manifest || {};
      const counters = runLike.counters || manifest.counters || {};
      const buckets = manifest.buckets || {};
      const steps = manifest.steps || runLike.steps || []; // defensive

      // Header counts (include 'services')
      const header = document.createElement("div");
      header.className = "output-item";
      const parts = [
        "domains",
        "hosts",
        "ips",
        "ports",
        "services",
        "urls",
        "endpoints",
        "findings",
      ]
        .filter((k) => Number.isFinite(counters?.[k]))
        .map((k) => `${k}:${counters[k]}`);
      header.textContent = `Summary — ${parts.join(" ") || "no counters"}`;
      out.appendChild(header);

      // Per-step table
      if (Array.isArray(steps) && steps.length) {
        const sec = document.createElement("div");
        sec.className = "output-item";
        const tbl = document.createElement("table");
        tbl.className = "results-steps";
        tbl.innerHTML = `
        <thead><tr>
          <th>#</th><th>Tool</th><th>Status</th><th>Exec (ms)</th><th>Artifacts</th>
        </tr></thead><tbody></tbody>`;
        const tb = tbl.querySelector("tbody");
        steps.forEach((st, i) => {
          const tr = document.createElement("tr");
          const art = [];
          const of = st.output_file || st.artifact || st.output?.file;
          if (of)
            art.push(
              `<a href="${of}" target="_blank" rel="noreferrer">output</a>`
            );
          const cnt = st.counters || {};
          const quick = [
            "domains",
            "hosts",
            "ips",
            "ports",
            "services",
            "urls",
            "endpoints",
            "findings",
          ]
            .filter((k) => Number.isFinite(cnt[k]) && cnt[k] > 0)
            .slice(0, 3)
            .map((k) => `${k}:${cnt[k]}`)
            .join(" ");
          if (quick) art.push(quick);
          tr.innerHTML = `
          <td>${i}</td>
          <td>${st.tool_slug || st.tool || "—"}</td>
          <td>${st.status || "—"}</td>
          <td>${Number.isFinite(st.execution_ms) ? st.execution_ms : "—"}</td>
          <td>${art.join(" · ") || "—"}</td>`;
          tb.appendChild(tr);
        });
        sec.appendChild(tbl);
        out.appendChild(sec);
      }

      // Buckets preview (top 50 each)
      Object.entries(buckets).forEach(([k, v]) => {
        const items = v?.items || [];
        if (!items.length) return;
        const sec = document.createElement("div");
        sec.className = "output-item";
        const preview = items
          .slice(0, 50)
          .map((x) => (typeof x === "string" ? x : JSON.stringify(x)));
        sec.innerHTML = `<strong>${k}</strong><br>${preview.join("<br>")}${
          items.length > 50 ? "<br>…" : ""
        }`;
        out.appendChild(sec);
      });

      // Error info
      const er = runLike.error_reason || manifest.error_reason;
      if (er) {
        const err = document.createElement("div");
        err.className = "output-item";
        const ed = runLike.error_detail || manifest.error_detail;
        err.innerHTML = `<strong>Error:</strong> ${er}${
          ed ? " — " + String(ed) : ""
        }`;
        out.appendChild(err);
      }

      this.addLog?.("Summary loaded");
    };

    try {
      const s = await this.API.runs.summary(runId);
      if (s?.ok && (s.data?.run || s.data)) {
        paint(s.data.run || s.data);
        return;
      }
      const r = await this.API.runs.get(runId);
      if (r?.ok && (r.data?.run || r.data)) {
        paint(r.data.run || r.data);
        return;
      }
      throw new Error("No data");
    } catch (e) {
      console.error(e);
      this.addLog?.(`Summary error: ${e.message || e}`);
      const fallback = document.createElement("div");
      fallback.className = "output-item";
      fallback.textContent = "Failed to load summary.";
      out.appendChild(fallback);
    }
  };
}
