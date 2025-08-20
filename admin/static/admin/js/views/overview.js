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

import { el, qs } from "../lib/dom.js";
import { getState, setHeader, subscribe } from "../lib/state.js";
import { num, pct } from "../lib/format.js";
import { getOverview } from "../api/metrics.js";
import { createStatCard } from "../components/cards.js";
import { drawLineChart, drawBarChart } from "../components/charts.js";

let cleanup = [];
let ui = null; // hold DOM refs so we can update instead of re-creating

function onCleanup(fn) {
  cleanup.push(fn);
}
function clearCleanup() {
  cleanup.forEach((fn) => {
    try {
      fn();
    } catch {}
  });
  cleanup = [];
}

function buildSkeleton(root) {
  root.innerHTML = ""; // <-- ensure we never append twice
  const wrap = el("div", { class: "overview-wrap" });

  // cards row
  const cardsRow = el("div", {
    class: "cards-row",
    style:
      "display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;",
  });
  const cardTotal = createStatCard({ title: "Total Users" });
  const cardRate = createStatCard({ title: "Scan Success Rate" });
  const cardNew = createStatCard({ title: "New Registrations" });
  const cardScans = createStatCard({ title: "Scan Count" });
  cardsRow.append(cardTotal.el, cardRate.el, cardNew.el, cardScans.el);

  // charts row
  // const chartsRow = el("div", {
  //   class: "charts-row",
  //   style:
  //     "display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;",
  // });
  // const dailyBox = el("div", { class: "panel" }, el("h3", {}, "Daily Scans"));
  // const toolsBox = el("div", { class: "panel" }, el("h3", {}, "Tools Usage"));
  // const lineCanvas = el("canvas", { width: 900, height: 320, id: "ov-daily" });
  // const barCanvas = el("canvas", { width: 900, height: 320, id: "ov-tools" });
  const chartsRow = el("div", { class: "charts-row" });
  const dailyBox = el(
    "div",
    { class: "chart-card" },
    el("h3", {}, "Daily Scans")
  );
  const toolsBox = el(
    "div",
    { class: "chart-card" },
    el("h3", {}, "Tools Usage")
  );
  const lineCanvas = el("canvas", { class: "chart-canvas", id: "ov-daily" });
  const barCanvas = el("canvas", { class: "chart-canvas", id: "ov-tools" });
  dailyBox.append(lineCanvas);
  toolsBox.append(barCanvas);
  chartsRow.append(dailyBox, toolsBox);

  wrap.append(cardsRow, chartsRow);
  root.append(wrap);

  ui = {
    cards: {
      total: cardTotal,
      rate: cardRate,
      newRegs: cardNew,
      scans: cardScans,
    },
    lineCanvas,
    barCanvas,
  };
}

async function refresh({ signal }) {
  const { period } = getState();
  const data = await getOverview(period, { signal }); // returns inner {computed_at, cards, charts}

  // header subtitle
  setHeader({
    subtitle: `Last updated ${new Date(data.computed_at).toLocaleString()}`,
  });

  // cards
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
  const dailyTotals = (data.charts?.daily_scans ?? []).map((d) => d.total ?? 0);
  drawLineChart(ui.lineCanvas, dailyTotals.length ? dailyTotals : [0]);

  const toolCounts = (data.charts?.tools_usage ?? []).map((t) => t.count ?? 0);
  drawBarChart(ui.barCanvas, toolCounts.length ? toolCounts : [0]);
}

export async function mount(root, { signal }) {
  // build once
  buildSkeleton(root);
  await refresh({ signal });

  // re-fetch when period changes (don’t rebuild DOM)
  const unsub = subscribe(["period"], () => refresh({ signal }));
  onCleanup(unsub);

  // re-fetch on the global 60s tick
  const onTick = () => refresh({ signal });
  window.addEventListener("admin:refresh", onTick);
  onCleanup(() => window.removeEventListener("admin:refresh", onTick));
  const onResize = () => {
    // just re-run refresh – prepCanvas will fit to new width
    refresh({ signal });
  };
  window.addEventListener("resize", onResize);
  onCleanup(() => window.removeEventListener("resize", onResize));
}

export function unmount() {
  clearCleanup();
  ui = null;
}
