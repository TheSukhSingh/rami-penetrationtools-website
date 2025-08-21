// import { setHeader } from '../lib/state.js';

// export async function mount(root) {
//   setHeader({ title: 'Scan History', subtitle: 'Scan history and activity timeline coming soon...' });
//   root.innerHTML = `
//     <div class="panel" style="padding:20px">
//       <h2>Scan History</h2>
//       <p>Scan history and activity timeline coming soon...</p>
//     </div>`;
// }
// export function unmount() {}



// static/admin/js/views/scans.js
// import { el } from "../lib/dom.js";
// import { getState, setHeader, subscribe } from "../lib/state.js";
// import { num, pct } from "../lib/format.js";
// import { getScansSummary, listScans, getScanDetail } from "../api/scans.js";
// import { createStatCard } from "../components/cards.js";
// import { drawTimeSeriesChart, drawBarChartLabeled } from "../components/charts.js";

// let cleanup = [];
// let ui = null;
// let cacheSummary = null;
// let cacheTable = { items: [], total: 0 };
// let currentPage = 1;

// function onCleanup(fn){ cleanup.push(fn); }
// function clearCleanup(){ cleanup.forEach(fn => { try{fn();}catch{} }); cleanup = []; }

// function buildSkeleton(root){
//   root.innerHTML = "";
//   const wrap = el("div", { class: "scans-wrap" });

//   // Cards
//   const cardsRow = el("div", { class: "cards-row" });
//   const cTotal   = createStatCard({ title: "Total Scans" });
//   const cRate    = createStatCard({ title: "Success Rate" });
//   const cFail    = createStatCard({ title: "Failures" });
//   const cAvg     = createStatCard({ title: "Avg Duration (ms)" });
//   cardsRow.append(cTotal.el, cRate.el, cFail.el, cAvg.el);

//   // Charts
//   const chartsRow  = el("div", { class: "charts-row" });
//   const dailyBox   = el("div", { class: "chart-card" }, el("h3", {}, "Daily Scans"));
//   const toolsBox   = el("div", { class: "chart-card" }, el("h3", {}, "Top Tools"));
//   const lineCanvas = el("canvas", { class: "chart-canvas", id: "sc-daily" });
//   const barCanvas  = el("canvas", { class: "chart-canvas", id: "sc-tools" });
//   dailyBox.append(lineCanvas); toolsBox.append(barCanvas);
//   chartsRow.append(dailyBox, toolsBox);

//   // Filters + table
//   const tableBox   = el("div", { class: "table-card" });
//   const filtersRow = el("div", { class: "filters-row" });
//   const qInput     = el("input", { class: "search", type: "search", placeholder: "Search (tool, command, file, user)..." });
//   const statusSel  = el("select", { class: "sel" }, 
//     el("option", { value: "" }, "All statuses"),
//     el("option", { value: "success" }, "Success"),
//     el("option", { value: "failure" }, "Failure"),
//   );
//   const toolInput  = el("input", { class: "search", type: "text", placeholder: "Tool slug (optional)" });
//   const btnApply   = el("button", { class: "btn" }, "Apply");
//   filtersRow.append(qInput, toolInput, statusSel, btnApply);

//   const table = buildTable();
//   tableBox.append(filtersRow, table.el);

//   wrap.append(cardsRow, chartsRow, tableBox);
//   root.append(wrap);

//   ui = {
//     cards: { total: cTotal, rate: cRate, fail: cFail, avg: cAvg },
//     lineCanvas, barCanvas,
//     filters: { qInput, statusSel, toolInput, btnApply },
//     table
//   };
// }

// function buildTable(){
//   const head = el("div", { class: "table-head" });
//   ["Time", "Tool", "User", "Status", "Duration", "Actions"].forEach(t => head.append(el("div", { class: "th" }, t)));

//   const body = el("div", { class: "table-body" });
//   const footer = el("div", { class: "table-footer" });
//   const prev = el("button", { class: "btn" }, "Prev");
//   const next = el("button", { class: "btn" }, "Next");
//   const info = el("span", { class: "muted" }, "");
//   footer.append(prev, next, info);

//   prev.onclick = () => { if (currentPage > 1) { currentPage--; refreshTable(); } };
//   next.onclick = () => { const maxp = Math.ceil((cacheTable.total || 0) / 20); if (currentPage < maxp) { currentPage++; refreshTable(); } };

