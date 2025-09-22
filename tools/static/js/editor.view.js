export function attachView(editor) {
  editor.addLog = function(message) {
    const wrap = document.getElementById('outputLogs');
    if (!wrap) return;
    const row = document.createElement('div');
    row.className = 'output-item';
    row.innerHTML = `<span class="status-indicator idle"></span>${new Date().toLocaleTimeString()}: ${message}`;
    wrap.appendChild(row);
    wrap.scrollTop = wrap.scrollHeight;
  };

  editor.loadCatalog = async function() {
    try {
      const { ok, data } = await this.API.tools();
      if (!ok) throw new Error('catalog not ok');
      this.catalog = data?.categories || {};
      const flat = Object.values(this.catalog).flat();
      this.toolMetaBySlug = flat.reduce((a,m)=> (a[m.slug]=m, a), {});
      this.tools = flat.map(it => ({
        id: it.slug,
        tool_slug: it.slug,
        name: it.name || it.slug,
        type: this.inferNodeType(it),
        icon: (it.slug?.[0] || 'T').toUpperCase(),
        config: this.defaultConfigFor(it),
      }));
    } catch (e) { console.error(e); this.addLog('Error loading tool catalog'); }
  };

  editor.renderTools = function() {
    const toolsList = document.getElementById('toolsList');
    if (!toolsList) return;
    toolsList.innerHTML = '';

    // Optional: group by category header
    const groups = this.catalog;
    if (groups && Object.keys(groups).length) {
      Object.entries(groups).forEach(([cat, items]) => {
        const head = document.createElement('div');
        head.className = 'tools-category';
        head.textContent = cat;
        toolsList.appendChild(head);

        (items || []).forEach(it => {
          const tool = this.tools.find(t => t.tool_slug === it.slug);
          if (!tool) return;
          const el = document.createElement('div');
          el.className = 'tool-item';
          el.draggable = true;
          el.dataset.toolId = tool.id;
          el.innerHTML = `<div class="tool-icon">${tool.icon}</div><div class="tool-name">${tool.name}</div>`;
          el.addEventListener('dragstart', (e) => {
            this.draggedTool = tool; el.classList.add('dragging'); e.dataTransfer.effectAllowed = 'copy';
          });
          el.addEventListener('dragend', () => { el.classList.remove('dragging'); this.draggedTool = null; });
          toolsList.appendChild(el);
        });
      });
    }
  };

  editor.getNodeDescription = function(node) {
    const meta = this.toolMetaBySlug[node.tool_slug];
    const desc = meta?.desc || 'Click gear to configure';
    const v = (node.config?.value) ? ` • value: ${String(node.config.value).slice(0,60)}` : '';
    return desc + v;
  };

  editor.showNodeConfig = function(node) {
    const modal = document.getElementById('configModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    modalTitle.textContent = `Configure ${node.name}`;

    let formHTML = '';
    Object.keys(node.config).forEach((key) => {
      const value = node.config[key];
      const inputType = typeof value === 'boolean' ? 'checkbox' : 'text';
      formHTML += `<div class="form-group"><label class="form-label" for="${key}">${this.formatLabel(key)}</label>${
        inputType === 'checkbox' ? `<input type="checkbox" id="${key}" ${value ? 'checked' : ''}>`
                                 : `<input type="text" class="form-input" id="${key}" value="${value}">`
      }</div>`;
    });
    formHTML += `<div class="form-group" style="margin-top:24px;">
      <button class="btn primary" onclick="workflowEditor.saveNodeConfig('${node.id}')">Save Configuration</button>
      <button class="btn" onclick="workflowEditor.closeModal()" style="margin-left:8px;">Cancel</button>
    </div>`;
    modalBody.innerHTML = formHTML;
    modal.classList.remove('hidden');
  };

  editor.closeModal = function() {
    document.getElementById('configModal')?.classList.add('hidden');
  };

  editor.formatLabel = function(key) {
    return key.charAt(0).toUpperCase() + key.slice(1).replace(/([A-Z])/g, ' $1');
  };

  editor.renderRunSummary = async function(runId) {
    try {
      const res = await this.API.runs.get(runId);
      if (!res.ok) throw new Error(res.error?.message || 'Failed to fetch run');
      const d = res.data || {};
      const run = d.run || d;
      const manifest = run.run_manifest || run.manifest || {};
      const counters = run.counters || manifest.counters || {};
      const out = document.getElementById('outputResults');
      if (!out) return;
      out.innerHTML = '';
      const header = document.createElement('div');
      header.className = 'output-item';
      const countText = [
        ['domains', counters.domains], ['hosts', counters.hosts], ['ips', counters.ips],
        ['ports', counters.ports], ['urls', counters.urls], ['endpoints', counters.endpoints], ['findings', counters.findings],
      ].filter(([,v])=>Number.isFinite(v)).map(([k,v])=>`${k}:${v}`).join(' ');
      header.textContent = `Summary — ${countText || 'no counters'}`;
      out.appendChild(header);
      const buckets = manifest.buckets || {};
      Object.entries(buckets).forEach(([k, v]) => {
        const items = v?.items || [];
        if (!items.length) return;
        const sec = document.createElement('div');
        sec.className = 'output-item';
        const list = items.slice(0, 50).map(x => typeof x === 'string' ? x : JSON.stringify(x));
        sec.innerHTML = `<strong>${k}</strong><br>${list.join('<br>')}${items.length > 50 ? '<br>…' : ''}`;
        out.appendChild(sec);
      });
      this.addLog('Summary loaded');
    } catch (e) { console.error(e); this.addLog(`Summary error: ${e.message || e}`); }
  };
}
