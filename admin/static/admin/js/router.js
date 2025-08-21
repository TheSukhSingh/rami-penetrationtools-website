// let routes = {};
// let current = null; // {name, api, abort}

// export function initRouter(routeTable) {
//   routes = routeTable;
//   window.addEventListener("popstate", () =>
//     mountByPath(location.pathname, { replace: true })
//   );
//   mountByPath(location.pathname, { replace: true });
// }

// export function navigate(path) {
//   if (location.pathname === path) return;
//   history.pushState({}, "", path);
//   mountByPath(path);
// }

// // export function setActiveNav(path) {
// //   document.querySelectorAll('.nav-link[data-nav]').forEach(a => a.classList.remove('active'));
// //   const el = document.querySelector(`.nav-link[href="${path}"]`);
// //   if (el) el.classList.add('active');
// // }

// export function setActiveNav(path) {
//   const clean = path.split("?")[0].replace(/\/$/, "") || "/admin";
//   document.querySelectorAll(".nav-link[data-nav]").forEach((a) => {
//     const href = a.getAttribute("href").split("?")[0].replace(/\/$/, "");
//     a.classList.toggle("active", href === clean);
//   });
// }

// async function mountByPath(path, { replace = false } = {}) {
//   const name = routes[path] || routes["/admin"];
//   if (current?.name === name) return;
//   if (replace) history.replaceState({}, "", path);

//   // unmount previous
//   if (current?.api?.unmount) current.api.unmount();
//   if (current?.abort) current.abort.abort();

//   // clean root
//   const root = document.getElementById("view-root");
//   root.innerHTML = "";

//   // mount new
//   const ac = new AbortController();
//   const api = await import(`./views/${name}.js`).then((m) => m.default || m);
//   try {
//     await api.mount(root, { signal: ac.signal }); // might throw on abort
//   } catch (err) {
//     const msg = String(err?.message || "").toLowerCase();
//     const name = String(err?.name || "").toLowerCase();
//     if (name !== "aborterror" && !msg.includes("abort")) {
//       // optional: surface real mount errors somewhere
//       console.error("mount failed:", err);
//     }
//   }
//   current = { name, api, abort: ac };
//   setActiveNav(path);
// }




let routes = {};
let current = null; // {name, api, abort, cleanup}

export function initRouter(routeTable) {
  routes = routeTable || {};
  window.addEventListener("popstate", () => mountByPath(location.pathname, { replace: true }));
  mountByPath(location.pathname, { replace: true });
}

export function navigate(path) {
  if (location.pathname === path) return;
  history.pushState({}, "", path);
  mountByPath(path);
}

export function setActiveNav(path) {
  const clean = (path || "").split("?")[0].replace(/\/$/, "") || "/admin";
  document.querySelectorAll(".nav-link[data-nav]").forEach((a) => {
    const href = (a.getAttribute("href") || "").split("?")[0].replace(/\/$/, "");
    a.classList.toggle("active", href === clean);
  });
}

async function mountByPath(path, { replace = false } = {}) {
  const name = routes[path] || routes["/admin"];
  if (!name) return;

  // no-op if same view
  if (current?.name === name) {
    setActiveNav(path);
    return;
  }
  if (replace) history.replaceState({}, "", path);

  // unmount previous
  try {
    if (typeof current?.cleanup === "function") current.cleanup();
    else if (typeof current?.api?.unmount === "function") current.api.unmount();
  } catch (e) {
    console.warn("unmount error:", e);
  }
  if (current?.abort) current.abort.abort();

  // clean root
  const root = document.getElementById("view-root");
  if (root) root.innerHTML = "";

  // mount new
  const ac = new AbortController();
  let api = null;
  let cleanup = null;

  try {
    const mod = await import(`./views/${name}.js`);
    api = mod.default || mod;

    // Support both shapes:
    // 1) default export is a function: (root, {signal}) => optional cleanup fn
    // 2) default export is an object with .mount(): returns optional cleanup fn
    let ret;
    if (typeof api === "function") {
      ret = await api(root, { signal: ac.signal });
    } else if (api && typeof api.mount === "function") {
      ret = await api.mount(root, { signal: ac.signal });
    } else {
      throw new Error(`View "${name}" must export a default function or { mount }`);
    }
    if (typeof ret === "function") cleanup = ret;
  } catch (err) {
    const msg = String(err?.message || "").toLowerCase();
    const en = String(err?.name || "").toLowerCase();
    if (en !== "aborterror" && !msg.includes("abort")) {
      console.error("mount failed:", err);
      // Show a friendly error in the view root
      if (root) root.innerHTML = `<div class="panel" style="padding:16px;color:#f66">Failed to load view: ${escapeHtml(err.message || err)}</div>`;
    }
  }

  current = { name, api, abort: ac, cleanup };
  setActiveNav(path);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