//   return {
//     el: el("div", { class: "table" }, head, body, footer),
//     body, info,
//     render(items, total){
//       body.innerHTML = "";
//       if (!items?.length){
//         body.append(el("div", { class: "tr empty" }, el("div", { class: "td span" }, "No scans found")));
//       } else {
//         for (const it of items) body.append(renderRow(it));
//       }
//       const maxp = Math.ceil((total || 0) / 20) || 1;
//       this.info.textContent = `Page ${currentPage} of ${maxp} • ${total ?? 0} total`;
//     }
//   };
// }

// function renderRow(it){
//   const tr = el("div", { class: "tr" });
//   const when = it.scanned_at ? new Date(it.scanned_at).toLocaleString() : "-";
//   const user = it.user?.username || it.user?.email || it.user?.id || "-";
//   const status = it.success ? "SUCCESS" : (it.status || "FAILURE");
//   const dur = (it.duration_ms != null) ? `${it.duration_ms}` : "-";
//   const viewBtn = el("button", { class: "btn sm" }, "View");
//   viewBtn.onclick = async () => {
//     try {
//       const detail = await getScanDetail(it.id);
//       // You can swap this alert with your modal component
//       alert(JSON.stringify(detail, null, 2));
//     } catch (e) {}
//   };

//   tr.append(
//     el("div", { class: "td" }, when),
//     el("div", { class: "td" }, it.tool || "-"),
//     el("div", { class: "td" }, user),
//     el("div", { class: "td" }, status),
//     el("div", { class: "td" }, dur),
//     el("div", { class: "td" }, viewBtn),
//   );
//   return tr;
// }

// function baselineLabel(period){
//   switch(period){
//     case "1d":  return "from yesterday";
//     case "7d":  return "from previous week";
//     case "30d": return "from previous month";
//     case "90d": return "from previous quarter";
//     default:    return "vs previous period";
//   }
// }

// function updateCards(data){
//   const period = getState().period;
//   const suffix = ` ${baselineLabel(period)}`;
//   const c = data.cards || {};
//   ui.cards.total.update({
//     value: num(c.scan_count?.value ?? 0),
//     changeText: (pct(c.scan_count?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
//   });
//   ui.cards.rate.update({
//     value: pct((c.success_rate?.value ?? 0) * 100),
//     changeText: (pct(c.success_rate?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
//   });
//   ui.cards.fail.update({
//     value: num(c.failures?.value ?? 0),
//     changeText: (pct(c.failures?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.failures?.delta_vs_prev ?? 0) < 0, // lower failures is good
//   });
//   ui.cards.avg.update({
//     value: num(c.avg_duration_ms?.value ?? 0),
//     changeText: (pct(c.avg_duration_ms?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.avg_duration_ms?.delta_vs_prev ?? 0) <= 0, // lower is good
//   });
// }

// function updateCharts(data){
//   const period = getState().period;
//   const daily = data.charts?.daily_scans || [];
//   const series = (daily || []).map(r => ({ x: new Date(r.day || r.date), y: Number(r.total || 0) }));
//   drawTimeSeriesChart(ui.lineCanvas, series, { bucket: (period === "90d" ? "week" : period === "all" ? "month" : "day"), integer: true });

//   const tu = data.charts?.tools_usage || [];
//   drawBarChartLabeled(
//     ui.barCanvas,
//     tu.map(t => t.tool || t.name || "Tool"),
//     tu.map(t => Number(t.count || 0)),
//     { integer: true }
//   );
// }

// async function refreshSummary({ signal, silent=false }){
//   const { period } = getState();
//   if (cacheSummary && !silent) {
//     setHeader({ subtitle: `Last updated ${new Date(cacheSummary.computed_at).toLocaleString()}` });
//     updateCards(cacheSummary);
//     updateCharts(cacheSummary);
//   }
//   try {
//     const fresh = await getScansSummary(period, { signal });
//     cacheSummary = fresh;
//     setHeader({ subtitle: `Last updated ${new Date(fresh.computed_at).toLocaleString()}` });
//     updateCards(fresh);
//     updateCharts(fresh);
//   } catch (e) {}
// }

// async function refreshTable({ signal } = {}){
//   const params = {
//     page: currentPage,
//     per_page: 20,
//     q: ui.filters.qInput.value.trim(),
//     status: ui.filters.statusSel.value,
//     tool: ui.filters.toolInput.value.trim(),
//     sort: "-scanned_at",
//   };
//   try {
//     const res = await listScans(params, { signal });
//     cacheTable = { items: res.items || res, total: (res.meta?.total ?? res.total ?? 0) };
//     const items = res.items || res; // both shapes supported
//     const total = res.meta?.total ?? res.total ?? 0;
//     ui.table.render(items, total);
//   } catch (e) {}
// }

