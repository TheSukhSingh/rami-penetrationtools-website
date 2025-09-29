/* tools/static/js/api.js */

(function (global) {
  function getMetaCSRF() {
    const t = document.querySelector('meta[name="csrf-token"]');
    return t ? t.getAttribute("content") : "";
  }
  function getCookie(name) {
    if (window && typeof window.getCookie === "function" && window.getCookie !== getCookie) {
      return window.getCookie(name);
    }
    const m = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : null;
  }
  function haveRefreshCSRF() {
    return !!getCookie("csrf_refresh_token");
  }
  function needCsrf(method) {
    method = (method || "GET").toUpperCase();
    return !["GET", "HEAD", "OPTIONS"].includes(method);
  }
  function isFormData(body) {
    return typeof FormData !== "undefined" && body instanceof FormData;
  }

  let refreshPromise = null;
  async function refreshTokens({ silent = true } = {}) {
    if (refreshPromise) return refreshPromise;
    const csrf = getCookie("csrf_refresh_token");
    if (!csrf) return { ok: false, status: 0 };

    refreshPromise = fetch("/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json", "X-CSRF-TOKEN": csrf },
    })
      .then((res) => ({ ok: res.ok, status: res.status }))
      .catch(() => ({ ok: false, status: 0 }))
      .finally(() => (refreshPromise = null));

    return refreshPromise;
  }

  async function authFetch(url, options = {}) {
    const opts = { credentials: "include", ...options };
    const method = (opts.method || "GET").toUpperCase();
    const headers = new Headers(opts.headers || {});

    if (needCsrf(method)) {
      const which = options?.csrf === "refresh" ? "csrf_refresh_token" : "csrf_access_token";
      const jwtCsrf = getCookie(which) || "";
      const wtfCsrf = getMetaCSRF() || "";
      if (jwtCsrf) headers.set("X-CSRF-TOKEN", jwtCsrf);
      if (wtfCsrf) headers.set("X-CSRFToken", wtfCsrf);
    }

    if (opts.body && !isFormData(opts.body) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
      if (typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
    }
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    opts.headers = headers;

    let res;
    try {
      res = await fetch(url, opts);
    } catch {
      return new Response("", { status: 0 });
    }

    if (res.status === 401) {
      if (options?.refresh === false) return res;
      if (!haveRefreshCSRF()) {
        if (!options?.silent) window.dispatchEvent(new CustomEvent("auth:required", { detail: { url } }));
        return res;
      }
      const refreshed = await refreshTokens({ silent: true });
      if (!refreshed.ok) {
        if (!options?.silent) window.dispatchEvent(new CustomEvent("auth:required", { detail: { url } }));
        return res;
      }
      if (needCsrf(method)) {
        const which = options?.csrf === "refresh" ? "csrf_refresh_token" : "csrf_access_token";
        const jwtCsrf = getCookie(which) || "";
        const wtfCsrf = getMetaCSRF() || "";
        if (jwtCsrf) headers.set("X-CSRF-TOKEN", jwtCsrf);
        if (wtfCsrf) headers.set("X-CSRFToken", wtfCsrf);
        opts.headers = headers;
      }
      res = await fetch(url, opts);
    }

    if (res.status === 403 || res.status === 422) {
      const ct = res.headers.get("Content-Type") || "";
      let body = null;
      if (ct.includes("application/json")) {
        try { body = await res.clone().json(); } catch {}
      }
      if (body && (String(body.msg||"").includes("csrf") || String(body.error||"").includes("csrf"))) {
        window.dispatchEvent(new CustomEvent("auth:csrf_error", { detail: { url, status: res.status } }));
      }
    }
    return res;
  }

  async function fetchJSON(url, options = {}) {
    const res = await authFetch(url, options);
    const ct = res.headers.get("Content-Type") || "";
    let data = null;
    if (ct.includes("application/json")) { try { data = await res.json(); } catch {} }
    else if (ct.startsWith("text/")) { data = await res.text(); }
    return { ok: res.ok, status: res.status, headers: res.headers, data, raw: res };
  }
  const getJSON = (url, o={}) => fetchJSON(url, { method: "GET", ...o });
  const postJSON = (url, body, o={}) => fetchJSON(url, { method: "POST", body, ...o });
  const putJSON = (url, body, o={}) => fetchJSON(url, { method: "PUT", body, ...o });
  const delJSON = (url, o={}) => fetchJSON(url, { method: "DELETE", ...o });

  global.authFetch = authFetch;
  global.fetchJSON = fetchJSON;
  global.getJSON = getJSON;
  global.postJSON = postJSON;
  global.putJSON = putJSON;
  global.delJSON = delJSON;
  global.refreshTokens = refreshTokens;

  window.addEventListener("auth:required", () => window?.showAuth?.("login"));
  window.addEventListener("auth:csrf_error", (e) => console.warn("CSRF error on", e.detail?.url, "status:", e.detail?.status));
})(window);

// ------------------------------------------------------------------
// API surface (the rest of your code imports: import { API } from "./api.js")
// ------------------------------------------------------------------
export const API = {
  tools: () => getJSON("/tools/api/tools"),
  workflows: {
    list: () => getJSON("/tools/api/workflows"),
    get: (id) => getJSON(`/tools/api/workflows/${encodeURIComponent(id)}`),
    create: (payload) => postJSON("/tools/api/workflows", payload),
    update: (id, payload) => putJSON(`/tools/api/workflows/${encodeURIComponent(id)}`, payload),
    del: (id) => delJSON(`/tools/api/workflows/${encodeURIComponent(id)}`),
  },
  runs: {
    start: (payload) => postJSON("/tools/api/run", payload),
    list: (wfId) => getJSON(`/tools/api/runs?workflow_id=${encodeURIComponent(wfId)}`),
    get: (runId) => getJSON(`/tools/api/runs/${encodeURIComponent(runId)}`),
  },
};
export default API;
