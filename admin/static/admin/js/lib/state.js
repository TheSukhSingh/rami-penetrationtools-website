const listeners = new Set();

const _state = {
  period: localStorage.getItem("admin.period") || "7d",
  pageTitle: "Dashboard Overview",
  pageSubtitle: "Monitor and manage your Hunter's Terminal platform",
};

export const state = new Proxy(
  {},
  { get: (_, k) => _state[k] }
);

export function initState() {
  notify();
}


export function subscribe(keys, fn) {
  const ks =
    keys == null
      ? null
      : Array.isArray(keys)
      ? new Set(keys)
      : new Set([keys]); // allow single string
  const rec = { keys: ks, fn };
  listeners.add(rec);
  return () => listeners.delete(rec);
}

export function setPeriod(period) {
  if (!period || _state.period === period) return;
  _state.period = period;
  localStorage.setItem("admin.period", period);
  notify(["period"]);
}

export function setHeader(titleOrObj, subtitle) {
  if (typeof titleOrObj === "object" && titleOrObj !== null) {
    const { title, subtitle: sub } = titleOrObj;
    if (title) _state.pageTitle = title;
    if (sub) _state.pageSubtitle = sub;
  } else {
    if (titleOrObj) _state.pageTitle = titleOrObj;
    if (subtitle) _state.pageSubtitle = subtitle;
  }
  notify(["pageTitle", "pageSubtitle"]);
}

export function getState() {
  return { ..._state };
}

export function onRefresh(fn) {
  const handler = () => fn();
  window.addEventListener("admin:refresh", handler);
  return () => window.removeEventListener("admin:refresh", handler);
}

function notify(changedKeys) {
  const snapshot = getState();
  listeners.forEach(({ keys, fn }) => {
    if (!keys || !changedKeys || changedKeys.some((k) => keys.has(k))) {
      fn(snapshot);
    }
  });
}
