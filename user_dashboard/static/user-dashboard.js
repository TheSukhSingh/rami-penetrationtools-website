// user_dashboard/static/user-dashboard.js
(function() {
  const qs = sel => document.querySelector(sel);
  const qsa = sel => Array.from(document.querySelectorAll(sel));

  const sections = {
    overview: qs('#udb-overview'),
    analytics: qs('#udb-analytics'),
    scans: qs('#udb-scans'),
  };

  function showSection(name) {
    Object.entries(sections).forEach(([key, el]) => {
      if (!el) return;
      el.hidden = key !== name;
    });
    qsa('.udb-sidebar a').forEach(a => {
      a.classList.toggle('active', a.dataset.section === name);
    });
  }

  async function fetchJSON(url) {
    const res = await fetch(url, { credentials: 'include' });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
  }

  function renderOverview(data) {
    const el = sections.overview;
    if (!el) return;
    const s = data.summary || {};
    const byTool = data.by_tool || [];
    el.innerHTML = `
      <div class="udb-cards">
        <div class="udb-card"><div class="label">Total Scans (${s.days}d)</div><div class="value">${s.total ?? 0}</div></div>
        <div class="udb-card"><div class="label">Success</div><div class="value green">${s.success ?? 0}</div></div>
        <div class="udb-card"><div class="label">Failed</div><div class="value red">${s.failed ?? 0}</div></div>
      </div>
      <div class="udb-panel">
        <h3>Top Tools</h3>
        <ul class="udb-list">
          ${byTool.map(t => `<li><strong>${t.name}</strong> <span class="muted">(${t.slug})</span> — ${t.runs} runs</li>`).join('') || '<li class="muted">No data yet</li>'}
        </ul>
      </div>
    `;
  }

  function renderScans(data) {
    const el = sections.scans;
    if (!el) return;
    const rows = data.items || [];
    el.innerHTML = `
      <div class="udb-panel">
        <h3>Recent Scans</h3>
        <table class="udb-table">
          <thead><tr><th>When</th><th>Tool</th><th>Status</th><th>File</th><th>Download</th></tr></thead>
          <tbody>
            ${rows.map(r => {
              const when = r.scanned_at ? new Date(r.scanned_at).toLocaleString() : '-';
              const status = r.status ?? '—';
              const file = r.filename ?? '—';
              return `<tr>
                <td>${when}</td>
                <td>${r.tool?.name ?? ''}</td>
                <td>${status}</td>
                <td class="truncate" title="${file}">${file}</td>
                <td>${r.id ? `<a href="/dashboard/api/dashboard/download/${r.id}" target="_blank">Download</a>` : '—'}</td>
              </tr>`;
            }).join('') || `<tr><td colspan="5" class="muted">No scans yet</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

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
          ${series.map(p => `<li>${p.day}: ${p.runs}</li>`).join('') || '<li class="muted">No activity yet</li>'}
        </ul>
      </div>
    `;
  }

  async function loadAll() {
    showSection('overview');

    try {
      const [overview, scans, analytics] = await Promise.all([
        fetchJSON('/dashboard/api/dashboard/overview?days=30'),
        fetchJSON('/dashboard/api/dashboard/scans?page=1&per_page=10'),
        fetchJSON('/dashboard/api/dashboard/analytics?range=30d'),
      ]);
      renderOverview(overview);
      renderScans(scans);
      renderAnalytics(analytics);
    } catch (err) {
      console.error(err);
      const msg = (err && err.message) ? err.message : String(err);
      Object.values(sections).forEach(el => { if (el) el.innerHTML = `<div class="udb-error">${msg}</div>`; });
    }
  }

  // sidebar nav
  qsa('.udb-sidebar a').forEach(a => {
    a.addEventListener('click', () => showSection(a.dataset.section));
  });

  loadAll();
})();
