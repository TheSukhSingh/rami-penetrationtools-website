const BASE = '/admin/api';

export async function getJSON(path, { params = {}, signal } = {}) {
  const url = new URL(BASE + path, location.origin);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  // const res = await fetch(url, { headers: { 'Accept': 'application/json' }, signal });

  const res = await fetch(url, {
    method: 'GET',
    headers: { 'Accept':'application/json'},
    credentials: 'same-origin',
    cache: 'no-store',
    signal
  })

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
