(function (global) {
  // --- Utils ----------------------------------------------------
  // function getCookie(name) {
  //   // use existing global getCookie if you already defined one elsewhere
  //   if (typeof global.getCookie === "function") return global.getCookie(name);
  //   const m = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
  //   return m ? decodeURIComponent(m[2]) : null;
  // }

  function getCookie(name) {
    // Prefer the shared helper from requesting.js (decodes values)
    if (
      window &&
      typeof window.getCookie === "function" &&
      window.getCookie !== getCookie
    ) {
      return window.getCookie(name);
    }
    const m = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : null;
  }

  function needCsrf(method) {
    method = (method || "GET").toUpperCase();
    return !["GET", "HEAD", "OPTIONS"].includes(method);
  }

  function isFormData(body) {
    return typeof FormData !== "undefined" && body instanceof FormData;
  }

  // --- Refresh queue (single-flight) ----------------------------
  let refreshPromise = null;
  async function refreshTokens() {
    if (!refreshPromise) {
      refreshPromise = fetch("/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-TOKEN": getCookie("csrf_refresh_token") || "" },
      })
        .then((r) => {
          if (!r.ok) throw new Error("refresh_failed");
          // cookies rotated server-side; nothing to return
        })
        .finally(() => {
          refreshPromise = null;
        });
    }
    return refreshPromise;
  }

  // --- Core fetch with CSRF + refresh retry ---------------------
  async function authFetch(url, options = {}) {
    const opts = { credentials: "include", ...options };
    const method = (opts.method || "GET").toUpperCase();
    const headers = new Headers(opts.headers || {});

    // Attach CSRF only for mutating requests
    if (needCsrf(method)) {
      const which =
        options?.csrf === "refresh"
          ? "csrf_refresh_token"
          : "csrf_access_token";
      const csrf = getCookie(which);
      if (csrf) headers.set("X-CSRF-TOKEN", csrf);
    }

    // If JSON body (not FormData), set header + stringify
    if (opts.body && !isFormData(opts.body) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
      if (typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
    }

    // Accept JSON by default
    if (!headers.has("Accept")) headers.set("Accept", "application/json");

    opts.headers = headers;

    // First attempt
    let res = await fetch(url, opts);

    // If unauthorized, try a single refresh then retry
    if (res.status === 401) {
      try {
        await refreshTokens();
        // rotate CSRF for retry
        if (needCsrf(method)) {
          const which =
            options?.csrf === "refresh"
              ? "csrf_refresh_token"
              : "csrf_access_token";
          const csrf = getCookie(which);
          if (csrf) headers.set("X-CSRF-TOKEN", csrf);
        }

        res = await fetch(url, opts);
      } catch {
        // refresh failed → surface 401, notify listeners
        window.dispatchEvent(new CustomEvent("auth:required"));
        return res;
      }
    }

    // 403/422 could indicate CSRF mismatch—optional hook
    if (res.status === 403 || res.status === 422) {
      window.dispatchEvent(
        new CustomEvent("auth:csrf_error", {
          detail: { url, status: res.status },
        })
      );
    }

    return res;
  }

  // --- JSON helpers ---------------------------------------------
  async function fetchJSON(url, options = {}) {
    const res = await authFetch(url, options);
    const contentType = res.headers.get("Content-Type") || "";
    let data = null;

    if (contentType.includes("application/json")) {
      try {
        data = await res.json();
      } catch (_) {
        data = null;
      }
    } else if (contentType.startsWith("text/")) {
      data = await res.text();
    } // (leave blobs/streams to callers)

    return {
      ok: res.ok,
      status: res.status,
      headers: res.headers,
      data,
      raw: res,
    };
  }

  const getJSON = (url, opts) => fetchJSON(url, { method: "GET", ...opts });
  const postJSON = (url, body, opts = {}) =>
    fetchJSON(url, { method: "POST", body, ...opts });
  const putJSON = (url, body, opts = {}) =>
    fetchJSON(url, { method: "PUT", body, ...opts });
  const delJSON = (url, body, opts = {}) =>
    fetchJSON(url, { method: "DELETE", body, ...opts });

  // Expose globals (non-module)
  global.authFetch = authFetch;
  global.fetchJSON = fetchJSON;
  global.getJSON = getJSON;
  global.postJSON = postJSON;
  global.putJSON = putJSON;
  global.delJSON = delJSON;
  global.refreshTokens = refreshTokens;

  // When a request needs re-auth (refresh failed), open login modal
  window.addEventListener("auth:required", () => showAuth("login"));

  // Optional: surface CSRF errors
  window.addEventListener("auth:csrf_error", (e) => {
    console.warn("CSRF error on", e.detail?.url, "status:", e.detail?.status);
  });
})(window);
