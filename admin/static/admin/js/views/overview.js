// import { el, qs } from '../lib/dom.js';
// import { getState, setHeader, subscribe } from '../lib/state.js';
// import { num, pct } from '../lib/format.js';
// import { getOverview } from '../api/metrics.js';
// import { createStatCard } from '../components/cards.js';
// import { drawLineChart, drawBarChart } from '../components/charts.js';

// let cleanupFns = [];

// function clearCleanup() { cleanupFns.forEach(fn => { try { fn(); } catch {} }); cleanupFns = []; }

// async function renderOnce(root, { signal }) {
//   const { period } = getState();
//   const payload = await getOverview(period, { signal });
//   const data = payload?.data ?? payload;
//   // --- header text (optional; you already show page title) ---
//   setHeader({
//     title: 'Dashboard Overview',
//     subtitle: `Last updated ${new Date(data.computed_at).toLocaleString()}`
//   });

//   // --- cards ---
//   const cardsWrap = el('div', { class: 'metrics-grid' });
//   const cardUsers   = createStatCard({ title: 'Total Users' });
//   const cardSR      = createStatCard({ title: 'Scan Success Rate' });
//   const cardNewRegs = createStatCard({ title: 'New Registrations' });
//   const cardScans   = createStatCard({ title: 'Scan Count' });
//   cardsWrap.append(cardUsers.el, cardSR.el, cardNewRegs.el, cardScans.el);

//   // --- charts ---
//   const chartsWrap = el('div', { class: 'charts-grid' });
//   const lineCanvas = el('canvas', { width: 800, height: 260, class: 'chart-canvas' });
//   const barCanvas  = el('canvas', { width: 800, height: 260, class: 'chart-canvas' });
//   chartsWrap.append(
//     el('div', { class: 'chart-card glass' }, el('h3', {}, 'Daily Scans'), lineCanvas),
//     el('div', { class: 'chart-card glass' }, el('h3', {}, 'Tools Usage'), barCanvas)
//   );

//   // mount layout (fresh each time mount() runs)
//   root.append(cardsWrap, chartsWrap);

//   // ---- populate cards ----
//   const tu = data.cards.total_users;
//   const sr = data.cards.success_rate;
//   const nr = data.cards.new_registrations;
//   const sc = data.cards.scan_count;

//   cardUsers.update({
//     value: num(tu.value || 0),
//     changeText: pct(Math.round((tu.delta_vs_prev || 0) * 10) / 10),
//     positive: (tu.delta_vs_prev || 0) >= 0
//   });

//   const srPct = Math.round(((sr.value || 0) * 1000)) / 10; // one decimal
//   cardSR.update({
//     value: `${srPct}%`,
//     changeText: pct(Math.round((sr.delta_vs_prev || 0) * 10) / 10),
//     positive: (sr.delta_vs_prev || 0) >= 0
//   });

//   cardNewRegs.update({
//     value: num(nr.value || 0),
//     changeText: pct(Math.round((nr.delta_vs_prev || 0) * 10) / 10),
//     positive: (nr.delta_vs_prev || 0) >= 0
//   });

//   cardScans.update({
//     value: num(sc.value || 0),
//     changeText: pct(Math.round((sc.delta_vs_prev || 0) * 10) / 10),
//     positive: (sc.delta_vs_prev || 0) >= 0
//   });

//   // ---- charts ----
//   const daily = (data.charts?.daily_scans || []).map(d => d.total || 0);
//   drawLineChart(lineCanvas, daily.length ? daily : [0]);

//   const tools = (data.charts?.tools_usage || []).map(t => t.count || 0);
//   drawBarChart(barCanvas, tools.length ? tools : [0]);

//   // ---- optional: topbar live stat if you later add it to payload ----
//   // const au = data.cards.active_users?.value;
//   // if (au != null) { const elAU = qs('#stat-active-users'); if (elAU) elAU.textContent = num(au); }
// }

// async function refresh(root, { signal }) {
//   // Replace only the dynamic numbers/charts; keep DOM stable for less flicker
//   // Here we simply re-render the whole view for simplicity; you can optimize later.
//   root.innerHTML = '';
//   await renderOnce(root, { signal });
// }

// export async function mount(root, { signal }) {
//   // initial paint
//   await renderOnce(root, { signal });

//   // re-fetch when global period changes
//   const unsub = subscribe(['period'], () => refresh(root, { signal }));
//   cleanupFns.push(unsub);

//   // re-fetch on global tick
//   const onTick = () => refresh(root, { signal });
//   window.addEventListener('admin:refresh', onTick);
//   cleanupFns.push(() => window.removeEventListener('admin:refresh', onTick));
// }

// export function unmount() {
//   clearCleanup();
// }

// import { el } from "../lib/dom.js";
// import { getState, setHeader, subscribe } from "../lib/state.js";
// import { num, pct } from "../lib/format.js";
// import { getOverview } from "../api/metrics.js";
// import { createStatCard } from "../components/cards.js";
// import { drawLineChart, drawBarChart } from "../components/charts.js";