// export async function mount(root, { signal }){
//   buildSkeleton(root);
//   await refreshSummary({ signal, silent: false });
//   await refreshTable({ signal });

//   const unsub = subscribe(["period"], () => {
//     currentPage = 1;
//     refreshSummary({ signal, silent: false });
//     refreshTable({ signal });
//   });
//   onCleanup(unsub);

//   ui.filters.btnApply.onclick = () => { currentPage = 1; refreshTable({ signal }); };

//   const onTick = () => refreshSummary({ signal, silent: true });
//   window.addEventListener("admin:refresh", onTick);
//   onCleanup(() => window.removeEventListener("admin:refresh", onTick));

//   const onResize = () => { if (cacheSummary) { updateCharts(cacheSummary); } };
//   window.addEventListener("resize", onResize);
//   onCleanup(() => window.removeEventListener("resize", onResize));
// }

// export function unmount(){
//   clearCleanup();
//   ui = null;
// }





// static/admin/js/views/scans.js
// import { el } from "../lib/dom.js";
// import { getState, setHeader, subscribe } from "../lib/state.js";
// import { num, pct } from "../lib/format.js";
// import { getScansSummary, listScans, getScanDetail } from "../api/scans.js";
// import { createStatCard } from "../components/cards.js";
// import { drawTimeSeriesChart, drawBarChartLabeled } from "../components/charts.js";

// let cleanup = [];
// let ui = null;
// let cacheSummary = null;
// let cacheTable = { items: [], total: 0 };
// let currentPage = 1;

// function onCleanup(fn){ cleanup.push(fn); }
// function clearCleanup(){ cleanup.forEach(fn => { try{fn();}catch{} }); cleanup = []; }

// function buildSkeleton(root){
//   root.innerHTML = "";
//   const wrap = el("div", { class: "scans-wrap" });

//   // cards
//   const cardsRow = el("div", { class: "cards-row" });
//   const cTotal = createStatCard({ title: "Total Scans" });
//   const cActive = createStatCard({ title: "Active Scans" });
//   const cFailed = createStatCard({ title: "Failed Scans" });
//   const cRate   = createStatCard({ title: "Success Rate" });
//   cardsRow.append(cTotal.el, cActive.el, cFailed.el, cRate.el);

//   // charts
//   const chartsRow  = el("div", { class: "charts-row" });
//   const dailyBox   = el("div", { class: "chart-card" }, el("h3", {}, "Daily Scans"));
//   const toolsBox   = el("div", { class: "chart-card" }, el("h3", {}, "Top Tools"));
//   const lineCanvas = el("canvas", { class: "chart-canvas", id: "sc-daily" });
//   const barCanvas  = el("canvas", { class: "chart-canvas", id: "sc-tools" });
//   dailyBox.append(lineCanvas); toolsBox.append(barCanvas);
//   chartsRow.append(dailyBox, toolsBox);

//   // table + filters
//   const tableBox   = el("div", { class: "table-card" }, el("h3", {}, "Recent Scan History"));
//   const filtersRow = el("div", { class: "filters-row" });
//   const qInput     = el("input", { class: "search", type: "search", placeholder: "Search (tool, command, file, user)..." });
//   const toolInput  = el("input", { class: "search", type: "text", placeholder: "Tool (slug)" });
//   const statusSel  = el("select", { class: "sel" },
//     el("option", { value: "" }, "All statuses"),
//     el("option", { value: "success" }, "Success"),
//     el("option", { value: "failure" }, "Failure"),
//   );
//   const btnApply   = el("button", { class: "btn" }, "Apply");
//   filtersRow.append(qInput, toolInput, statusSel, btnApply);

//   const table = buildTable();

//   tableBox.append(filtersRow, table.el);

//   wrap.append(cardsRow, chartsRow, tableBox);
//   root.append(wrap);

//   ui = {
//     cards: { total: cTotal, active: cActive, failed: cFailed, rate: cRate },
//     lineCanvas, barCanvas,
//     filters: { qInput, toolInput, statusSel, btnApply },
//     table,
//   };
// }

// function buildTable(){
//   const head = el("div", { class: "table-head" });
//   ["Scan ID","User","Tool","Target","Location","Status","Duration","When"].forEach(t => head.append(el("div", { class: "th" }, t)));
//   const body = el("div", { class: "table-body" });
//   const footer = el("div", { class: "table-footer" });
//   const prev = el("button", { class: "btn" }, "Prev");
//   const next = el("button", { class: "btn" }, "Next");
//   const info = el("span", { class: "muted" }, "");
//   footer.append(prev, next, info);

