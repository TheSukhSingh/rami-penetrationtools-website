const BASE = '/api/admin';

export async function getJSON(path, { params = {}, signal } = {}) {
  const url = new URL(BASE + path, location.origin);
  Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url, { headers: { 'Accept': 'application/json' }, signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
