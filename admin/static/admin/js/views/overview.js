import { el, qs } from '../lib/dom.js';
import { getState, setHeader, subscribe } from '../lib/state.js';
import { num, pct } from '../lib/format.js';
import { getOverview } from '../api/metrics.js';
import { createStatCard } from '../components/cards.js';
import { drawLineChart, drawBarChart } from '../components/charts.js';

let cleanupFns = [];

function clearCleanup() { cleanupFns.forEach(fn => { try { fn(); } catch {} }); cleanupFns = []; }

async function renderOnce(root, { signal }) {
  const { period } = getState();
  const payload = await getOverview(period, { signal });
  const data = payload?.data ?? payload;
  // --- header text (optional; you already show page title) ---
  setHeader({
    title: 'Dashboard Overview',
    subtitle: `Last updated ${new Date(data.computed_at).toLocaleString()}`
  });

  // --- cards ---
  const cardsWrap = el('div', { class: 'metrics-grid' });
  const cardUsers   = createStatCard({ title: 'Total Users' });
  const cardSR      = createStatCard({ title: 'Scan Success Rate' });
  const cardNewRegs = createStatCard({ title: 'New Registrations' });
  const cardScans   = createStatCard({ title: 'Scan Count' });
  cardsWrap.append(cardUsers.el, cardSR.el, cardNewRegs.el, cardScans.el);

  // --- charts ---
  const chartsWrap = el('div', { class: 'charts-grid' });
  const lineCanvas = el('canvas', { width: 800, height: 260, class: 'chart-canvas' });
  const barCanvas  = el('canvas', { width: 800, height: 260, class: 'chart-canvas' });
  chartsWrap.append(
    el('div', { class: 'chart-card glass' }, el('h3', {}, 'Daily Scans'), lineCanvas),
    el('div', { class: 'chart-card glass' }, el('h3', {}, 'Tools Usage'), barCanvas)
  );

  // mount layout (fresh each time mount() runs)
  root.append(cardsWrap, chartsWrap);

  // ---- populate cards ----
  const tu = data.cards.total_users;
  const sr = data.cards.success_rate;
  const nr = data.cards.new_registrations;
  const sc = data.cards.scan_count;

  cardUsers.update({
    value: num(tu.value || 0),
    changeText: pct(Math.round((tu.delta_vs_prev || 0) * 10) / 10),
    positive: (tu.delta_vs_prev || 0) >= 0
  });

  const srPct = Math.round(((sr.value || 0) * 1000)) / 10; // one decimal
  cardSR.update({
    value: `${srPct}%`,
    changeText: pct(Math.round((sr.delta_vs_prev || 0) * 10) / 10),
    positive: (sr.delta_vs_prev || 0) >= 0
  });

  cardNewRegs.update({
    value: num(nr.value || 0),
    changeText: pct(Math.round((nr.delta_vs_prev || 0) * 10) / 10),
    positive: (nr.delta_vs_prev || 0) >= 0
  });

  cardScans.update({
    value: num(sc.value || 0),
    changeText: pct(Math.round((sc.delta_vs_prev || 0) * 10) / 10),
    positive: (sc.delta_vs_prev || 0) >= 0
  });

  // ---- charts ----
  const daily = (data.charts?.daily_scans || []).map(d => d.total || 0);
  drawLineChart(lineCanvas, daily.length ? daily : [0]);

  const tools = (data.charts?.tools_usage || []).map(t => t.count || 0);
  drawBarChart(barCanvas, tools.length ? tools : [0]);

  // ---- optional: topbar live stat if you later add it to payload ----
  // const au = data.cards.active_users?.value;
  // if (au != null) { const elAU = qs('#stat-active-users'); if (elAU) elAU.textContent = num(au); }
}

async function refresh(root, { signal }) {
  // Replace only the dynamic numbers/charts; keep DOM stable for less flicker
  // Here we simply re-render the whole view for simplicity; you can optimize later.
  root.innerHTML = '';
  await renderOnce(root, { signal });
}

export async function mount(root, { signal }) {
  // initial paint
  await renderOnce(root, { signal });

  // re-fetch when global period changes
  const unsub = subscribe(['period'], () => refresh(root, { signal }));
  cleanupFns.push(unsub);

  // re-fetch on global tick
  const onTick = () => refresh(root, { signal });
  window.addEventListener('admin:refresh', onTick);
  cleanupFns.push(() => window.removeEventListener('admin:refresh', onTick));
}

export function unmount() {
  clearCleanup();
}