//   prev.onclick = () => { if (currentPage > 1) { currentPage--; refreshTable(); } };
//   next.onclick = () => { const maxp = Math.ceil((cacheTable.total || 0) / 20); if (currentPage < maxp) { currentPage++; refreshTable(); } };

//   return {
//     el: el("div", { class: "table" }, head, body, footer),
//     body, info,
//     render(items, total){
//       body.innerHTML = "";
//       if (!items?.length){
//         body.append(el("div", { class: "tr empty" }, el("div", { class: "td span" }, "No scans found")));
//       } else {
//         for (const it of items) body.append(renderRow(it));
//       }
//       const maxp = Math.ceil((total || 0) / 20) || 1;
//       info.textContent = `Page ${currentPage} of ${maxp} • ${total ?? 0} total`;
//     }
//   };
// }

// function truncate(s, n=15){
//   if (!s) return "-";
//   s = String(s);
//   return s.length > n ? (s.slice(0, n) + "…") : s;
// }

// function fmtDuration(ms){
//   if (ms == null) return "-";
//   const sec = ms / 1000;
//   if (sec < 1) return `${ms} ms`;
//   if (sec < 60) return `${sec.toFixed(1)} s`;
//   const m = Math.floor(sec / 60);
//   const s = Math.round(sec % 60);
//   return `${m}m ${s}s`;
// }

// function renderRow(it){
//   const id = String(it.id);
//   const user = it.user?.username || it.user?.email || it.user?.id || "-";
//   const loc = it.location;
//   const locStr = loc?.city && loc?.country ? `${loc.city}, ${loc.country}` : (loc?.ip || "-");
//   const status = it.status || (it.success ? "SUCCESS" : "FAILURE");
//   const when = it.scanned_at ? new Date(it.scanned_at).toLocaleString() : "-";

//   const viewBtn = el("button", { class: "btn sm" }, "View");
//   viewBtn.onclick = async () => {
//     try {
//       const detail = await getScanDetail(it.id);
//       alert(JSON.stringify(detail, null, 2)); // swap with modal component if you like
//     } catch (e) {}
//   };

//   const tr = el("div", { class: "tr" });
//   tr.append(
//     el("div", { class: "td" }, id),
//     el("div", { class: "td" }, user),
//     el("div", { class: "td" }, it.tool || "-"),
//     el("div", { class: "td" }, truncate(it.target, 15)),
//     el("div", { class: "td" }, locStr),
//     el("div", { class: "td" }, status),
//     el("div", { class: "td" }, fmtDuration(it.duration_ms)),
//     el("div", { class: "td" }, when),
//   );
//   tr.addEventListener("dblclick", () => viewBtn.click());
//   return tr;
// }

// function baselineLabel(period){
//   switch (period){
//     case '1d':  return 'from yesterday';
//     case '7d':  return 'from previous week';
//     case '30d': return 'from previous month';
//     case '90d': return 'from previous quarter';
//     default:    return 'vs previous period';
//   }
// }

// function updateCards(data){
//   const period = getState().period;
//   const suffix = ` ${baselineLabel(period)}`;
//   const c = data.cards || {};
//   ui.cards.total.update({
//     value: num(c.scan_count?.value ?? 0),
//     changeText: (pct(c.scan_count?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
//   });
//   ui.cards.active.update({
//     value: num(c.active_now?.value ?? 0),
//     changeText: "live now",
//     positive: true,
//   });
//   ui.cards.failed.update({
//     value: num(c.failures?.value ?? 0),
//     changeText: (pct(c.failures?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.failures?.delta_vs_prev ?? 0) <= 0, // fewer failures = good
//   });
//   ui.cards.rate.update({
//     value: pct((c.success_rate?.value ?? 0) * 100),
//     changeText: (pct(c.success_rate?.delta_vs_prev ?? 0) + suffix),
//     positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
//   });
// }

// function updateCharts(data){
//   const period = getState().period;

//   const daily = data.charts?.daily_scans || [];
//   const series = daily.map(r => ({ x: new Date(r.day || r.date), y: Number(r.total || 0) }));
//   const bucket = (period === '90d') ? 'week' : (period === 'all') ? 'month' : 'day';
//   drawTimeSeriesChart(ui.lineCanvas, series, { bucket, integer: true });

