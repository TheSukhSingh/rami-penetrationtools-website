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
