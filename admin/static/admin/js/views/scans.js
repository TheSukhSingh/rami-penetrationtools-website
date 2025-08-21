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
import { el } from "../lib/dom.js";
import { getState, setHeader, subscribe } from "../lib/state.js";
import { num, pct } from "../lib/format.js";
import { getScansSummary, listScans, getScanDetail } from "../api/scans.js";
import { createStatCard } from "../components/cards.js";
import { drawTimeSeriesChart, drawBarChartLabeled } from "../components/charts.js";

let cleanup = [];
let ui = null;
let cacheSummary = null;
let cacheTable = { items: [], total: 0 };
let currentPage = 1;

function onCleanup(fn){ cleanup.push(fn); }
function clearCleanup(){ cleanup.forEach(fn => { try{fn();}catch{} }); cleanup = []; }

function buildSkeleton(root){
  root.innerHTML = "";
  const wrap = el("div", { class: "scans-wrap" });

  // Cards
  const cardsRow = el("div", { class: "cards-row" });
  const cTotal   = createStatCard({ title: "Total Scans" });
  const cRate    = createStatCard({ title: "Success Rate" });
  const cFail    = createStatCard({ title: "Failures" });
  const cAvg     = createStatCard({ title: "Avg Duration (ms)" });
  cardsRow.append(cTotal.el, cRate.el, cFail.el, cAvg.el);

  // Charts
  const chartsRow  = el("div", { class: "charts-row" });
  const dailyBox   = el("div", { class: "chart-card" }, el("h3", {}, "Daily Scans"));
  const toolsBox   = el("div", { class: "chart-card" }, el("h3", {}, "Top Tools"));
  const lineCanvas = el("canvas", { class: "chart-canvas", id: "sc-daily" });
  const barCanvas  = el("canvas", { class: "chart-canvas", id: "sc-tools" });
  dailyBox.append(lineCanvas); toolsBox.append(barCanvas);
  chartsRow.append(dailyBox, toolsBox);

  // Filters + table
  const tableBox   = el("div", { class: "table-card" });
  const filtersRow = el("div", { class: "filters-row" });
  const qInput     = el("input", { class: "search", type: "search", placeholder: "Search (tool, command, file, user)..." });
  const statusSel  = el("select", { class: "sel" }, 
    el("option", { value: "" }, "All statuses"),
    el("option", { value: "success" }, "Success"),
    el("option", { value: "failure" }, "Failure"),
  );
  const toolInput  = el("input", { class: "search", type: "text", placeholder: "Tool slug (optional)" });
  const btnApply   = el("button", { class: "btn" }, "Apply");
  filtersRow.append(qInput, toolInput, statusSel, btnApply);

  const table = buildTable();
  tableBox.append(filtersRow, table.el);

  wrap.append(cardsRow, chartsRow, tableBox);
  root.append(wrap);

  ui = {
    cards: { total: cTotal, rate: cRate, fail: cFail, avg: cAvg },
    lineCanvas, barCanvas,
    filters: { qInput, statusSel, toolInput, btnApply },
    table
  };
}

function buildTable(){
  const head = el("div", { class: "table-head" });
  ["Time", "Tool", "User", "Status", "Duration", "Actions"].forEach(t => head.append(el("div", { class: "th" }, t)));

  const body = el("div", { class: "table-body" });
  const footer = el("div", { class: "table-footer" });
  const prev = el("button", { class: "btn" }, "Prev");
  const next = el("button", { class: "btn" }, "Next");
  const info = el("span", { class: "muted" }, "");
  footer.append(prev, next, info);

  prev.onclick = () => { if (currentPage > 1) { currentPage--; refreshTable(); } };
  next.onclick = () => { const maxp = Math.ceil((cacheTable.total || 0) / 20); if (currentPage < maxp) { currentPage++; refreshTable(); } };

  return {
    el: el("div", { class: "table" }, head, body, footer),
    body, info,
    render(items, total){
      body.innerHTML = "";
      if (!items?.length){
        body.append(el("div", { class: "tr empty" }, el("div", { class: "td span" }, "No scans found")));
      } else {
        for (const it of items) body.append(renderRow(it));
      }
      const maxp = Math.ceil((total || 0) / 20) || 1;
      this.info.textContent = `Page ${currentPage} of ${maxp} • ${total ?? 0} total`;
    }
  };
}

