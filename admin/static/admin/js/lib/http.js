
const BASE = "/admin/api";

export async function getJSON(path, { params = {}, signal } = {}) {
  const url = withParams(new URL(BASE + path, location.origin), params);
  const res = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
  return parse(res);
}

export async function postJSON(path, body = {}, { params = {}, signal } = {}) {
  const url = withParams(new URL(BASE + path, location.origin), params);
  const headers = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const csrf = getCSRFToken();
  if (csrf) headers["X-CSRF-TOKEN"] = csrf;

  const res = await fetch(url, {
    method: "POST",
    headers,
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify(body),
    signal,
  });
  return parse(res);
}

export async function putJSON(path, body = {}, { params = {}, signal } = {}) {
  const url = withParams(new URL(BASE + path, location.origin), params);
  const headers = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const csrf = getCSRFToken();
  if (csrf) headers["X-CSRF-TOKEN"] = csrf;

  const res = await fetch(url, {
    method: "PUT",
    headers,
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify(body),
    signal,
  });
  return parse(res);
}

export async function delJSON(path, { params = {}, signal } = {}) {
  const url = withParams(new URL(BASE + path, location.origin), params);
  const headers = { Accept: "application/json" };
  const csrf = getCSRFToken();
  if (csrf) headers["X-CSRF-TOKEN"] = csrf;

  const res = await fetch(url, {
    method: "DELETE",
    headers,
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
  return parse(res);
}

/* ----------------------- helpers ----------------------- */

function withParams(url, params) {
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
  });
  return url;
}

async function parse(res) {
  // 204 No Content
  if (res.status === 204) return { ok: true, status: 204, data: null };
  const ct = res.headers.get("Content-Type") || "";
  let data = null;
  try {
    data = ct.includes("application/json") ? await res.json() : await res.text();
  } catch (_) {
    data = null;
  }
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function getCSRFToken() {
  // Prefer meta tag if you set it in base_admin.html
  const meta =
    document.querySelector('meta[name="csrf-token"]') ||
    document.querySelector('meta[name="csrf_token"]');
  if (meta && meta.content) return meta.content;

  // Fallback to common cookie names
  return (
    getCookie("csrf_access_token") ||
    getCookie("csrf_refresh_token") ||
    getCookie("csrf_token") ||
    ""
  );
}

function getCookie(name) {
  const m = document.cookie.match(
    new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)")
  );
  return m ? decodeURIComponent(m[1]) : "";
}
