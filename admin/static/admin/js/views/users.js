
import { setHeader, onRefresh, state } from "../lib/state.js";
import { el } from "../lib/dom.js";
import { num, pct, ago } from "../lib/format.js";
import { navigate } from "../router.js";
import {
  getUsersSummary,
  listUsers,
  getUserDetail,
  deactivateUser,
  reactivateUser,
  setUserTier,
} from "../api/users.js";
import { makeCardRow } from "../components/cards.js";
import { makeTable } from "../components/table.js";
import { makeSearchBox } from "../components/searchbox.js";
import { makePaginator } from "../components/paginator.js";
import { toast } from "../components/toast.js";
import { confirm } from "../components/modal.js";

// ---------- Small render helpers ----------
function initialsFrom(emailOrName) {
  const s = String(emailOrName || "").trim();
  if (!s) return "U";
  const local = s.includes("@") ? s.split("@")[0] : s;
  const letters = local.replace(/[^a-z0-9]/gi, "").toUpperCase();
  return (letters[0] || "U") + (letters[1] || "");
}

function userCell(row) {
  return el(
    "div",
    { class: "user-cell" },
    el("div", { class: "user-avatar" }, initialsFrom(row.email || row.username || row.name)),
    el(
      "div",
      { class: "user-info" },
      el("div", { class: "user-email" }, row.email || "—"),
      el("div", { class: "user-subtle" }, row.username ? `@${row.username}` : "—")
    )
  );
}

function tierPill(tier) {
  const t = String(tier || "").toLowerCase();
  const isPro = t.includes("pro");
  const label = isPro ? "PRO" : "BASIC";
  return el("span", { class: `pill ${isPro ? "pill-pro" : "pill-basic"}` }, label);
}

function statusBadge(deactivated) {
  return el(
    "span",
    { class: `badge ${deactivated ? "badge-deactivated" : "badge-active"}` },
    deactivated ? "DEACTIVATED" : "ACTIVE"
  );
}

// read-only input row
function roField(label, value) {
  return el(
    "div",
    { class: "form-row" },
    el("div", { class: "form-label" }, label),
    el("input", {
      class: "form-input",
      value: value == null || value === "" ? "—" : String(value),
      disabled: true,
      readOnly: true,
    })
  );
}

function roSwitch(label, checked, onChange) {
  return el(
    "div",
    { class: "form-row" },
    el("div", { class: "form-label" }, label),
    el(
      "label",
      { class: "switch" },
      el("input", {
        type: "checkbox",
        checked: !!checked,
        onChange: (e) => onChange?.(e.target.checked),
      }),
      el("span", { class: "switch-ui" })
    )
  );
}