function renderRow(it){
  const tr = el("div", { class: "tr" });
  const when = it.scanned_at ? new Date(it.scanned_at).toLocaleString() : "-";
  const user = it.user?.username || it.user?.email || it.user?.id || "-";
  const status = it.success ? "SUCCESS" : (it.status || "FAILURE");
  const dur = (it.duration_ms != null) ? `${it.duration_ms}` : "-";
  const viewBtn = el("button", { class: "btn sm" }, "View");
  viewBtn.onclick = async () => {
    try {
      const detail = await getScanDetail(it.id);
      // You can swap this alert with your modal component
      alert(JSON.stringify(detail, null, 2));
    } catch (e) {}
  };

  tr.append(
    el("div", { class: "td" }, when),
    el("div", { class: "td" }, it.tool || "-"),
    el("div", { class: "td" }, user),
    el("div", { class: "td" }, status),
    el("div", { class: "td" }, dur),
    el("div", { class: "td" }, viewBtn),
  );
  return tr;
}

function baselineLabel(period){
  switch(period){
    case "1d":  return "from yesterday";
    case "7d":  return "from previous week";
    case "30d": return "from previous month";
    case "90d": return "from previous quarter";
    default:    return "vs previous period";
  }
}

function updateCards(data){
  const period = getState().period;
  const suffix = ` ${baselineLabel(period)}`;
  const c = data.cards || {};
  ui.cards.total.update({
    value: num(c.scan_count?.value ?? 0),
    changeText: (pct(c.scan_count?.delta_vs_prev ?? 0) + suffix),
    positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.rate.update({
    value: pct((c.success_rate?.value ?? 0) * 100),
    changeText: (pct(c.success_rate?.delta_vs_prev ?? 0) + suffix),
    positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.fail.update({
    value: num(c.failures?.value ?? 0),
    changeText: (pct(c.failures?.delta_vs_prev ?? 0) + suffix),
    positive: (c.failures?.delta_vs_prev ?? 0) < 0, // lower failures is good
  });
  ui.cards.avg.update({
    value: num(c.avg_duration_ms?.value ?? 0),
    changeText: (pct(c.avg_duration_ms?.delta_vs_prev ?? 0) + suffix),
    positive: (c.avg_duration_ms?.delta_vs_prev ?? 0) <= 0, // lower is good
  });
}

function updateCharts(data){
  const period = getState().period;
  const daily = data.charts?.daily_scans || [];
  const series = (daily || []).map(r => ({ x: new Date(r.day || r.date), y: Number(r.total || 0) }));
  drawTimeSeriesChart(ui.lineCanvas, series, { bucket: (period === "90d" ? "week" : period === "all" ? "month" : "day"), integer: true });

  const tu = data.charts?.tools_usage || [];
  drawBarChartLabeled(
    ui.barCanvas,
    tu.map(t => t.tool || t.name || "Tool"),
    tu.map(t => Number(t.count || 0)),
    { integer: true }
  );
}

async function refreshSummary({ signal, silent=false }){
  const { period } = getState();
  if (cacheSummary && !silent) {
    setHeader({ subtitle: `Last updated ${new Date(cacheSummary.computed_at).toLocaleString()}` });
    updateCards(cacheSummary);
    updateCharts(cacheSummary);
  }
  try {
    const fresh = await getScansSummary(period, { signal });
    cacheSummary = fresh;
    setHeader({ subtitle: `Last updated ${new Date(fresh.computed_at).toLocaleString()}` });
    updateCards(fresh);
    updateCharts(fresh);
  } catch (e) {}
}

async function refreshTable({ signal } = {}){
  const params = {
    page: currentPage,
    per_page: 20,
    q: ui.filters.qInput.value.trim(),
    status: ui.filters.statusSel.value,
    tool: ui.filters.toolInput.value.trim(),
    sort: "-scanned_at",
  };
  try {
    const res = await listScans(params, { signal });
    cacheTable = { items: res.items || res, total: (res.meta?.total ?? res.total ?? 0) };
    const items = res.items || res; // both shapes supported
    const total = res.meta?.total ?? res.total ?? 0;
    ui.table.render(items, total);
  } catch (e) {}
}

export async function mount(root, { signal }){
  buildSkeleton(root);
  await refreshSummary({ signal, silent: false });
  await refreshTable({ signal });

  const unsub = subscribe(["period"], () => {
    currentPage = 1;
    refreshSummary({ signal, silent: false });
    refreshTable({ signal });
  });
  onCleanup(unsub);

  ui.filters.btnApply.onclick = () => { currentPage = 1; refreshTable({ signal }); };

  const onTick = () => refreshSummary({ signal, silent: true });
  window.addEventListener("admin:refresh", onTick);
  onCleanup(() => window.removeEventListener("admin:refresh", onTick));

  const onResize = () => { if (cacheSummary) { updateCharts(cacheSummary); } };
  window.addEventListener("resize", onResize);
  onCleanup(() => window.removeEventListener("resize", onResize));
}

export function unmount(){
  clearCleanup();
  ui = null;
}