// let cleanup = [];
// let ui = null; // hold DOM refs so we can update instead of re-creating
// let cache = null; 

// function onCleanup(fn) {
//   cleanup.push(fn);
// }
// function clearCleanup() {
//   cleanup.forEach((fn) => {
//     try {
//       fn();
//     } catch {}
//   });
//   cleanup = [];
// }

// function buildSkeleton(root) {
//   root.innerHTML = ""; // <-- ensure we never append twice
//   const wrap = el("div", { class: "overview-wrap" });

//   const cardsRow = el('div', { class: 'cards-row' });
//   const cardTotal = createStatCard({ title: "Total Users" });
//   const cardRate = createStatCard({ title: "Scan Success Rate" });
//   const cardNew = createStatCard({ title: "New Registrations" });
//   const cardScans = createStatCard({ title: "Scan Count" });
//   cardsRow.append(cardTotal.el, cardRate.el, cardNew.el, cardScans.el);

//   // charts row
//   // const chartsRow = el("div", {
//   //   class: "charts-row",
//   //   style:
//   //     "display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;",
//   // });
//   // const dailyBox = el("div", { class: "panel" }, el("h3", {}, "Daily Scans"));
//   // const toolsBox = el("div", { class: "panel" }, el("h3", {}, "Tools Usage"));
//   // const lineCanvas = el("canvas", { width: 900, height: 320, id: "ov-daily" });
//   // const barCanvas = el("canvas", { width: 900, height: 320, id: "ov-tools" });
//   const chartsRow = el("div", { class: "charts-row" });
//   const dailyBox = el(
//     "div",
//     { class: "chart-card" },
//     el("h3", {}, "Daily Scans")
//   );
//   const toolsBox = el(
//     "div",
//     { class: "chart-card" },
//     el("h3", {}, "Tools Usage")
//   );
//   const lineCanvas = el("canvas", { class: "chart-canvas", id: "ov-daily" });
//   const barCanvas = el("canvas", { class: "chart-canvas", id: "ov-tools" });
//   dailyBox.append(lineCanvas);
//   toolsBox.append(barCanvas);
//   chartsRow.append(dailyBox, toolsBox);

//   wrap.append(cardsRow, chartsRow);
//   root.append(wrap);

//   ui = {
//     cards: {
//       total: cardTotal,
//       rate: cardRate,
//       newRegs: cardNew,
//       scans: cardScans,
//     },
//     lineCanvas,
//     barCanvas,
//   };
// }
// function updateUI(data){
//   setHeader({ subtitle: `Last updated ${new Date(data.computed_at).toLocaleString()}` });

//   const c = data.cards || {};
//   ui.cards.total.update({
//     value: num(c.total_users?.value ?? 0),
//     changeText: pct(c.total_users?.delta_vs_prev ?? 0),
//     positive: (c.total_users?.delta_vs_prev ?? 0) >= 0,
//   });
//   ui.cards.rate.update({
//     value: pct((c.success_rate?.value ?? 0) * 100),
//     changeText: pct(c.success_rate?.delta_vs_prev ?? 0),
//     positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
//   });
//   ui.cards.newRegs.update({
//     value: num(c.new_registrations?.value ?? 0),
//     changeText: pct(c.new_registrations?.delta_vs_prev ?? 0),
//     positive: (c.new_registrations?.delta_vs_prev ?? 0) >= 0,
//   });
//   ui.cards.scans.update({
//     value: num(c.scan_count?.value ?? 0),
//     changeText: pct(c.scan_count?.delta_vs_prev ?? 0),
//     positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
//   });

//   const dailyTotals = (data.charts?.daily_scans ?? []).map(d => d.total ?? 0);
//   drawLineChart(ui.lineCanvas, dailyTotals.length ? dailyTotals : [0]);

//   const toolCounts = (data.charts?.tools_usage ?? []).map(t => t.count ?? 0);
//   drawBarChart(ui.barCanvas, toolCounts.length ? toolCounts : [0]);
// }

// async function refresh({ signal, silent=false }){
//   const { period } = getState();

//   // paint last known data immediately (no flicker)
//   if (cache && !silent) updateUI(cache);

//   try {
//     const fresh = await getOverview(period, { signal }); // returns inner data
//     cache = fresh;               // keep it
//     updateUI(fresh);
//   } catch (err) {
//     const msg = String(err?.message || '').toLowerCase();
//     const name = String(err?.name || '').toLowerCase();
//     if (name === 'aborterror' || msg.includes('abort')) return; // ignore route change
//     // optionally toast real errors here
//   }
// }

// export async function mount(root, { signal }){
//   buildSkeleton(root);
//   if (cache) updateUI(cache);            // instant paint from cache
//   await refresh({ signal, silent: !!cache });

