// ---------- helpers ----------
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const fmt = (ts) => ts ? new Date(ts).toLocaleString() : "—";

function getCookie(name) {
  // read cookie value (non-HttpOnly)
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}

function csrfHeader() {
  const token = getCookie("csrf_access_token");
  return token ? { "X-CSRF-TOKEN": token } : {};
}

async function jfetch(url, options = {}) {
  const opts = {
    credentials: "same-origin",
    headers: {
      ...(options.headers || {})
    },
    ...options
  };

  // Add CSRF on mutating methods
  const method = (opts.method || "GET").toUpperCase();
  const needsCsrf = ["POST", "PATCH", "PUT", "DELETE"].includes(method);
  if (needsCsrf && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = opts.headers["Content-Type"] || "application/json";
  }
  if (needsCsrf) Object.assign(opts.headers, csrfHeader());

  const res = await fetch(url, opts);
  let data = null;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  if (isJson) {
    data = await res.json().catch(() => null);
  } else {
    const text = await res.text();
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
  }

  if (!res.ok) {
    const msg = data?.message || data?.error || `${res.status} ${res.statusText}`;
    const err = new Error(msg);
    err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}

function setText(id, val) { const el = typeof id === "string" ? document.getElementById(id) : id; if (el) el.textContent = val ?? ""; }
function show(el, v=true){ (typeof el==="string" ? $(el) : el).hidden = !v; }

// ---------- API ----------
const API = {
  myTickets: () => jfetch("/support/my"),
  adminTickets: (params={}) => {
    const q = new URLSearchParams({ page: 1, per_page: 20, sort: "created_at", order: "desc", ...params });
    return jfetch(`/support/admin/tickets?${q}`);
  },
  ticket: (id) => jfetch(`/support/t/${id}`),
  newTicket: (payload) => jfetch("/support/new", { method: "POST", body: JSON.stringify(payload) }),
  reply: (id, body) => jfetch(`/support/t/${id}/reply`, { method: "POST", body: JSON.stringify({ body }) }),
  upload: (id, file, body) => {
    const fd = new FormData();
    if (file) fd.append("file", file);
    if (body) fd.append("body", body);
    return jfetch(`/support/t/${id}/upload`, { method: "POST", body: fd });
  },
  setStatus: (id, status) => jfetch(`/support/t/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  setPriority: (id, priority) => jfetch(`/support/t/${id}/priority`, { method: "PATCH", body: JSON.stringify({ priority }) }),
  assign: (id, assignee_user_id) => jfetch(`/support/t/${id}/assign`, { method: "PATCH", body: JSON.stringify({ assignee_user_id }) }),
  snippets: () => jfetch("/support/admin/snippets"),
  applySnippet: (id, snippet_id) => jfetch(`/support/t/${id}/apply-snippet`, { method: "POST", body: JSON.stringify({ snippet_id }) }),
};

// ---------- state ----------
const state = {
  admin: false,
  selectedId: null,
  my: [],
  adminList: [],
  snippets: [],
};

// ---------- UI: My Tickets ----------
const myTicketsEl = $("#myTickets");
const refreshMyBtn = $("#refreshMy");
const emptyStateEl = $("#emptyState");
const ticketHeaderEl = $("#ticketHeader");
const threadEl = $("#thread");
const messagesEl = $("#messages");

async function loadMyTickets() {
  try {
    const data = await API.myTickets();
    state.my = data.tickets || [];
    renderMyTickets();
    // if nothing selected, show empty
    if (!state.selectedId) {
      show(emptyStateEl, true);
      show(ticketHeaderEl, false);
      show(threadEl, false);
    }
  } catch (e) {
    $("#auth-hint").hidden = false;
    myTicketsEl.innerHTML = `<div class="muted small">${e.message}</div>`;
  }
}

function renderMyTickets() {
  myTicketsEl.innerHTML = "";
  if (!state.my.length) {
    myTicketsEl.innerHTML = `<div class="muted small">No tickets yet.</div>`;
    return;
  }
  state.my.forEach(t => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `
      <div><strong>${escapeHtml(t.subject)}</strong></div>
      <div class="meta">
        <span class="chip">${t.status}</span>
        <span class="chip">p:${t.priority}</span>
        <span class="chip">${fmt(t.updated_at)}</span>
      </div>
    `;
    div.addEventListener("click", () => selectTicket(t.id));
    myTicketsEl.appendChild(div);
  });
}

async function selectTicket(id) {
  state.selectedId = id;
  await refreshTicket();
  // If admin, show admin tools section now that we have a ticket selected
  if (state.admin) {
    $("#adminTicketTools").hidden = false;
    populateAdminControlsFromTicket();
  }
}

async function refreshTicket() {
  if (!state.selectedId) return;
  const data = await API.ticket(state.selectedId);
  // header
  setText("tSubject", data.ticket.subject);
  setText("tStatus", data.ticket.status);
  setText("tPriority", data.ticket.priority);
  setText("tId", data.ticket.id);
  setText("tUpdated", fmt(data.ticket.updated_at));
  show(ticketHeaderEl, true);
  show(emptyStateEl, false);

  // messages
  messagesEl.innerHTML = "";
  const msgs = data.messages || [];
  for (const m of msgs) {
    const li = document.createElement("li");
    li.className = "msg";
    const who = m.author_user_id != null ? `User #${m.author_user_id}` : "System";
    const atts = (m.attachments || []).map(a =>
      `<a class="att" href="/support/attachments/${a.id}/download">📎 ${escapeHtml(a.filename)} (${a.size}B)</a>`
    ).join("");
    li.innerHTML = `
      <div class="msg-head">
        <span class="chip">${m.visibility}</span>
        <span>${who}</span>
        <span class="muted">• ${fmt(m.created_at)}</span>
      </div>
      <div class="msg-body">${linkify(escapeHtml(m.body || ""))}</div>
      ${atts ? `<div class="atts">${atts}</div>` : ``}
    `;
    messagesEl.appendChild(li);
  }
  show(threadEl, true);
}

// ---------- UI: New Ticket ----------
$("#newTicketForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.currentTarget);
  const payload = {
    subject: (fd.get("subject") || "").toString().trim(),
    description: (fd.get("description") || "").toString().trim(),
    priority: (fd.get("priority") || "normal").toString(),
  };
  $("#newTicketMsg").textContent = "Creating…";
  try {
    const res = await API.newTicket(payload);
    $("#newTicketMsg").textContent = "Created!";
    await loadMyTickets();
    if (res?.ticket?.id) await selectTicket(res.ticket.id);
    e.currentTarget.reset();
  } catch (err) {
    $("#newTicketMsg").textContent = `Error: ${err.message}`;
  }
});

