import { el } from "../lib/dom.js";
import { getState, setHeader, subscribe } from "../lib/state.js";
import { num, pct } from "../lib/format.js";
import { getOverview } from "../api/metrics.js";
import { createStatCard } from "../components/cards.js";
import { drawTimeSeriesChart, drawBarChartLabeled } from "../components/charts.js";

let cleanup = [];
let ui = null;          // DOM refs
let cache = null;       // last successful payload

function onCleanup(fn) { cleanup.push(fn); }
function clearCleanup() { cleanup.forEach(fn => { try{fn();}catch{} }); cleanup = []; }

function buildSkeleton(root) {
  root.innerHTML = "";
  const wrap = el("div", { class: "overview-wrap" });

  // cards
  const cardsRow = el("div", { class: "cards-row" });
  const cardTotal = createStatCard({ title: "Total Users" });
  const cardRate  = createStatCard({ title: "Scan Success Rate" });
  const cardNew   = createStatCard({ title: "New Registrations" });
  const cardScans = createStatCard({ title: "Scan Count" });
  cardsRow.append(cardTotal.el, cardScans.el, cardNew.el, cardRate.el);

  // charts
  const chartsRow  = el("div", { class: "charts-row" });
  const dailyBox   = el("div", { class: "chart-card" }, el("h3", {}, "Daily Scans"));
  const toolsBox   = el("div", { class: "chart-card" }, el("h3", {}, "Tools Usage"));
  const lineCanvas = el("canvas", { class: "chart-canvas", id: "ov-daily" });
  const barCanvas  = el("canvas", { class: "chart-canvas", id: "ov-tools" });
  dailyBox.append(lineCanvas); toolsBox.append(barCanvas);
  chartsRow.append(dailyBox, toolsBox);

  wrap.append(cardsRow, chartsRow);
  root.append(wrap);

  ui = {
    cards: { total: cardTotal, rate: cardRate, newRegs: cardNew, scans: cardScans },
    lineCanvas, barCanvas
  };
}

/** Build {x: Date, y: number} series with missing buckets filled as zeros */
function buildSeries(raw, period) {
  const getDate = (r) => new Date(r.date || r.day || r.ts || r.d || r.x);
  const pts = (raw || []).map(r => ({ x: getDate(r), y: Number(r.total ?? r.y ?? 0) }))
                          .sort((a,b) => +a.x - +b.x);

  // bucket: day/week/month
  const bucket = (period === '90d') ? 'week'
               : (period === 'all') ? 'month'
               : 'day';

  const floor = (d) => {
    d = new Date(d); d.setHours(0,0,0,0);
    if (bucket === 'week') { const k = d.getDay(); d.setDate(d.getDate() - k); }
    if (bucket === 'month') d.setDate(1);
    return d;
  };

  const end = new Date(); end.setHours(0,0,0,0);
  const start = new Date(end);
  if (period === '1d')      start.setDate(end.getDate() - 0);
  else if (period === '7d') start.setDate(end.getDate() - 6);
  else if (period === '30d')start.setDate(end.getDate() - 29);
  else if (period === '90d')start.setDate(end.getDate() - 89);
  else { start.setMonth(end.getMonth() - 11); start.setDate(1); } // last 12 months

  const byBucket = new Map();
  for (const p of pts) {
    const k = +floor(p.x);
    byBucket.set(k, (byBucket.get(k) || 0) + p.y);
  }

  const step = (d) => {
    if (bucket === 'day')   d.setDate(d.getDate() + 1);
    if (bucket === 'week')  d.setDate(d.getDate() + 7);
    if (bucket === 'month'){ d.setMonth(d.getMonth() + 1); d.setDate(1); }
  };

  const series = [];
  for (let d = floor(start); +d <= +floor(end); step(d)) {
    const k = +d;
    series.push({ x: new Date(k), y: byBucket.get(k) || 0 });
  }
  return { series, bucket };
}

function baselineLabel(period) {
  switch (period) {
    case '1d':  return 'from yesterday';
    case '7d':  return 'from previous week';
    case '30d': return 'from previous month';
    case '90d': return 'from previous quarter';
    default:    return 'vs previous period';
  }
}

function updateUI(data){
  setHeader("Overview", "At-a-glance metrics, trends, and recent activity");
  setHeader({ subtitle: `Last updated ${new Date(data.computed_at).toLocaleString()}` });

  const period = getState().period;
  const suffix = ` ${baselineLabel(period)}`;
  const c = data.cards || {};

  ui.cards.total.update({
    value: num(c.total_users?.value ?? 0),
    changeText: (pct(c.total_users?.delta_vs_prev ?? 0) + suffix),
    positive: (c.total_users?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.rate.update({
    value: pct((c.success_rate?.value ?? 0) * 100),
    changeText: (pct(c.success_rate?.delta_vs_prev ?? 0) + suffix),
    positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.newRegs.update({
    value: num(c.new_registrations?.value ?? 0),
    changeText: (pct(c.new_registrations?.delta_vs_prev ?? 0) + suffix),
    positive: (c.new_registrations?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.scans.update({
    value: num(c.scan_count?.value ?? 0),
    changeText: (pct(c.scan_count?.delta_vs_prev ?? 0) + suffix),
    positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
  });

  // charts
  const { series, bucket } =
    buildSeries(data.charts?.daily_scans || [], period);
  drawTimeSeriesChart(ui.lineCanvas, series, { bucket, integer: true });

  const tu = (data.charts?.tools_usage || []);
  const labels = tu.map(t => t.tool || t.name || 'Tool');
  const values = tu.map(t => Number(t.count || 0));
  drawBarChartLabeled(ui.barCanvas, labels, values, { integer: true });
}


async function refresh({ signal, silent=false }){
  const { period } = getState();
  if (cache && !silent) updateUI(cache);

  try {
    const fresh = await getOverview(period, { signal });
    cache = fresh;
    updateUI(fresh);
  } catch (err) {
    const msg = String(err?.message || '').toLowerCase();
    const name = String(err?.name || '').toLowerCase();
    if (name === 'aborterror' || msg.includes('abort')) return; // ignore route change
    // else: optionally toast error
  }
}

export async function mount(root, { signal }){
  buildSkeleton(root);
  if (cache) updateUI(cache);                   // instant paint
  await refresh({ signal, silent: !!cache });  // fetch fresh

  // changes & timers
  const unsub = subscribe(['period'], () => refresh({ signal, silent:false }));
  onCleanup(unsub);

  const onTick = () => refresh({ signal, silent:true });
  window.addEventListener('admin:refresh', onTick);
  onCleanup(() => window.removeEventListener('admin:refresh', onTick));

  const onResize = () => { if (cache) updateUI(cache); };
  window.addEventListener('resize', onResize);
  onCleanup(() => window.removeEventListener('resize', onResize));
}

export function unmount(){
  clearCleanup();
  ui = null;   // keep cache for instant paint next time
}
