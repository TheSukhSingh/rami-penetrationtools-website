// tools/static/js/editor.history.js
export function attachHistory(editor) {

  // Open Run History (list)
  editor.openRunHistory = async function () {
    try {
      // Toolbar + list shell
      const wrap = document.createElement("div");
      wrap.className = "history-modal";
      wrap.innerHTML = `
        <div class="history-toolbar">
          <input id="rhSearch" class="input" type="search" placeholder="Search by title or run id…" aria-label="Search runs">
          <select id="rhStatus" class="input">
            <option value="">All statuses</option>
            <option value="RUNNING">Running</option>
            <option value="QUEUED">Queued</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="CANCELED">Canceled</option>
            <option value="PAUSED">Paused</option>
          </select>
          <label class="chk"><input type="checkbox" id="rhMine"> Current preset only</label>
        </div>
        <div class="history-list" id="rhList"></div>
        <div class="muted" id="rhEmpty" style="display:none">No runs.</div>
      `;

      const listEl = wrap.querySelector("#rhList");
      const emptyEl = wrap.querySelector("#rhEmpty");
      const searchEl = wrap.querySelector("#rhSearch");
      const statusEl = wrap.querySelector("#rhStatus");
      const mineEl   = wrap.querySelector("#rhMine");

      const refresh = async () => {
        const q = searchEl.value.trim();
        const status = statusEl.value || "";
        const workflow_id = mineEl.checked ? (editor.currentWorkflow?.id || "") : "";
        const r = await editor.API.runs.list({ q, status, workflow_id, limit: 50 });
        if (!r?.ok) throw new Error(r?.error?.message || "Failed to fetch runs");
        const runs = normalizeList(r.data);
        renderList(runs);
      };

      const renderList = (items) => {
        listEl.innerHTML = "";
        let shown = 0;
        items.sort((a,b)=> (b.started_at || 0) - (a.started_at || 0)).forEach(it => {
          const row = document.createElement("div");
          row.className = "run-row";
          row.innerHTML = `
            <div class="run-main">
              <div class="run-title" title="${esc(it.workflow_title || "")}">
                ${esc(it.workflow_title || "Untitled")} <span class="muted">#${it.id}</span>
              </div>
              <div class="run-meta">
                <span class="badge ${klass(it.status)}">${it.status}</span>
                <span>·</span>
                <span>${fmt(it.started_at) || "—"}</span>
                <span>·</span>
                <span>${dur(it.duration_ms)}</span>
                <span>·</span>
                <span>${it.step_count ?? "?"} steps</span>
              </div>
            </div>
            <div class="run-actions">
              <button class="btn xs" data-act="open">Open</button>
              <button class="btn xs" data-act="retry">Retry</button>
              ${it.status==="RUNNING" || it.status==="QUEUED" || it.status==="PAUSED"
                ? `<button class="btn xs" data-act="pause">Pause</button>
                   <button class="btn xs" data-act="resume">Resume</button>
                   <button class="btn xs danger" data-act="cancel">Cancel</button>`
                : ``}
            </div>
          `;
          row.querySelector('[data-act="open"]').addEventListener("click", () => editor._openRunDetail(it.id));
          row.querySelector('[data-act="retry"]').addEventListener("click", async () => {
            const rr = await editor.API.runs.retry(it.id);
            if (!rr?.ok) { alert(rr?.error?.message || "Retry failed"); return; }
            editor.addLog?.(`Retry started for run #${it.id}`);
            // Optionally open the new run if id is returned
            const newRunId = rr.data?.id || rr.data?.run_id || rr.data?.run?.id;
            if (newRunId) editor._openRunDetail(newRunId);
            refresh();
          });
          const pauseBtn = row.querySelector('[data-act="pause"]');
          const resumeBtn= row.querySelector('[data-act="resume"]');
          const cancelBtn= row.querySelector('[data-act="cancel"]');
          pauseBtn?.addEventListener("click", async ()=> { const pr = await editor.API.runs.pause(it.id); if (!pr?.ok) alert(pr?.error?.message || "Pause failed"); refresh(); });
          resumeBtn?.addEventListener("click", async()=> { const rr = await editor.API.runs.resume(it.id); if (!rr?.ok) alert(rr?.error?.message || "Resume failed"); refresh(); });
          cancelBtn?.addEventListener("click", async()=> { if (!confirm("Cancel this run?")) return; const cr = await editor.API.runs.cancel(it.id); if (!cr?.ok) alert(cr?.error?.message || "Cancel failed"); refresh(); });

          listEl.appendChild(row);
          shown++;
        });
        emptyEl.style.display = shown ? "none" : "block";
      };

      searchEl.addEventListener("input", refresh);
      statusEl.addEventListener("change", refresh);
      mineEl.addEventListener("change", refresh);

      await refresh();
      editor.openModal?.("Run History", wrap);
    } catch (e) {
      console.error(e);
      alert(`Failed to open history: ${e.message || e}`);
    }
  };

  // Run detail (with live attach if active)
  editor._openRunDetail = async function (runId) {
    // Stop any previous ephemeral stream
    try { editor._stopEphemeralStream?.(); } catch {}

    const shell = document.createElement("div");
    shell.className = "run-detail";
    shell.innerHTML = `
      <div class="run-detail-head">
        <div class="rd-title">Run #${runId}</div>
        <div class="rd-actions">
          <button class="btn xs" id="rdPause">Pause</button>
          <button class="btn xs" id="rdResume">Resume</button>
          <button class="btn xs danger" id="rdCancel">Cancel</button>
          <button class="btn xs" id="rdRetry">Retry</button>
        </div>
      </div>
      <div class="rd-status"><span class="status-indicator idle" id="rdDot"></span><span id="rdText">Loading…</span></div>
      <div class="rd-counters" id="rdCounters"></div>
      <div class="rd-steps" id="rdSteps"></div>
      <div class="rd-buckets" id="rdBuckets"></div>
    `;

    const dot = shell.querySelector("#rdDot");
    const txt = shell.querySelector("#rdText");
    const ctr = shell.querySelector("#rdCounters");
    const stp = shell.querySelector("#rdSteps");
    const bkt = shell.querySelector("#rdBuckets");
    const btnPause = shell.querySelector("#rdPause");
    const btnResume= shell.querySelector("#rdResume");
    const btnCancel= shell.querySelector("#rdCancel");
    const btnRetry = shell.querySelector("#rdRetry");

    const setDot = (status, pct=null) => {
      const cls = ["idle","running","ok","failed","canceled"];
      cls.forEach(c => dot.classList.remove(c));
      const s = String(status||"").toUpperCase();
      if (s==="RUNNING"||s==="QUEUED"||s==="PAUSED") dot.classList.add("running");
      else if (s==="COMPLETED"||s==="SUCCESS") dot.classList.add("ok");
      else if (s==="FAILED") dot.classList.add("failed");
      else if (s==="CANCELED") dot.classList.add("canceled");
      else dot.classList.add("idle");
      txt.textContent = ` ${status}${Number.isFinite(pct)?` (${pct}%)`:""}`;
    };

    const paintCounters = (counters={}) => {
      const order = ["domains","hosts","ips","ports","services","urls","endpoints","findings"];
      const parts = order.filter(k=>Number.isFinite(counters[k])).map(k=>`${k}:${counters[k]}`);
      ctr.innerHTML = parts.length ? `<div class="output-item"><strong>Summary —</strong> ${parts.join(" ")}</div>` : "";
    };

    const paintSteps = (steps=[]) => {
      if (!Array.isArray(steps) || !steps.length) { stp.innerHTML = ""; return; }
      const tbl = document.createElement("table");
      tbl.className = "results-steps";
      tbl.innerHTML = `<thead><tr><th>#</th><th>Tool</th><th>Status</th><th>Exec (ms)</th><th>Artifacts</th></tr></thead><tbody></tbody>`;
      const tb = tbl.querySelector("tbody");
      steps.forEach((s, i) => {
        const art = [];
        const of = s.output_file || s.artifact || (s.output && s.output.file);
        if (of) art.push(`<a href="${of}" target="_blank" rel="noreferrer">output</a>`);
        const cnt = s.counters || {};
        const quick = ["domains","hosts","ips","ports","services","urls","endpoints","findings"]
          .filter(k => Number.isFinite(cnt[k]) && cnt[k]>0).slice(0,3)
          .map(k => `${k}:${cnt[k]}`).join(" ");
        if (quick) art.push(quick);
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${i}</td><td>${s.tool_slug || s.tool || "—"}</td><td>${s.status || "—"}</td><td>${Number.isFinite(s.execution_ms)?s.execution_ms:"—"}</td><td>${art.join(" · ") || "—"}</td>`;
        tb.appendChild(tr);
      });
      stp.innerHTML = "";
      stp.appendChild(tbl);
    };

    const paintBuckets = (buckets={}) => {
      bkt.innerHTML = "";
      Object.entries(buckets).forEach(([k, v]) => {
        const items = v?.items || [];
        if (!items.length) return;
        const sec = document.createElement("div");
        sec.className = "output-item";
        const preview = items.slice(0, 50).map(x => typeof x==="string" ? x : JSON.stringify(x));
        sec.innerHTML = `<strong>${k}</strong><br>${preview.join("<br>")}${items.length>50?"<br>…":""}`;
        bkt.appendChild(sec);
      });
    };

    const refresh = async () => {
      const g = await editor.API.runs.get(runId);
      if (!g?.ok) throw new Error(g?.error?.message || "Failed to read run");
      const runObj = g.data?.run || g.data || g;
      setDot(runObj.status, Number.isFinite(runObj.progress_pct)?runObj.progress_pct:null);

      // Counters & buckets via summary
      const s = await editor.API.runs.summary(runId);
      const summary = (s?.ok && (s.data?.run || s.data)) ? (s.data.run || s.data) : {};
      paintCounters(summary.counters || {});
      const manifest = summary.run_manifest || summary.manifest || {};
      const buckets  = manifest.buckets || {};
      paintBuckets(buckets);

      // Steps (prefer manifest.steps array if present)
      const steps = Array.isArray(manifest.steps) ? manifest.steps : (runObj.steps || []);
      paintSteps(steps);

      // Enable/disable buttons per status
      const st = String(runObj.status||"").toUpperCase();
      const isActive = ["RUNNING","QUEUED","PAUSED"].includes(st);
      btnPause.disabled  = !["RUNNING","QUEUED"].includes(st);
      btnResume.disabled = !(st==="PAUSED");
      btnCancel.disabled = !isActive;
    };

    // Controls
    btnPause.addEventListener("click", async ()=>{ const r = await editor.API.runs.pause(runId); if (!r?.ok) alert(r?.error?.message || "Pause failed"); refresh(); });
    btnResume.addEventListener("click", async()=>{ const r = await editor.API.runs.resume(runId); if (!r?.ok) alert(r?.error?.message || "Resume failed"); refresh(); });
    btnCancel.addEventListener("click", async()=>{ if (!confirm("Cancel this run?")) return; const r = await editor.API.runs.cancel(runId); if (!r?.ok) alert(r?.error?.message || "Cancel failed"); refresh(); });
    btnRetry.addEventListener("click", async ()=>{ const r = await editor.API.runs.retry(runId); if (!r?.ok) { alert(r?.error?.message || "Retry failed"); return; } const newRun = r.data?.id || r.data?.run_id || r.data?.run?.id; if (newRun) this._openRunDetail(newRun); });

    await refresh();

    // Live attach if still active (ephemeral stream scoped to this modal)
    const stopper = editor.connectRunSSE(runId, {
      onEvent: (type, payload) => {
        if (type==="snapshot" && payload.run) setDot(payload.run.status, payload.run.progress_pct);
        if (type==="update" && (payload.type==="run" || payload.kind==="run")) {
          setDot(payload.status, payload.progress_pct);
          if (["COMPLETED","FAILED","CANCELED"].includes(payload.status)) {
            try { stopper?.(); } catch {}
          }
          refresh();
        }
      },
      onError: () => { /* silent; user can hit Refresh via reopening */ }
    });
    editor._stopEphemeralStream = stopper;

    editor.openModal?.(`Run #${runId}`, shell);
  };

  // Optional helper: check in-flight run for current workflow (called after loading a preset)
  editor._checkInFlightForWorkflow = async function (workflowId) {
    if (!workflowId) return;
    const r = await editor.API.runs.list({ status: "RUNNING", workflow_id: workflowId, limit: 1 });
    if (!r?.ok) return;
    const items = normalizeList(r.data);
    if (items.length) {
      const banner = document.getElementById("warningBanner");
      const text = document.getElementById("warningText");
      if (banner && text) {
        text.innerHTML = `A run (#${items[0].id}) is in progress for this preset. <a href="#" id="openInflight">Open</a>`;
        banner.classList.remove("hidden");
        document.getElementById("openInflight")?.addEventListener("click", (e)=>{ e.preventDefault(); editor._openRunDetail(items[0].id); });
      }
    }
  };

  // Helpers
  function normalizeList(data) {
    const arr = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
    return arr.map(it => ({
      id: it.id || it.run_id || it.pk || it.uuid,
      workflow_id: it.workflow_id,
      workflow_title: it.workflow_title || it.title || it.workflow?.title,
      status: it.status || "UNKNOWN",
      started_at: safeTs(it.started_at || it.created || it.queued_at),
      finished_at: safeTs(it.finished_at || it.completed_at),
      duration_ms: it.duration_ms ?? (safeTs(it.finished_at) && safeTs(it.started_at) ? (safeTs(it.finished_at)-safeTs(it.started_at)) : null),
      step_count: it.step_count ?? it.steps ?? it.step_total,
    })).filter(x => x.id != null);
  }
  function klass(status){ const s=String(status||"").toUpperCase();
    if (s==="RUNNING"||s==="QUEUED"||s==="PAUSED") return "b-running";
    if (s==="COMPLETED") return "b-ok";
    if (s==="FAILED") return "b-failed";
    if (s==="CANCELED") return "b-canceled";
    return "b-idle";
  }
  function esc(s){ return String(s).replace(/[&<>"']/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[m])); }
  function safeTs(x){ try { return x ? new Date(x).getTime() : null; } catch { return null; } }
  function fmt(ms){ if (!ms) return ""; try { return new Date(ms).toLocaleString(); } catch { return ""; } }
  function dur(ms){ if (!Number.isFinite(ms)) return "—"; const s=Math.max(0,Math.round(ms/1000)); const m=Math.floor(s/60), ss=s%60; return m?`${m}m ${ss}s`:`${ss}s`; }
}
