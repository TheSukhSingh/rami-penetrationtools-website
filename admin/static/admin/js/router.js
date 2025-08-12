let routes = {};
let current = null; // {name, api, abort}

export function initRouter(routeTable) {
  routes = routeTable;
  window.addEventListener('popstate', () => mountByPath(location.pathname, { replace: true }));
  mountByPath(location.pathname, { replace: true });
}

export function navigate(path) {
  if (location.pathname === path) return;
  history.pushState({}, '', path);
  mountByPath(path);
}

export function setActiveNav(path) {
  document.querySelectorAll('.nav-link[data-nav]').forEach(a => a.classList.remove('active'));
  const el = document.querySelector(`.nav-link[href="${path}"]`);
  if (el) el.classList.add('active');
}

async function mountByPath(path, { replace = false } = {}) {
  const name = routes[path] || routes['/admin'];
  if (current?.name === name) return;

  // unmount previous
  if (current?.api?.unmount) current.api.unmount();
  if (current?.abort) current.abort.abort();

  // clean root
  const root = document.getElementById('view-root');
  root.innerHTML = '';

  // mount new
  const ac = new AbortController();
  const api = await import(`./views/${name}.js`).then(m => m.default || m);
  await api.mount(root, { signal: ac.signal });

  current = { name, api, abort: ac };
  setActiveNav(path);
}
