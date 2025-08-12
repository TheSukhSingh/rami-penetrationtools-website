import { el } from '../lib/dom.js';
import { getState, subscribe, setHeader } from '../lib/state.js';
import { periodToRange } from '../lib/time.js';
import { num } from '../lib/format.js';
import { createStatCard } from '../components/cards.js';
import { drawLineChart, drawBarChart } from '../components/charts.js';

const sample = {
  scans: {
    '7d': [1200, 1400, 1100, 1600, 1800, 2100, 2156],
    '30d': Array.from({length: 30}, () => Math.floor(Math.random() * 1000) + 1000),
    '90d': Array.from({length: 90}, () => Math.floor(Math.random() * 1000) + 1000)
  },
  tools: [2847, 2156, 1923, 1654, 1432, 1287, 1098, 876, 654, 432]
};

let unsub = null;

export async function mount(root) {
  setHeader({ title: 'Dashboard Overview', subtitle: "Monitor and manage your Hunter's Terminal platform" });

  // --- KPIs
  const kpis = el('div', { class: 'metrics-grid' });
  const cUsers = createStatCard({ title: 'Total Users' });
  const cScans = createStatCard({ title: 'Total Scans' });
  const cToday = createStatCard({ title: "Today's Scans" });
  const cNew = createStatCard({ title: 'New Registrations' });
  [cUsers, cScans, cToday, cNew].forEach(c => kpis.appendChild(c.el));

  // --- Charts
  const charts = el('div', { class: 'charts-grid' },
    el('div', { class: 'chart-card glass' },
      el('div', { class: 'chart-header' }, el('h3', {}, 'Daily Scans')),
      el('div', { class: 'chart-container' }, el('canvas', { id: 'scansChart', width: 400, height: 200 }))
    ),
    el('div', { class: 'chart-card glass' },
      el('div', { class: 'chart-header' }, el('h3', {}, 'Tool Usage')),
      el('div', { class: 'chart-container' }, el('canvas', { id: 'toolsChart', width: 400, height: 200 }))
    )
  );

  // --- Activity (placeholder)
  const activity = el('div', { class: 'activity-section' },
    el('div', { class: 'activity-card glass' },
      el('div', { class: 'activity-header' }, el('h3', {}, 'Recent Activity')),
      el('div', { class: 'activity-list' }, el('div', { class: 'activity-item' }, el('div', { class: 'activity-content' }, 'Loading...')))
    )
  );

  root.append(kpis, charts, activity);

  // initial fill
  const s = getState();
  updateAll(s);

  // react to period changes
  unsub = subscribe(['period'], (st) => updateAll(st));

  function updateAll(st) {
    // demo numbers — hook up to real APIs later
    cUsers.update({ value: num(12847), changeText: '+12.5% from last month', positive: true });
    cScans.update({ value: num(89342), changeText: '+8.3% from last month', positive: true });
    cToday.update({ value: num(2156), changeText: '+15.2% from yesterday', positive: true });
    cNew.update({ value: num(156), changeText: '+22.1% from last week', positive: true });

    // charts
    const line = document.getElementById('scansChart');
    drawLineChart(line, sample.scans[st.period] || sample.scans['7d']);

    const bar = document.getElementById('toolsChart');
    drawBarChart(bar, sample.tools);

    // You already have period → range if you need to call APIs:
    const { start, end } = periodToRange(st.period);
    // e.g., http.getJSON('/metrics/kpis', { params: { start, end }, signal });
  }
}

export function unmount() {
  if (unsub) unsub(), unsub = null;
}
export default { mount, unmount };
