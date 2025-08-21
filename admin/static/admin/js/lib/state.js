// const listeners = new Set();

// const _state = {
//   period: localStorage.getItem("admin.period") || "7d",
//   pageTitle: "Dashboard Overview",
//   pageSubtitle: "Monitor and manage your Hunter's Terminal platform",
// };

// export const state = new Proxy(
//   {},
//   { get: (_, k) => _state[k] }
// );

// export function initState() {
//   notify();
// }


// export function subscribe(keys, fn) {
//   const ks =
//     keys == null
//       ? null
//       : Array.isArray(keys)
//       ? new Set(keys)
//       : new Set([keys]); // allow single string
//   const rec = { keys: ks, fn };
//   listeners.add(rec);
//   return () => listeners.delete(rec);
// }

// export function setPeriod(period) {
//   if (!period || _state.period === period) return;
//   _state.period = period;
//   localStorage.setItem("admin.period", period);
//   notify(["period"]);
// }

// export function setHeader(titleOrObj, subtitle) {
//   if (typeof titleOrObj === "object" && titleOrObj !== null) {
//     const { title, subtitle: sub } = titleOrObj;
//     if (title) _state.pageTitle = title;
//     if (sub) _state.pageSubtitle = sub;
//   } else {
//     if (titleOrObj) _state.pageTitle = titleOrObj;
//     if (subtitle) _state.pageSubtitle = subtitle;
//   }
//   notify(["pageTitle", "pageSubtitle"]);
// }

// export function getState() {
//   return { ..._state };
// }

// export function onRefresh(fn) {
//   const handler = () => fn();
//   window.addEventListener("admin:refresh", handler);
//   return () => window.removeEventListener("admin:refresh", handler);
// }

// function notify(changedKeys) {
//   const snapshot = getState();
//   listeners.forEach(({ keys, fn }) => {
//     if (!keys || !changedKeys || changedKeys.some((k) => keys.has(k))) {
//       fn(snapshot);
//     }
//   });
// }




// admin/static/admin/js/lib/state.js

const listeners = new Set();

const _state = {
  period: localStorage.getItem("admin.period") || "7d",
  pageTitle: "Dashboard Overview",
  pageSubtitle: "Monitor and manage your Hunter's Terminal platform",
};

// live view AND back-compat method on it
export const state = {
  get period() { return _state.period; },
  get pageTitle() { return _state.pageTitle; },
  get pageSubtitle() { return _state.pageSubtitle; },
  // back-compat so views can call: state.subscribe(...)
  subscribe: (keys, fn) => subscribe(keys, fn),
};

export function initState() { notify(); }

/** Subscribe to specific keys or all (null/undefined). */
export function subscribe(keys, fn) {
  const ks = keys == null ? null : (Array.isArray(keys) ? new Set(keys) : new Set([keys]));
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

/** setHeader("Title", "Subtitle") OR setHeader({ title, subtitle }) */
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

export function getState() { return { ..._state }; }

/** Hook into admin refresh ticker (admin.js should dispatch 'admin:refresh'). */
export function onRefresh(fn) {
  const handler = () => fn();
  window.addEventListener("admin:refresh", handler);
  return () => window.removeEventListener("admin:refresh", handler);
}

function notify(changedKeys) {
  const snapshot = getState();
  listeners.forEach(({ keys, fn }) => {
    if (!keys || !changedKeys || changedKeys.some((k) => keys.has(k))) fn(snapshot);
  });
}
