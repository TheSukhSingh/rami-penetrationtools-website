(function () {
  const qs = (s) => document.querySelector(s);
  const qsa = (s) => Array.from(document.querySelectorAll(s));

  const sections = {
    overview: qs('#udb-overview'),
    analytics: qs('#udb-analytics'),
    scans: qs('#udb-scans'),
  };

  function showSection(name) {
    Object.entries(sections).forEach(([k, el]) => el && (el.hidden = k !== name));
    qsa('.udb-sidebar a').forEach(a => a.classList.toggle('active', a.dataset.section === name));

  }

  async function fetchJSON(url) {
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  function renderOverview(data) {
    const el = sections.overview;
    if (!el) return;
    const s = data.summary || {};
    const byTool = data.by_tool || [];
    el.innerHTML = `
      <div class="udb-cards">
        <div class="udb-card"><div class="label">Total Scans (${s.days ?? 30}d)</div><div class="value">${s.total ?? 0}</div></div>

        <div class="udb-card"><div class="label">Success</div><div class="value green">${s.success ?? 0}</div></div>
        <div class="udb-card"><div class="label">Failed</div><div class="value red">${s.failed ?? 0}</div></div>
      </div>
      <div class="udb-panel">
        <h3>Top Tools</h3>
        <ul class="udb-list">
          ${
            byTool.length
              ? byTool.map(t => `<li><strong>${t.name}</strong> <span class="muted">(${t.slug})</span> — ${t.runs} runs</li>`).join('')
              : '<li class="muted">No data yet</li>'
          }

        </ul>
      </div>
    `;
  }

  // ---------- SCANS (filters + pagination + details) ----------
  const state = {
    tools: [],
    scans: { page: 1, perPage: 10, total: 0, items: [] },
    filters: { tool: '', status: '', search: '', date_from: '', date_to: '' },
  };

  async function loadTools() {
    try {
      const data = await fetchJSON('/tools/api/tools');
      state.tools = Array.isArray(data) ? data : (data.items || []);
    } catch {
      state.tools = [];
    }
  }

  function scansQuery() {
    const f = state.filters;
    const p = state.scans;
    const params = new URLSearchParams();
    params.set('page', String(p.page));
    params.set('per_page', String(p.perPage));
    if (f.tool) params.set('tool', f.tool);
    if (f.status) params.set('status', f.status);
    if (f.search) params.set('search', f.search);
    if (f.date_from) params.set('date_from', f.date_from);
    if (f.date_to) params.set('date_to', f.date_to);
    return `/dashboard/api/dashboard/scans?${params.toString()}`;
  }

  async function loadScans() {
    const data = await fetchJSON(scansQuery());
    state.scans.items = data.items || [];
    state.scans.total = data.total ?? state.scans.items.length;
    state.scans.page = data.page ?? state.scans.page;
    state.scans.perPage = data.per_page ?? state.scans.perPage;
    renderScans();
  }

  function renderFilters(container) {
    container.innerHTML = `
      <div class="udb-filterbar">
        <div class="row">
          <label>Tool
            <select id="f-tool">
              <option value="">All</option>
              ${state.tools.map(t => `<option value="${t.slug}">${t.name || t.slug}</option>`).join('')}
            </select>
          </label>
          <label>Status
            <select id="f-status">
              <option value="">All</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="FAILED">FAILED</option>
              <option value="RUNNING">RUNNING</option>
            </select>
          </label>
          <label>Search
            <input id="f-search" type="text" placeholder="filename, params…" />
          </label>
          <label>From
            <input id="f-from" type="date" />
          </label>
          <label>To
            <input id="f-to" type="date" />
          </label>
          <button id="f-apply" class="cyber-button small">Apply</button>
          <button id="f-clear" class="ghost small">Clear</button>
        </div>
      </div>
    `;

    qs('#f-tool').value = state.filters.tool;
    qs('#f-status').value = state.filters.status;
    qs('#f-search').value = state.filters.search;
    qs('#f-from').value = state.filters.date_from;
    qs('#f-to').value = state.filters.date_to;

    qs('#f-apply').addEventListener('click', async () => {
      state.filters.tool = qs('#f-tool').value;
      state.filters.status = qs('#f-status').value;
      state.filters.search = qs('#f-search').value.trim();
      state.filters.date_from = qs('#f-from').value;
      state.filters.date_to = qs('#f-to').value;
      state.scans.page = 1;
      await loadScans();
    });
    qs('#f-clear').addEventListener('click', async () => {
      state.filters = { tool: '', status: '', search: '', date_from: '', date_to: '' };
      state.scans.page = 1;
      await loadScans();
    });
  }

  function renderScans() {
    const el = sections.scans;
    if (!el) return;

    // create containers if first render
    if (!qs('#scans-filters')) {
      el.innerHTML = `<div id="scans-filters"></div><div id="scans-table"></div><div id="scans-pager"></div>`;
      renderFilters(qs('#scans-filters'));
    }

    const rows = state.scans.items;
    qs('#scans-table').innerHTML = `
      <div class="udb-panel">
        <h3>Recent Scans</h3>
        <table class="udb-table">
          <thead>
            <tr><th>When</th><th>Tool</th><th>Status</th><th>File</th><th>Actions</th></tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows.map(r => {
                    const when = r.scanned_at ? new Date(r.scanned_at).toLocaleString() : '-';
                    const tool = r.tool?.name || r.tool?.slug || '';
                    const file = r.filename || r.filename_by_user || '—';
                    const status = r.status || r.scan_success_state || '—';
                    return `
                      <tr>
                        <td>${when}</td>
                        <td>${tool}</td>
                        <td>${status}</td>
                        <td class="truncate" title="${file}">${file}</td>
                        <td>
                          ${r.id ? `<a class="small" href="/dashboard/api/dashboard/download/${r.id}" target="_blank">Download</a>` : ''}
                          ${r.id ? `<button class="small ghost" data-detail="${r.id}">View</button>` : ''}
                        </td>
                      </tr>`;
                  }).join('')
                : `<tr><td colspan="5" class="muted">No scans yet</td></tr>`
            }

          </tbody>
        </table>
      </div>
    `;

    // pagination
    const total = Number(state.scans.total || 0);
    const page = Number(state.scans.page || 1);
    const per = Number(state.scans.perPage || 10);
    const totalPages = Math.max(1, Math.ceil(total / per));

    qs('#scans-pager').innerHTML = `
      <div class="pager">
        <button id="pg-prev" class="ghost small" ${page <= 1 ? 'disabled' : ''}>Prev</button>
        <span>Page ${page} / ${totalPages} • ${total} total</span>
        <button id="pg-next" class="ghost small" ${page >= totalPages ? 'disabled' : ''}>Next</button>
      </div>
    `;

    qs('#pg-prev').onclick = async () => {
      if (state.scans.page > 1) { state.scans.page--; await loadScans(); }
    };
    qs('#pg-next').onclick = async () => {
      if (state.scans.page < totalPages) { state.scans.page++; await loadScans(); }
    };

    // detail modal buttons
    qsa('button[data-detail]').forEach(btn => {
      btn.addEventListener('click', () => openDetailModal(Number(btn.dataset.detail)));
    });
  }

  async function openDetailModal(scanId) {
    try {
      const data = await fetchJSON(`/dashboard/api/dashboard/scans/${scanId}`);
      const d = data || {};
      const diag = d.diagnostics || {};
      const body = `
        <div class="udb-modal glass">
          <div class="udb-modal-header">
            <h3>Scan #${d.id}</h3>
            <button class="close">&times;</button>
          </div>
          <div class="udb-modal-body">
            <div class="kv"><span class="k">Tool</span><span class="v">${d.tool?.name || d.tool?.slug || ''}</span></div>
            <div class="kv"><span class="k">When</span><span class="v">${d.scanned_at ? new Date(d.scanned_at).toLocaleString() : '-'}</span></div>
            <div class="kv"><span class="k">Status</span><span class="v">${d.status || d.scan_success_state || '—'}</span></div>
            <div class="kv"><span class="k">Filename</span><span class="v">${d.filename || '—'}</span></div>
            <hr/>
            <h4>Diagnostics</h4>
            <pre class="mono small">${JSON.stringify(diag, null, 2)}</pre>
          </div>
        </div>
      `;
      ensureModalHost().innerHTML = body;
      ensureModalHost().querySelector('.close').onclick = closeModal;
      ensureModalHost().addEventListener('click', (e) => { if (e.target === ensureModalHost()) closeModal(); });
      ensureModalHost().style.display = 'flex';
    } catch (e) {
      alert('Failed to load scan detail');
      console.error(e);
    }
  }

  function ensureModalHost() {
    let host = qs('#udb-modal-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'udb-modal-host';
      document.body.appendChild(host);
    }
    return host;
  }
  function closeModal() {
    const host = ensureModalHost();
    host.style.display = 'none';
    host.innerHTML = '';
  }

  // ---------- ANALYTICS ----------

  function renderAnalytics(data) {
    const el = sections.analytics;
    if (!el) return;
    const series = data.series || [];
    const total = data.total_runs ?? 0;
    el.innerHTML = `
      <div class="udb-panel">
        <h3>Usage (last ${data.days ?? 30} days)</h3>
        <div class="udb-cards">
          <div class="udb-card"><div class="label">Total Runs</div><div class="value">${total}</div></div>
        </div>
        <ul class="udb-list">
          ${series.length ? series.map(p => `<li>${p.day}: ${p.runs}</li>`).join('') : '<li class="muted">No activity yet</li>'}

        </ul>
      </div>
    `;
  }

  // ---------- INIT ----------
  qsa('.udb-sidebar a').forEach(a => a.addEventListener('click', () => showSection(a.dataset.section)));
  showSection('overview');

  (async function boot() {
    try {
      const [overview, scans, analytics] = await Promise.all([
        fetchJSON('/dashboard/api/dashboard/overview?days=30'),
        (async () => {
          await loadTools();
          return fetchJSON('/dashboard/api/dashboard/scans?page=1&per_page=10');
        })(),
        fetchJSON('/dashboard/api/dashboard/analytics?range=30d'),
      ]);

      renderOverview(overview);
      // seed initial scans payload into state before painting
      state.scans.items = scans.items || [];
      state.scans.total = scans.total ?? state.scans.items.length;
      state.scans.page = scans.page ?? 1;
      state.scans.perPage = scans.per_page ?? 10;
      renderScans();

      renderAnalytics(analytics);
    } catch (err) {
      console.error(err);
      Object.values(sections).forEach(el => el && (el.innerHTML = `<div class="udb-error">Failed to load: ${err.message}</div>`));
    }
  })();

})();