//   // period change → fresh fetch
//   const unsub = subscribe(['period'], () => refresh({ signal, silent:false }));
//   onCleanup(unsub);

//   // global 60s tick → silent refresh
//   const onTick = () => refresh({ signal, silent:true });
//   window.addEventListener('admin:refresh', onTick);
//   onCleanup(() => window.removeEventListener('admin:refresh', onTick));

//   // resize → redraw from cache to fit new width
//   const onResize = () => { if (cache) updateUI(cache); };
//   window.addEventListener('resize', onResize);
//   onCleanup(() => window.removeEventListener('resize', onResize));
// }

// export function unmount(){
//   clearCleanup();
//   // keep `cache` so coming back is instant
//   ui = null;
// }


// import { getState } from '../lib/state.js';

// // build an array of { x: Date, y: number } with missing buckets filled
// function buildSeries(raw, period) {
//   // raw items may be {date|day|ts, total}
//   const getDate = (r) => new Date(r.date || r.day || r.ts || r.d || r.x);
//   const pts = (raw || []).map(r => ({ x: getDate(r), y: Number(r.total || r.y || 0) }))
//                           .sort((a,b) => +a.x - +b.x);

//   // choose bucket
//   const bucket = (period === '90d') ? 'week'
//                : (period === 'all') ? 'month'
//                : 'day';

//   // helper to floor date to bucket
//   const floor = (d) => {
//     d = new Date(d); d.setHours(0,0,0,0);
//     if (bucket === 'week') {
//       const day = d.getDay(); // 0=Sun
//       d.setDate(d.getDate() - day); // start of week (Sun)
//     }
//     if (bucket === 'month') d.setDate(1);
//     return d;
//   };

//   // figure start/end from current period
//   const end = new Date(); end.setHours(0,0,0,0);
//   const start = new Date(end);
//   if (period === '1d') start.setDate(end.getDate() - 0);
//   else if (period === '7d') start.setDate(end.getDate() - 6);
//   else if (period === '30d') start.setDate(end.getDate() - 29);
//   else if (period === '90d') start.setDate(end.getDate() - 89);
//   else { start.setMonth(end.getMonth() - 11); start.setDate(1); } // 'all' → last 12 months as an example

//   // index incoming by bucket
//   const map = new Map();
//   pts.forEach(p => {
//     const k = +floor(p.x);
//     map.set(k, (map.get(k) || 0) + p.y);
//   });

//   // walk all buckets between start..end and fill zeros
//   const step = (d) => {
//     if (bucket === 'day')  d.setDate(d.getDate() + 1);
//     if (bucket === 'week') d.setDate(d.getDate() + 7);
//     if (bucket === 'month'){ d.setMonth(d.getMonth() + 1); d.setDate(1); }
//   };
//   const series = [];
//   for (let d = floor(start); +d <= +floor(end); step(d)){
//     const k = +d;
//     series.push({ x: new Date(k), y: map.get(k) || 0 });
//   }
//   return { series, bucket };
// }


// // DAILY SCANS (time series)
// const { series, bucket } = buildSeries(data.charts?.daily_scans || [], getState().period);
// drawTimeSeriesChart(ui.lineCanvas, series, { bucket });

// // TOOLS USAGE (bars with labels + hover)
// const tu = (data.charts?.tools_usage || []);
// const labels = tu.map(t => t.tool || t.name || 'Tool');
// const values = tu.map(t => Number(t.count || 0));
// drawBarChartLabeled(ui.barCanvas, labels, values);
 




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
  cardsRow.append(cardTotal.el, cardRate.el, cardNew.el, cardScans.el);

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

function updateUI(data){
  setHeader({ subtitle: `Last updated ${new Date(data.computed_at).toLocaleString()}` });

  const c = data.cards || {};
  ui.cards.total.update({
    value: num(c.total_users?.value ?? 0),
    changeText: pct(c.total_users?.delta_vs_prev ?? 0),
    positive: (c.total_users?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.rate.update({
    value: pct((c.success_rate?.value ?? 0) * 100),
    changeText: pct(c.success_rate?.delta_vs_prev ?? 0),
    positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.newRegs.update({
    value: num(c.new_registrations?.value ?? 0),
    changeText: pct(c.new_registrations?.delta_vs_prev ?? 0),
    positive: (c.new_registrations?.delta_vs_prev ?? 0) >= 0,
  });
  ui.cards.scans.update({
    value: num(c.scan_count?.value ?? 0),
    changeText: pct(c.scan_count?.delta_vs_prev ?? 0),
    positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
  });

  // charts
  const period = getState().period;
  const { series, bucket } =
    buildSeries(data.charts?.daily_scans || [], period);
  drawTimeSeriesChart(ui.lineCanvas, series, { bucket });

  const tu = (data.charts?.tools_usage || []);
  const labels = tu.map(t => t.tool || t.name || 'Tool');
  const values = tu.map(t => Number(t.count || 0));
  drawBarChartLabeled(ui.barCanvas, labels, values);
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
