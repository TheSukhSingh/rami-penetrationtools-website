(function (global) {
  // --- Utils ----------------------------------------------------
  // function getCookie(name) {
  //   // use existing global getCookie if you already defined one elsewhere
  //   if (typeof global.getCookie === "function") return global.getCookie(name);
  //   const m = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
  //   return m ? decodeURIComponent(m[2]) : null;
  // }
  function getMetaCSRF() {
    const t = document.querySelector('meta[name="csrf-token"]');
    return t ? t.getAttribute("content") : "";
  }
  function haveRefreshCSRF() {
    return !!getCookie("csrf_refresh_token");
  }

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
  async function refreshTokens({ silent = true } = {}) {
    if (refreshPromise) return refreshPromise;
    const csrf = getCookie("csrf_refresh_token");
    if (!csrf) {
      return { ok: false, status: 0 };
    }

    refreshPromise = fetch("/auth/refresh", {
      method: "POST",
      credentials: "include",
      // csrf: "refresh",
      // refresh: false,
      // silent,
      headers: {
        Accept: "application/json",
        "X-CSRF-TOKEN": csrf,
      },
    })
      .then((res) => ({ ok: res.ok, status: res.status }))
      .catch(() => ({ ok: false, status: 0 }))
      .finally(() => {
        refreshPromise = null;
      }); // <-- clear

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
      const csrf = getCookie(which) || getMetaCSRF();
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
    let res;
    try {
      // First attempt
      res = await fetch(url, opts);
    } catch (error) {
      console.log(`first fetch error - ${error}`);
    }

    // If unauthorized, try a single refresh then retry
    // if (res.status === 401) {
    //   try {
    //     await refreshTokens();
    //     if (needCsrf(method)) {
    //       const which =
    //         options?.csrf === "refresh"
    //           ? "csrf_refresh_token"
    //           : "csrf_access_token";
    //       const csrf = getCookie(which) || getMetaCSRF();
    //       if (csrf) headers.set("X-CSRF-TOKEN", csrf);
    //     }

    //     res = await fetch(url, opts);
    //   } catch {
    //     // refresh failed → surface 401, notify listeners
    //     window.dispatchEvent(new CustomEvent("auth:required"));
    //     return res;
    //   }
    // }

    if (!res) {
      // return a Response-like object so callers don’t explode
      return new Response("", { status: 0 });
    }

    // If unauthorized, optionally try a single refresh then retry
    if (res.status === 401) {
      // Caller can opt-out of refresh for this request
      if (options?.refresh === false) {
        return res;
      }

      // If we clearly don't have a refresh CSRF cookie, don't even try
      if (!haveRefreshCSRF()) {
        if (!options?.silent) {
          window.dispatchEvent(
            new CustomEvent("auth:required", { detail: { url } })
          );
        }
        return res; // keep original 401
      }

      // Try one refresh (uses refresh CSRF header internally)
      const refreshed = await refreshTokens({ silent: true });
      if (!refreshed.ok) {
        if (!options?.silent) {
          window.dispatchEvent(
            new CustomEvent("auth:required", { detail: { url } })
          );
        }
        return res; // keep original 401
      }

      // Re-attach CSRF and retry original request once
      if (needCsrf(method)) {
        const which =
          options?.csrf === "refresh"
            ? "csrf_refresh_token"
            : "csrf_access_token";
        const csrf = getCookie(which) || getMetaCSRF();
        if (csrf){
          headers.set("X-CSRF-TOKEN", csrf);
          headers.set("X-CSRFToken", csrf);
          headers.set("X-CSRF-Token", csrf);
          
        }
           opts.headers = headers;
      }
      res = await fetch(url, opts);
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

  async function getJSON(url, options = {}) {
    return fetchJSON(url, { method: "GET", ...options });
  }
  async function postJSON(url, body, options = {}) {
    return fetchJSON(url, { method: "POST", body, ...options });
  }
  async function putJSON(url, body, options = {}) {
    return fetchJSON(url, { method: "PUT", body, ...options });
  }
  async function delJSON(url, options = {}) {
    return fetchJSON(url, { method: "DELETE", ...options });
  }

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
