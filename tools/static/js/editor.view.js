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
    wrap.scrollTop = wrap.scrollHeight;
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
    try {
      const res = await this.API.runs.get(runId);
      if (!res.ok) throw new Error(res.error?.message || "Failed to fetch run");
      const d = res.data || {};
      const run = d.run || d;
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
  };
}
