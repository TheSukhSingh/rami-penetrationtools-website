const listeners = new Set();
const state = {
  period: localStorage.getItem('admin.period') || '7d',
  pageTitle: 'Dashboard Overview',
  pageSubtitle: "Monitor and manage your Hunter's Terminal platform"
};

export function initState() {
  notify();
}

export function subscribe(keys, fn) {
  const rec = { keys: keys ? new Set(keys) : null, fn };
  listeners.add(rec);
  return () => listeners.delete(rec);
}

export function setPeriod(period) {
  if (!period || state.period === period) return;
  state.period = period;
  localStorage.setItem('admin.period', period);
  notify(['period']);
}

export function setHeader({ title, subtitle }) {
  if (title) state.pageTitle = title;
  if (subtitle) state.pageSubtitle = subtitle;
  notify(['pageTitle','pageSubtitle']);
}

export function getState() { return { ...state }; }

function notify(changedKeys) {
  const snapshot = getState();
  listeners.forEach(({ keys, fn }) => {
    if (!keys || !changedKeys || changedKeys.some(k => keys.has(k))) fn(snapshot);
  });
}
