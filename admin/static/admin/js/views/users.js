// import { setHeader } from '../lib/state.js';

// export async function mount(root) {
//   setHeader({ title: 'Analytics Dashboard', subtitle: 'Advanced analytics and performance metrics' });
//   root.innerHTML = `
//     <div class="panel" style="padding:20px">
//       <h2>Users Dashboard</h2>
//       <p>Advanced users and reporting features coming soon...</p>
//     </div>`;
// }
// export function unmount() {}



import { setHeader, onRefresh, state } from "../lib/state.js";
import { el } from "../lib/dom.js";
import { num, pct } from "../lib/format.js";
import { getUsersSummary, listUsers, getUserDetail, deactivateUser, reactivateUser, setUserTier } from "../api/users.js";
import { makeCardRow } from "../components/cards.js";
import { makeTable } from "../components/table.js";
import { makeSearchBox } from "../components/searchbox.js";
import { makePaginator } from "../components/paginator.js";
import { toast } from "../components/toast.js";
import { confirm } from "../components/modal.js";

export default function mountUsers(root) {
  setHeader("Users", "Manage users, activity, tiers, and status");

  const cardRow = makeCardRow();
  const toolbar = el("div", { class: "panel toolbar" });
  const tableWrap = el("div", { class: "panel" });

  root.replaceChildren(cardRow.el, toolbar, tableWrap);


  // --- Cards ---
  // async function loadCards() {
  //   const rng = state.period; // "1d" | "7d" | "30d" | "90d" | "all-time"
  //   const data = await getUsersSummary(rng);
  //   const c = data.cards || {};

  //   const cards = [
  //     { key: "total_users", title: "Total Users", value: c.total_users?.value, delta: null },
  //     { key: "active_users", title: "Active Users", value: c.active_users?.value, delta: c.active_users?.delta_vs_prev },
  //     { key: "new_registrations", title: "New Registrations", value: c.new_registrations?.value, delta: c.new_registrations?.delta_vs_prev },
  //     { key: "deactivated_users", title: "Deactivated (New)", value: c.deactivated_users?.value, delta: c.deactivated_users?.delta_vs_prev },
  //   ];

  //   cardRow.update(cards.map(card => ({
  //     title: card.title,
  //     value: num(card.value || 0),
  //     // show delta chip only if not null
  //     delta: (card.delta === null || card.delta === undefined) ? null : pct(card.delta),
  //     // optional: up/down color handled inside cards.js
  //   })));
  // }

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

  // --- Table (search + pager) ---
  let page = 1, per_page = 20, q = "", sort = "-last_login_at";
  const search = makeSearchBox({
    placeholder: "Search by email, username, name...",
    onInput(value) {
      q = value;
      page = 1;
      loadTable();
    },
  });
  toolbar.replaceChildren(search.el);

  const table = makeTable({
    columns: [
      { key: "email", label: "Email", width: "28%" },
      { key: "username", label: "Username", width: "16%" },
      { key: "name", label: "Name", width: "18%" },
      { key: "last_login_at", label: "Last Login", width: "16%", format: v => v ? new Date(v).toLocaleString() : "—", sortable: true, sortKey: "last_login_at" },
      { key: "scan_count", label: "Scans", width: "8%", format: v => num(v || 0), sortable: true, sortKey: "scan_count" },
      { key: "tier", label: "Tier", width: "8%" },
      { key: "is_deactivated", label: "Status", width: "8%", format: v => v ? "Deactivated" : "Active" },
    ],
    onSort(nextSortKey, isDesc) {
      sort = `${isDesc ? "-" : ""}${nextSortKey}`;
      page = 1;
      loadTable();
    },
    onRowClick(row) {
      openUserDetail(row.id);
    },
  });
  tableWrap.replaceChildren(table.el);

  const pager = makePaginator({
    onPage(next) { page = next; loadTable(); },
  });
  tableWrap.appendChild(pager.el);

  // async function loadTable() {
  //   const items = await listUsers({ page, per_page, q, sort });
  //   table.setRows(items);
  //   // NOTE: if your /users API also returns meta.total, hook it into pager.setTotal(total)
  //   // For now, keep it simple until you extend /users to return meta in listUsers() wrapper.
  // }
  async function loadTable() {
  try {
    const items = await listUsers({ page, per_page, q, sort });
    table.setRows(items || []);
  } catch (e) {
    table.setRows([]);
    throw e;
  }
}

  // --- Detail drawer (simple modal for now) ---
  async function openUserDetail(id) {
    const d = await getUserDetail(id);
    const body = el("div", { class: "stack gap-2" },
      el("div", {}, el("strong", {}, d.email), ` (${d.username})`),
      el("div", {}, "Name: ", d.name || "—"),
      el("div", {}, "Tier: ", d.tier || "—"),
      el("div", {}, "Last login: ", d.last_login_at ? new Date(d.last_login_at).toLocaleString() : "—"),
      el("div", {}, "Scans: ", num(d.scan_count || 0)),
      el("hr"),
      el("div", {}, el("strong", {}, "Recent IPs")),
      el("ul", {},
        ...(d.ip_logs || []).map(log =>
          el("li", {}, `${log.ip} • ${log.device || log.user_agent || ""} • ${new Date(log.created_at).toLocaleString()}`)
        )
      )
    );

    const actions = [
      d.is_deactivated
        ? { label: "Reactivate", primary: true, onClick: async close => { await reactivateUser(id); toast.success("User reactivated"); await loadTable(); await loadCards(); close(); } }
        : { label: "Deactivate", danger: true, onClick: async close => {
            const ok = await confirm("Deactivate this user?");
            if (!ok) return;
            await deactivateUser(id);
            toast.success("User deactivated");
            await loadTable(); await loadCards();
            close();
          }}
      ,
      { label: "Set Tier…", onClick: async close => {
          const tier = prompt("Enter tier role name (e.g. tier_pro, tier_free):");
          if (!tier) return;
          await setUserTier(id, tier);
          toast.success("Tier updated");
          await loadTable();
          close();
        } },
      { label: "Close", onClick: close => close() },
    ];

    // simple modal factory you already have
    const { open } = await import("../components/modal.js");
    open({ title: "User Details", body, actions });
  }

  // --- Wire to global period + refresh ticker ---
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