//   const tu = data.charts?.tools_usage || [];
//   drawBarChartLabeled(
//     ui.barCanvas,
//     tu.map(t => t.tool || t.name || 'Tool'),
//     tu.map(t => Number(t.count || 0)),
//     { integer: true }
//   );
// }

// async function refreshSummary({ signal, silent=false }){
//   const { period } = getState();
//   if (cacheSummary && !silent) {
//     setHeader({ subtitle: `Last updated ${new Date(cacheSummary.computed_at).toLocaleString()}` });
//     updateCards(cacheSummary); updateCharts(cacheSummary);
//   }
//   try {
//     const fresh = await getScansSummary(period, { signal });
//     cacheSummary = fresh;
//     setHeader({ subtitle: `Last updated ${new Date(fresh.computed_at).toLocaleString()}` });
//     updateCards(fresh); updateCharts(fresh);
//   } catch (e) {}
// }

// async function refreshTable({ signal }={}){
//   const params = {
//     page: currentPage,
//     per_page: 20,
//     q: ui.filters.qInput.value.trim(),
//     tool: ui.filters.toolInput.value.trim(),
//     status: ui.filters.statusSel.value,
//     sort: "-scanned_at",
//   };
//   try {
//     const res = await listScans(params, { signal });
//     const items = res.items || res; // your ok() returns {items, meta} or just array; support both
//     const total = res.meta?.total ?? res.total ?? 0;
//     cacheTable = { items, total };
//     ui.table.render(items, total);
//   } catch (e) {}
// }

// export async function mount(root, { signal }){
//   buildSkeleton(root);
//   await refreshSummary({ signal });
//   await refreshTable({ signal });

//   const unsub = subscribe(['period'], () => {
//     currentPage = 1;
//     refreshSummary({ signal }); refreshTable({ signal });
//   });
//   onCleanup(unsub);

//   ui.filters.btnApply.onclick = () => { currentPage = 1; refreshTable({ signal }); };

//   const onTick = () => refreshSummary({ signal, silent: true });
//   window.addEventListener('admin:refresh', onTick);
//   onCleanup(() => window.removeEventListener('admin:refresh', onTick));
// }

// export function unmount(){ clearCleanup(); ui = null; }







import { setHeader, onRefresh, state } from "../lib/state.js";
import { el } from "../lib/dom.js";
import { num, pct } from "../lib/format.js";
import { getScansSummary, listScans, getScanDetail } from "../api/scans.js";
import { makeCardRow } from "../components/cards.js";
import { makeTable } from "../components/table.js";
import { makeSearchBox } from "../components/searchbox.js";
import { makePaginator } from "../components/paginator.js";
import { toast } from "../components/toast.js";

