function toQS(params = {}) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) v.forEach(x => q.append(k, x));
    else q.append(k, v);
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const API = {
  tools: () => getJSON("/tools/api/tools"),

  workflows: {
    list:   () => getJSON("/tools/api/workflows"),
    get:    (id) => getJSON(`/tools/api/workflows/${id}`),
    create: (payload) => postJSON("/tools/api/workflows", payload),
    update: (id, payload) => putJSON(`/tools/api/workflows/${id}`, payload),
    remove: (id) => delJSON(`/tools/api/workflows/${id}`),
    archive: (id) => postJSON(`/tools/api/workflows/${id}/archive`, {}),
    run:    (id) => postJSON(`/tools/api/workflows/${id}/run`, {}),
  },

  runs: {
    list:    (params = {}) => getJSON(`/tools/api/runs${toQS(params)}`),
    get:     (id) => getJSON(`/tools/api/runs/${id}`),
    summary: (id) => getJSON(`/tools/api/runs/${id}/summary`),
    pause:   (id) => postJSON(`/tools/api/runs/${id}/pause`, {}),
    resume:  (id) => postJSON(`/tools/api/runs/${id}/resume`, {}),
    cancel:  (id) => postJSON(`/tools/api/runs/${id}/cancel`, {}),
    retry:   (id, step_index) =>
               postJSON(`/tools/api/runs/${id}/retry`, step_index == null ? {} : { step_index }),
  },
};
export async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, { credentials: "include", ...opts });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function fetchToolsFlat() {
  return fetchJSON("/tools/api/tools-flat");
}

export function listWorkflows() {
  return fetchJSON("/tools/api/workflows");
}
export function getWorkflow(wfId) {
  return fetchJSON(`/tools/api/workflows/${wfId}`);
}
export function createWorkflow(payload) {
  return fetchJSON(`/tools/api/workflows`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export function saveWorkflow(wfId, payload) {
  return fetchJSON(`/tools/api/workflows/${wfId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveNodeConfig(wfId, nodeId, config) {
  const res = await fetchJSON(`/tools/api/workflows/${wfId}/nodes/${nodeId}/config`, {
    method: "POST",
    body: { config },
  });
  if (!res.ok) {
    throw new Error(res.data?.error?.message || "Failed to save node config");
  }
  // Prefer backend echo if present; otherwise return what we sent.
  return res.data?.config || config;
}

export function runWorkflow(wfId) {
  return fetchJSON(`/tools/api/workflows/${wfId}/run`, { method: "POST" });
}
export function getRun(runId) {
  return fetchJSON(`/tools/api/runs/${runId}`);
}
export function openRunEvents(runId) {
  return new EventSource(`/tools/api/runs/${runId}/events`);
}