// ---------- View ----------
export default function mountUsers(root) {
  setHeader("Users", "Manage users, activity, tiers, and status");

  const cardRow = makeCardRow();

  // Card wrapper like the demo (“glass” look is handled in CSS we add below)
  const listCard = el("div", { class: "panel data-card" });
  const cardHeader = el(
    "div",
    { class: "card-header" },
    el("div", { class: "card-title" }, "User Management"),
    el("div", { class: "card-actions" }) // search goes here
  );
  const tableShell = el("div", { class: "table-wrap" }); // scroll if tall
  listCard.replaceChildren(cardHeader, tableShell);

  root.replaceChildren(cardRow.el, listCard);

  // ---- Cards ----
  async function loadCards() {
    try {
      const rng = state.period;
      const data = await getUsersSummary(rng);
      const c = data.cards || {};
      const cards = [
        { title: "Total Users", value: num(c.total_users?.value || 0), delta: null },
        { title: "Active Users", value: num(c.active_users?.value || 0), delta: c.active_users?.delta_vs_prev },
        { title: "New Registrations", value: num(c.new_registrations?.value || 0), delta: c.new_registrations?.delta_vs_prev },
        { title: "Deactivated (New)", value: num(c.deactivated_users?.value || 0), delta: c.deactivated_users?.delta_vs_prev },
      ];
      cardRow.update(cards.map(x => ({ title: x.title, value: x.value, delta: x.delta == null ? null : x.delta })));
    } catch (e) {
      cardRow.update([
        { title: "Total Users", value: "—", delta: null },
        { title: "Active Users", value: "—", delta: null },
        { title: "New Registrations", value: "—", delta: null },
        { title: "Deactivated (New)", value: "—", delta: null },
      ]);
      throw e;
    }
  }

  // ---- Search (header, no button) ----
  let page = 1, per_page = 20, q = "", sort = "-last_login_at", hasMore = true;
  const search = makeSearchBox({
    placeholder: "Search users…",
    onInput(value) {
      q = value;
      page = 1;
      loadTable();
    },
  });
  cardHeader.querySelector(".card-actions").replaceChildren(search.el);

  // ---- Table (no actions column) ----
  const table = makeTable({
    className: "data-table",
    columns: [
      { key: "user", label: "User", width: "44%", render: row => userCell(row) },
      { key: "tier", label: "Tier", width: "12%", render: row => tierPill(row.tier) },
      { key: "scan_count", label: "Scans", width: "12%", format: v => num(v || 0), sortable: true, sortKey: "scan_count" },
      { key: "last_login_at", label: "Last Login", width: "16%", render: row => (row.last_login_at ? ago(row.last_login_at) : "—"), sortable: true, sortKey: "last_login_at" },
      { key: "is_deactivated", label: "Status", width: "12%", render: row => statusBadge(row.is_deactivated) },
    ],
    onSort(next, isDesc) {
      sort = `${isDesc ? "-" : ""}${next}`;
      page = 1;
      loadTable();
    },
    onRowClick(row) {
      openUserDetail(row.id);
    },
  });
  tableShell.replaceChildren(table.el);

const pager = makePaginator({
  onPage(next) {
    page = next;
    loadTable();
  },
});


  listCard.appendChild(pager.el);

async function loadTable() {
  try {
    // listUsers may return array OR { items, meta: { total } }
    const res = await listUsers({ page, per_page, q, sort });
    const items = Array.isArray(res) ? res : (res.items || []);
    const total = Array.isArray(res) ? undefined : (res.meta?.total ?? res.total);

    if (items.length === 0 && page > 1) {
      page -= 1;
      return loadTable();
    }

    table.setRows(items);

    if (typeof total === "number") {
      pager.setTotal(total, per_page, page);
    } else {
      const approxTotal = (page - 1) * per_page + items.length;
      pager.setTotal(approxTotal, per_page, page);
    }
  } catch (e) {
    table.setRows([]);
    pager.setTotal((page - 1) * per_page, per_page, page);
    throw e;
  }
}



  // ---- Detail modal (read-only fields) ----
  async function openUserDetail(id) {
    const d = await getUserDetail(id);

    const body = el(
      "form",
      { class: "stack gap-3 readonly-form", onSubmit: (e) => e.preventDefault() },
      // Identity
      roField("Username", d.username || "—"),
      roField("Name", d.name || "—"),
      roField("Email", d.email),

      // Account meta
      roField("Tier", d.tier || "BASIC"),
      roField("Status", d.is_deactivated ? "Deactivated" : "Active"),
      roSwitch("Blocked", d.is_blocked, async (val) => {
        try {
          // (optional) wire when you add endpoints:
          // await setUserBlocked(id, val);
          toast.success(val ? "User blocked (demo)" : "User unblocked (demo)");
          await loadTable();
        } catch (e) {
          toast.error(e?.message || "Failed");
        }
      }),
      roSwitch("Email Verified", d.email_verified, async (val) => {
        try {
          // (optional) wire when you add endpoints:
          // await setUserEmailVerified(id, val);
          toast.success(val ? "Marked verified (demo)" : "Marked unverified (demo)");
        } catch (e) {
          toast.error(e?.message || "Failed");
        }
      }),

      // Usage & timestamps
      roField("Scans", num(d.scan_count || 0)),
      roField("Last Login", d.last_login_at ? new Date(d.last_login_at).toLocaleString() : "—"),
      roField("Created At", d.created_at ? new Date(d.created_at).toLocaleString() : "—"),

      // IPs
      el(
        "div",
        { class: "form-section" },
        el("div", { class: "form-label" }, "Recent IPs"),
        (d.ip_logs && d.ip_logs.length)
          ? el(
              "div",
              { class: "ip-table" },
              el(
                "div",
                { class: "ip-row ip-head" },
                el("div", { class: "ip-cell" }, "IP"),
                el("div", { class: "ip-cell" }, "Device / UA"),
                el("div", { class: "ip-cell" }, "When"),
              ),
              ...d.ip_logs.map(log =>
                el(
                  "div",
                  { class: "ip-row" },
                  el("div", { class: "ip-cell" }, log.ip || "—"),
                  el("div", { class: "ip-cell" }, log.device || log.user_agent || "—"),
                  el("div", { class: "ip-cell" }, log.created_at ? new Date(log.created_at).toLocaleString() : "—"),
                )
              )
            )
          : el("div", { class: "ip-empty" }, "—")
      ),
    );

    const wrapper = el("div", { style: { minWidth: "70vw", maxWidth: "1200px", width: "100%" } }, body);

    const actions = [
      { label: "View Scans", onClick: () => navigate(`/admin/scans?user=${id}`) },
      d.is_deactivated
        ? { label: "Reactivate", primary: true, onClick: async close => { await reactivateUser(id); toast.success("User reactivated"); await loadTable(); await loadCards(); close(); } }
        : { label: "Deactivate", danger: true, onClick: async close => {
            const ok = await confirm("Deactivate this user?");
            if (!ok) return;
            await deactivateUser(id);
            toast.success("User deactivated");
            await loadTable(); await loadCards();
            close();
          }},
      { label: "Set Tier…", onClick: async close => {
          const tier = prompt("Enter tier role name (tier_pro or tier_basic):");
          if (!tier) return;
          await setUserTier(id, tier);
          toast.success("Tier updated");
          await loadTable();
          close();
        } },
      { label: "Close", onClick: close => close() },
    ];

    const { open } = await import("../components/modal.js");
    open({ title: "User Details", body: wrapper, actions });
  }

  async function refresh() {
    try {
      await Promise.all([loadCards(), loadTable()]);
    } catch (err) {
      console.error(err);
      toast.error(err?.data?.message || err?.message || "Failed to load Users data");
    }
  }
  refresh();

  onRefresh(refresh);
  state.subscribe("period", refresh);
}