// ---------- UI: Reply + upload ----------
$("#replyForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedId) return;
  const form = e.currentTarget;
  const fd = new FormData(form);
  const body = (fd.get("body") || "").toString().trim();
  const file = fd.get("file");
  $("#replyMsg").textContent = "Sending…";
  try {
    if (file && file.size) {
      await API.upload(state.selectedId, file, body || undefined);
    } else {
      await API.reply(state.selectedId, body);
    }
    $("#replyMsg").textContent = "Sent!";
    form.reset();
    await refreshTicket();
  } catch (err) {
    $("#replyMsg").textContent = `Error: ${err.message}`;
  }
});

// ---------- Admin detection & tools ----------
async function detectAdmin() {
  try {
    const data = await API.adminTickets();
    state.admin = true;
    $("#adminPanel").hidden = false;
    renderAdmin(data);
    // preload snippets
    try {
      const s = await API.snippets();
      state.snippets = s.snippets || [];
      const sel = $("#admSnippetSel");
      sel.innerHTML = "";
      if (state.snippets.length === 0) {
        sel.innerHTML = `<option value="">(no snippets)</option>`;
      } else {
        for (const sn of state.snippets) {
          const opt = document.createElement("option");
          opt.value = sn.id;
          opt.textContent = sn.title;
          sel.appendChild(opt);
        }
      }
    } catch {}
  } catch {
    state.admin = false;
    $("#adminPanel").hidden = true;
  }
}

