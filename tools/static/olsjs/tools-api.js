// ---- tools api conveniences (prefixes) ----
window.ToolsAPI = {
  get:  (p, opts) => getJSON(`/tools/api${p}`, opts),
  post: (p, body, opts) => postJSON(`/tools/api${p}`, body, opts),
  put:  (p, body, opts) => putJSON(`/tools/api${p}`, body, opts),
  del:  (p, opts) => delJSON(`/tools/api${p}`, opts),
};

// ---- SSE helper (cookies auto-sent same-origin) ----
window.sse = function sse(path, { onEvent, onError, withSnapshot = true } = {}) {
  const es = new EventSource(path); // e.g. /tools/api/runs/123/events
  if (withSnapshot) {
    es.addEventListener("snapshot", ev => onEvent?.("snapshot", JSON.parse(ev.data)));
  }
  es.addEventListener("update",   ev => onEvent?.("update",   JSON.parse(ev.data)));
  es.onerror = (e) => onError?.(e);
  return () => es.close();
};