// ---- helpers ----
function baselineLabel(period) {
  switch (period) {
    case "1d":  return "from yesterday";
    case "7d":  return "from previous week";
    case "30d": return "from previous month";
    case "90d": return "from previous quarter";
    default:    return "vs previous period";
  }
}
function truncate(s, n = 15) {
  if (!s) return "—";
  s = String(s);
  return s.length > n ? s.slice(0, n) + "…" : s;
}
function fmtDuration(ms) {
  if (ms == null) return "—";
  const sec = ms / 1000;
  if (sec < 1) return `${ms} ms`;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

// ---- main view ----
export default function mountScans(root) {
  setHeader("Scans", "History, success rate, and live activity");

  const cardRow = makeCardRow();
  const toolbar = el("div", { class: "panel toolbar" });
  const tableWrap = el("div", { class: "panel" });

  root.replaceChildren(cardRow.el, toolbar, tableWrap);

  // --- Cards ---
  async function loadCards() {
    try {
      const rng = state.period; // "1d" | "7d" | "30d" | "90d" | "all"
      // You can tweak active_window minutes if you want:
      const data = await getScansSummary(rng, { active_window: 30 });
      const c = data.cards || {};
      const suffix = ` ${baselineLabel(rng)}`;

      const cards = [
        { title: "Total Scans",  value: num(c.scan_count?.value ?? 0),      delta: pct(c.scan_count?.delta_vs_prev ?? 0) + suffix,   positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0 },
        { title: "Active Scans", value: num(c.active_now?.value ?? 0),      delta: "live now",                                       positive: true },
        { title: "Failed Scans", value: num(c.failures?.value ?? 0),        delta: pct(c.failures?.delta_vs_prev ?? 0) + suffix,     // fewer failures = good
          positive: (c.failures?.delta_vs_prev ?? 0) <= 0 },
        { title: "Success Rate", value: pct((c.success_rate?.value ?? 0) * 100), delta: pct(c.success_rate?.delta_vs_prev ?? 0) + suffix, positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0 },
      ];

      cardRow.update(cards.map(x => ({
        title: x.title, value: x.value, delta: x.delta, positive: x.positive,
      })));
    } catch (e) {
      cardRow.update([
        { title: "Total Scans", value: "—", delta: null },
        { title: "Active Scans", value: "—", delta: null },
        { title: "Failed Scans", value: "—", delta: null },
        { title: "Success Rate", value: "—", delta: null },
      ]);
      throw e;
    }
  }

  // --- Table (search + pager) ---
  let page = 1, per_page = 20, q = "", tool = "", status = "", sort = "-scanned_at";

  const search = makeSearchBox({
    placeholder: "Search (tool, command, file, user)…",
    onInput(value) { q = value; page = 1; loadTable(); },
  });

  const toolInput = el("input", {
    class: "search",
    type: "text",
    placeholder: "Tool (slug)",
    oninput: (e) => { tool = e.target.value.trim(); },
  });

  const statusSel = el("select", { class: "sel" },
    el("option", { value: "" }, "All statuses"),
    el("option", { value: "success" }, "Success"),
    el("option", { value: "failure" }, "Failure"),
  );
  statusSel.onchange = (e) => { status = e.target.value; };

  const applyBtn = el("button", { class: "btn" }, "Apply");
  applyBtn.onclick = () => { page = 1; loadTable(); };

  toolbar.replaceChildren(search.el, toolInput, statusSel, applyBtn);

  const table = makeTable({
    columns: [
      { key: "id", label: "Scan ID", width: "10%" },
      { key: "user", label: "User", width: "16%", format: u => (u?.username || u?.email || u?.id || "—") },
      { key: "tool", label: "Tool", width: "12%" },
      { key: "target", label: "Target", width: "18%", format: v => truncate(v, 15) },
      { key: "location", label: "Location", width: "16%", format: loc => (loc?.ip ? [loc.city, loc.country].filter(Boolean).join(", ") || loc.ip : "—") },
      { key: "status", label: "Status", width: "12%" },
      { key: "duration_ms", label: "Duration", width: "8%", format: v => fmtDuration(v) },
      { key: "scanned_at", label: "When", width: "8%", format: t => t ? new Date(t).toLocaleString() : "—", sortable: true, sortKey: "scanned_at" },
    ],
    onSort(nextSortKey, isDesc) {
      sort = `${isDesc ? "-" : ""}${nextSortKey}`;
      page = 1;
      loadTable();
    },
    onRowClick(row) {
      openScanDetail(row.id);
    },
  });
  tableWrap.replaceChildren(table.el);

  const pager = makePaginator({
    onPage(next) { page = next; loadTable(); },
  });
  tableWrap.appendChild(pager.el);

  async function loadTable() {
    try {
      // NOTE: listScans can return either array or {items, meta}; handle both:
      const res = await listScans({ page, per_page, q, tool, status, sort });
      const items = Array.isArray(res) ? res : (res.items || []);
      const total = Array.isArray(res) ? undefined : (res.meta?.total ?? res.total);
      table.setRows(items || []);
      if (typeof total === "number") pager.setTotal(total, per_page, page);
    } catch (err) {
      console.error(err);
      toast.error(err?.data?.message || err?.message || "Failed to load Scans");
    }
  }

  // --- Row detail modal (plug your modal if you have one) ---
  async function openScanDetail(id) {
    try {
      const d = await getScanDetail(id);
      // Basic inline modal; replace with your own modal component if needed.
      const pre = el("pre", { style: "max-height:60vh;overflow:auto;margin:0" }, JSON.stringify(d, null, 2));
      const box = el("div", { class: "panel", style: "max-width: 900px" },
        el("h3", {}, "Scan Detail"),
        pre
      );
      const wrap = el("div", { class: "modal open" }, el("div", { class: "modal-box" }, box));
      function close(){ wrap.remove(); }
      wrap.addEventListener("click", (e) => { if (e.target === wrap) close(); });
      document.body.appendChild(wrap);
    } catch (err) {
      console.error(err);
      toast.error(err?.data?.message || err?.message || "Failed to load Scan detail");
    }
  }

  // --- Wire to global period + refresh ticker ---
  async function refresh() {
    await Promise.all([loadCards(), loadTable()]);
  }
  refresh();

  onRefresh(refresh);
  state.subscribe("period", refresh);
}
