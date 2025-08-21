// import { getJSON } from "../lib/http.js";

// export async function getScansSummary(period, { signal } = {}) {
//   const u = new URL("/admin/api/scans/summary", location.origin);
//   if (period) u.searchParams.set("range", period);
//   return getJSON(u.toString(), { method: "GET", signal }).then(r => r.data);
// }

// export async function listScans(params = {}, { signal } = {}) {
//   const u = new URL("/admin/api/scans", location.origin);
//   for (const [k, v] of Object.entries(params || {})) {
//     if (v !== undefined && v !== null && v !== "") u.searchParams.set(k, v);
//   }
//   return getJSON(u.toString(), { method: "GET", signal }).then(r => r.data);
// }

// export async function getScanDetail(id, { signal } = {}) {
//   return getJSON(`/admin/api/scans/${id}`, { method: "GET", signal }).then(r => r.data);
// }



// static/admin/js/api/scans.js
import { getJSON } from "../lib/http.js";

export async function getScansSummary(period, { signal } = {}) {
  const u = new URL("/admin/api/scans/summary", location.origin);
  if (period) u.searchParams.set("range", period);
  return getJSON(u.toString(), { method: "GET", signal }).then(r => r.data);
}

export async function listScans(params = {}, { signal } = {}) {
  const u = new URL("/admin/api/scans", location.origin);
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null && v !== "") u.searchParams.set(k, v);
  }
  return getJSON(u.toString(), { method: "GET", signal }).then(r => r.data);
}

export async function getScanDetail(id, { signal } = {}) {
  return getJSON(`/admin/api/scans/${id}`, { method: "GET", signal }).then(r => r.data);
}
