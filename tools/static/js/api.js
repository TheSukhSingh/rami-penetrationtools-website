export const API = {
  tools: () => getJSON('/tools/api/tools'),
  workflows: {
    list:   () => getJSON('/tools/api/workflows'),
    get:    (id) => getJSON(`/tools/api/workflows/${id}`),
    create: (payload) => postJSON('/tools/api/workflows', payload),
    update: (id, payload) => putJSON(`/tools/api/workflows/${id}`, payload),
    remove: (id) => delJSON(`/tools/api/workflows/${id}`),
    run:    (id) => postJSON(`/tools/api/workflows/${id}/run`, {}),
  },
  runs: {
    get:     (id) => getJSON(`/tools/api/runs/${id}`),
    summary: (id) => getJSON(`/tools/api/runs/${id}/summary`),
    pause:   (id) => postJSON(`/tools/api/runs/${id}/pause`, {}),
    resume:  (id) => postJSON(`/tools/api/runs/${id}/resume`, {}),
    cancel:  (id) => postJSON(`/tools/api/runs/${id}/cancel`, {}),
    retry:   (id, step_index) =>
                postJSON(`/tools/api/runs/${id}/retry`, { step_index }),
  },
};
// tools/static/js/api.js
export async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, { credentials: "include", ...opts });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Tools catalog (flattened with categories + schema)
export function fetchToolsFlat() {
  return fetchJSON("/tools/api/tools-flat");
}

// ── Workflows
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

// ── Node config (upsert)
export function saveNodeConfig(wfId, nodeId, config) {
  return fetchJSON(`/tools/api/workflows/${wfId}/nodes/${nodeId}/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
}

// ── Run + events
export function runWorkflow(wfId) {
  return fetchJSON(`/tools/api/workflows/${wfId}/run`, { method: "POST" });
}
export function getRun(runId) {
  return fetchJSON(`/tools/api/runs/${runId}`);
}
export function openRunEvents(runId) {
  // caller attaches 'message' handlers on returned EventSource
  return new EventSource(`/tools/api/runs/${runId}/events`);
}