function renderAdmin(data) {
  // counts chips
  const c = data.counts || {};
  $("#adminCounts").innerHTML = Object.entries(c)
    .map(([k,v]) => `<span class="chip">${k}: ${v}</span>`).join("");

  // list tickets (page 1)
  state.adminList = data.tickets || [];
  const list = $("#adminTickets");
  list.innerHTML = "";
  state.adminList.forEach(t => {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `
      <div><strong>${escapeHtml(t.subject)}</strong></div>
      <div class="meta">
        <span class="chip">${t.status}</span>
        <span class="chip">p:${t.priority}</span>
        <span class="chip">#${t.id}</span>
      </div>`;
    div.addEventListener("click", async () => {
      await selectTicket(t.id);
      populateAdminControlsFromTicket(t);
    });
    list.appendChild(div);
  });
}

$("#adminFilterForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.currentTarget);
  const params = {};
  for (const [k,v] of fd.entries()) if (v) params[k]=v;
  try {
    const data = await API.adminTickets(params);
    renderAdmin(data);
  } catch (err) {
    $("#adminTickets").innerHTML = `<div class="muted small">${err.message}</div>`;
  }
});

function populateAdminControlsFromTicket(t = null) {
  // Try to use the preview ticket, else fetch from header text
  if (t) {
    $("#admStatusSel").value = t.status;
    $("#admPrioritySel").value = t.priority;
  } else {
    $("#admStatusSel").value = $("#tStatus").textContent || "open";
    $("#admPrioritySel").value = $("#tPriority").textContent || "normal";
  }
  $("#adminTicketTools").hidden = !state.selectedId;
}

$("#admSetStatus").addEventListener("click", async () => {
  if (!state.selectedId) return;
  const status = $("#admStatusSel").value;
  setText("adminActionMsg", "Updating status…");
  try {
    await API.setStatus(state.selectedId, status);
    await refreshTicket();
    setText("adminActionMsg", "Status updated.");
  } catch (err) {
    setText("adminActionMsg", `Error: ${err.message}`);
  }
});

$("#admSetPriority").addEventListener("click", async () => {
  if (!state.selectedId) return;
  const priority = $("#admPrioritySel").value;
  setText("adminActionMsg", "Updating priority…");
  try {
    await API.setPriority(state.selectedId, priority);
    await refreshTicket();
    setText("adminActionMsg", "Priority updated.");
  } catch (err) {
    setText("adminActionMsg", `Error: ${err.message}`);
  }
});

$("#admAssign").addEventListener("click", async () => {
  if (!state.selectedId) return;
  const idRaw = $("#admAssignId").value.trim();
  const assignee_user_id = parseInt(idRaw, 10);
  if (!(assignee_user_id > 0)) {
    setText("adminActionMsg", "Enter a valid user id.");
    return;
  }
  setText("adminActionMsg", "Assigning…");
  try {
    await API.assign(state.selectedId, assignee_user_id);
    await refreshTicket();
    setText("adminActionMsg", `Assigned to #${assignee_user_id}.`);
  } catch (err) {
    setText("adminActionMsg", `Error: ${err.message}`);
  }
});

$("#admApplySnippet").addEventListener("click", async () => {
  if (!state.selectedId) return;
  const sel = $("#admSnippetSel");
  const snippet_id = parseInt(sel.value, 10);
  if (!snippet_id) { setText("adminActionMsg","Pick a snippet."); return; }
  setText("adminActionMsg", "Applying snippet…");
  try {
    await API.applySnippet(state.selectedId, snippet_id);
    await refreshTicket();
    setText("adminActionMsg", "Snippet applied.");
  } catch (err) {
    setText("adminActionMsg", `Error: ${err.message}`);
  }
});

// ---------- tiny utils ----------
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[ch]));
}
function linkify(s) {
  // super-light linkifier
  return s.replace(/\bhttps?:\/\/[^\s)]+/g, url => `<a href="${url}" target="_blank" rel="noopener">${url}</a>`);
}

// ---------- boot ----------
$("#refreshMy").addEventListener("click", loadMyTickets);
$("#refreshAdmin").addEventListener("click", async () => {
  try { const data = await API.adminTickets(); renderAdmin(data); } catch {}
});

(async function boot(){
  await loadMyTickets();
  await detectAdmin();
})();
