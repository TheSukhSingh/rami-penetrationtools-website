
// import { setHeader, onRefresh, state } from "../lib/state.js";
// import { el } from "../lib/dom.js";
// import { num, pct, ago } from "../lib/format.js";
// import { getUsersSummary, listUsers, getUserDetail, deactivateUser, reactivateUser, setUserTier } from "../api/users.js";
// import { makeCardRow } from "../components/cards.js";
// import { makeTable } from "../components/table.js";
// import { makeSearchBox } from "../components/searchbox.js";
// import { makePaginator } from "../components/paginator.js";
// import { toast } from "../components/toast.js";
// import { confirm } from "../components/modal.js";
// // ---- Card wrapper (header + table) ----
// const listCard = el("div", { class: "panel data-card" });
// const cardHeader = el("div", { class: "card-header" },
//   el("div", { class: "card-title" }, "User Management"),
//   el("div", { class: "card-actions" }) // we’ll place search here
// );
// const tableShell = el("div", { class: "table-wrap" }); // scrolling if tall
// listCard.replaceChildren(cardHeader, tableShell);

// root.replaceChildren(cardRow.el, listCard);

// // Search input in the header (no button)
// const search = makeSearchBox({
//   placeholder: "Search users…",
//   onInput(value) {
//     q = value;
//     page = 1;
//     loadTable();
//   },
// });
// cardHeader.querySelector(".card-actions").replaceChildren(search.el);

// // ---- Table (no Actions column; row click opens modal) ----
// const table = makeTable({
//   // add a class on the element so our CSS targets it
//   className: "data-table",
//   columns: [
//     { key: "user", label: "User", width: "44%", render: row => userCell(row) },
//     { key: "tier", label: "Tier", width: "12%", render: row => tierPill(row.tier) },
//     { key: "scan_count", label: "Scans", width: "12%", format: v => num(v || 0), sortable: true, sortKey: "scan_count" },
//     { key: "last_login_at", label: "Last Login", width: "16%", render: row => ago(row.last_login_at), sortable: true, sortKey: "last_login_at" },
//     { key: "is_deactivated", label: "Status", width: "12%", render: row => statusBadge(row.is_deactivated) },
//   ],
//   onSort(nextSortKey, isDesc) {
//     sort = `${isDesc ? "-" : ""}${nextSortKey}`;
//     page = 1;
//     loadTable();
//   },
//   onRowClick(row) {
//     openUserDetail(row.id);
//   },
// });
// tableShell.replaceChildren(table.el);

// // Paginator stays under the table inside the card
// const pager = makePaginator({
//   onPage(next) { page = next; loadTable(); },
// });
// listCard.appendChild(pager.el);

// function initialsFrom(emailOrName) {
//   const s = String(emailOrName || "").trim();
//   if (!s) return "U";
//   // prefer first two letters of local-part for email
//   const local = s.includes("@") ? s.split("@")[0] : s;
//   const letters = local.replace(/[^a-z0-9]/gi, "").toUpperCase();
//   return (letters[0] || "U") + (letters[1] || "");
// }
// function userCell(row) {
//   return el("div", { class: "user-cell" },
//     el("div", { class: "user-avatar" }, initialsFrom(row.email || row.username || row.name)),
//     el("div", { class: "user-info" },
//       el("div", { class: "user-email" }, row.email || "—"),
//       el("div", { class: "user-subtle" }, row.username ? `@${row.username}` : "—")
//     )
//   );
// }
// function tierPill(tier) {
//   const t = String(tier || "").toLowerCase();
//   const isPro = t.includes("pro");
//   const label = isPro ? "PRO" : "BASIC";
//   return el("span", { class: `pill ${isPro ? "pill-pro" : "pill-basic"}` }, label);
// }
// function statusBadge(deactivated) {
//   return el("span", { class: `badge ${deactivated ? "badge-deactivated" : "badge-active"}` },
//     deactivated ? "DEACTIVATED" : "ACTIVE"
//   );
// }


// export default function mountUsers(root) {
//   setHeader("Users", "Manage users, activity, tiers, and status");

//   const cardRow = makeCardRow();
//   const toolbar = el("div", { class: "panel toolbar" });
//   const tableWrap = el("div", { class: "panel" });

//   root.replaceChildren(cardRow.el, toolbar, tableWrap);

//   async function loadCards() {
//   try {
//     const rng = state.period;
//     const data = await getUsersSummary(rng);
//     const c = data.cards || {};
//     const cards = [
//       { title: "Total Users", value: num(c.total_users?.value || 0), delta: null },
//       { title: "Active Users", value: num(c.active_users?.value || 0), delta: c.active_users?.delta_vs_prev },
//       { title: "New Registrations", value: num(c.new_registrations?.value || 0), delta: c.new_registrations?.delta_vs_prev },
//       { title: "Deactivated (New)", value: num(c.deactivated_users?.value || 0), delta: c.deactivated_users?.delta_vs_prev },
//     ];
//     cardRow.update(cards.map(x => ({ title: x.title, value: x.value, delta: x.delta == null ? null : x.delta })));
//   } catch (e) {
//     cardRow.update([
//       { title: "Total Users", value: "—", delta: null },
//       { title: "Active Users", value: "—", delta: null },
//       { title: "New Registrations", value: "—", delta: null },
//       { title: "Deactivated (New)", value: "—", delta: null },
//     ]);
//     throw e;
//   }
// }

//   // --- Table (search + pager) ---
//   let page = 1, per_page = 20, q = "", sort = "-last_login_at";
//   const search = makeSearchBox({
//     placeholder: "Search by email, username, name...",
//     onInput(value) {
//       q = value;
//       page = 1;
//       loadTable();
//     },
//   });
//   toolbar.replaceChildren(search.el);

//   const table = makeTable({
//     columns: [
//       { key: "email", label: "Email", width: "28%" },
//       { key: "username", label: "Username", width: "16%" },
//       { key: "name", label: "Name", width: "18%" },
//       { key: "last_login_at", label: "Last Login", width: "16%", format: v => v ? new Date(v).toLocaleString() : "—", sortable: true, sortKey: "last_login_at" },
//       { key: "scan_count", label: "Scans", width: "8%", format: v => num(v || 0), sortable: true, sortKey: "scan_count" },
//       { key: "tier", label: "Tier", width: "8%" },
//       { key: "is_deactivated", label: "Status", width: "8%", format: v => v ? "Deactivated" : "Active" },
//     ],
//     onSort(nextSortKey, isDesc) {
//       sort = `${isDesc ? "-" : ""}${nextSortKey}`;
//       page = 1;
//       loadTable();
//     },
//     onRowClick(row) {
//       openUserDetail(row.id);
//     },
//   });
//   tableWrap.replaceChildren(table.el);

//   const pager = makePaginator({
//     onPage(next) { page = next; loadTable(); },
//   });
//   tableWrap.appendChild(pager.el);


//   async function loadTable() {
//   try {
//     const items = await listUsers({ page, per_page, q, sort });
//     table.setRows(items || []);
//   } catch (e) {
//     table.setRows([]);
//     throw e;
//   }
// }
// function roField(label, value) {
//   return el("div", { class: "form-row" },
//     el("div", { class: "form-label" }, label),
//     el("input", {
//       class: "form-input",
//       value: value == null || value === "" ? "—" : String(value),
//       disabled: true,
//       readOnly: true,
//     })
//   );
// }

// function roTextArea(label, value) {
//   return el("div", { class: "form-row" },
//     el("div", { class: "form-label" }, label),
//     el("textarea", {
//       class: "form-input",
//       disabled: true,
//       readOnly: true,
//       rows: 3,
//     }, value == null || value === "" ? "—" : String(value))
//   );
// }

// function roSwitch(label, checked, onChange) {
//   return el("div", { class: "form-row" },
//     el("div", { class: "form-label" }, label),
//     el("label", { class: "switch" },
//       el("input", {
//         type: "checkbox",
//         checked: !!checked,
//         onChange: (e) => onChange?.(e.target.checked),
//       }),
//       el("span", { class: "switch-ui" })
//     )
//   );
// }


// async function openUserDetail(id) {
//   const d = await getUserDetail(id);

//   const body = el("form", {
//     class: "stack gap-3 readonly-form",
//     onSubmit: (e) => e.preventDefault(),
//   },
//     roField("Username", d.username || "—"),
//     roField("Name", d.name || "—"),
//     roField("Email", d.email),
//     roSwitch("Email Verified", d.email_verified, async (val) => {
//     try { await setUserEmailVerified(id, val); toast.success(val ? "Marked verified" : "Marked unverified"); }
//     catch (e) { toast.error(e?.message || "Failed"); }
//   }),
//     // Account meta
//     roField("Tier", d.tier || "—Basic—"),
//   roField("Roles", (d.roles || []).join(", ") || "roles"),
//     roField("Status", d.is_deactivated ? "Deactivated" : "Active"),
//   roSwitch("Blocked", d.is_blocked, async (val) => {
//     try { await setUserBlocked(id, val); toast.success(val ? "User blocked" : "User unblocked"); await loadTable(); }
//     catch (e) { toast.error(e?.message || "Failed"); }
//   }),
//   roField("Scans", num(d.scan_count || 0)),
//     roField("Last Login", d.last_login_at ? new Date(d.last_login_at).toLocaleString() : "—"),
//     roField("Created At", d.created_at ? new Date(d.created_at).toLocaleString() : "—"),

//     // Usage

//     // Recent IPs (table-like list)
//     el("div", { class: "form-section" },
//       el("div", { class: "form-label" }, "Recent IPs"),
//       (d.ip_logs && d.ip_logs.length)
//         ? el("div", { class: "ip-table" },
//             el("div", { class: "ip-row ip-head" },
//               el("div", { class: "ip-cell" }, "IP"),
//               el("div", { class: "ip-cell" }, "Device / UA"),
//               el("div", { class: "ip-cell" }, "When"),
//             ),
//             // ↓↓↓ this line was `)))` before — remove one `)` so it’s just `))`
//             ...d.ip_logs.map(log => el("div", { class: "ip-row" },
//               el("div", { class: "ip-cell" }, log.ip || "—"),
//               el("div", { class: "ip-cell" }, log.device || log.user_agent || "—"),
//               el("div", { class: "ip-cell" }, log.created_at ? new Date(log.created_at).toLocaleString() : "—"),
//             ))
//           )
//         : el("div", { class: "ip-empty" }, "—")
//     ),
//   );
// const wrapper = el("div", {
//   style: {
//     minWidth: "70vw",         
//     maxWidth: "1200px",      
//     width: "100%",
//   }
// }, body);

//   const actions = [
//     { label: "View Scans", onClick: () => navigate(`/admin/scans?user=${id}`) },
//     d.is_deactivated
//       ? { label: "Reactivate", primary: true, onClick: async close => { await reactivateUser(id); toast.success("User reactivated"); await loadTable(); await loadCards(); close(); } }
//       : { label: "Deactivate", danger: true, onClick: async close => {
//           const ok = await confirm("Deactivate this user?");
//           if (!ok) return;
//           await deactivateUser(id);
//           toast.success("User deactivated");
//           await loadTable(); await loadCards();
//           close();
//         }},
//     { label: "Set Tier…", onClick: async close => {
//         const tier = prompt("Enter tier role name (e.g. tier_pro, tier_free):");
//         if (!tier) return;
//         await setUserTier(id, tier);
//         toast.success("Tier updated");
//         await loadTable();
//         close();
//       } },
//     { label: "Close", onClick: close => close() },
//   ];

//   const { open } = await import("../components/modal.js");
//   open({ title: "User Details", body: wrapper, actions });
// }

//   // --- Wire to global period + refresh ticker ---
// async function refresh() {
//   try {
//     await Promise.all([loadCards(), loadTable()]);
//   } catch (err) {
//     console.error(err);
//     toast.error(err?.data?.message || err?.message || "Failed to load Users data");
//   }
// }
//   refresh();

//   onRefresh(refresh);                
//   state.subscribe("period", refresh);
// }
























// admin/static/admin/js/views/users.js

// import { setHeader, onRefresh, state } from "../lib/state.js";
// import { navigate } from "../router.js";
// import { el } from "../lib/dom.js";
// import { num, pct, ago } from "../lib/format.js";
// import {
//   getUsersSummary,
//   listUsers,
//   getUserDetail,
//   deactivateUser,
//   reactivateUser,
//   setUserTier,
//   setUserBlocked,
//   setUserEmailVerified,
// } from "../api/users.js";
// import { makeCardRow } from "../components/cards.js";
// import { makeTable } from "../components/table.js";
// import { makeSearchBox } from "../components/searchbox.js";
// import { makePaginator } from "../components/paginator.js";
// import { toast } from "../components/toast.js";
// import { confirm } from "../components/modal.js";

// /* ---------- helpers ---------- */

// function initialsFrom(emailOrName) {
//   const s = String(emailOrName || "").trim();
//   if (!s) return "U";
//   const local = s.includes("@") ? s.split("@")[0] : s;
//   const letters = local.replace(/[^a-z0-9]/gi, "").toUpperCase();
//   return (letters[0] || "U") + (letters[1] || "");
// }

// function userCell(row) {
//   return el("div", { class: "user-cell" },
//     el("div", { class: "user-avatar" }, initialsFrom(row.email || row.username || row.name)),
//     el("div", { class: "user-info" },
//       el("div", { class: "user-email" }, row.email || "—"),
//       el("div", { class: "user-subtle" }, row.username ? `@${row.username}` : "—"),
//     ),
//   );
// }

// function tierPill(tier) {
//   const t = String(tier || "").toLowerCase();
//   const isPro = t.includes("pro");
//   const label = isPro ? "PRO" : "BASIC";
//   return el("span", { class: `pill ${isPro ? "pill-pro" : "pill-basic"}` }, label);
// }

// function statusBadge(deactivated) {
//   return el("span", { class: `badge ${deactivated ? "badge-deactivated" : "badge-active"}` },
//     deactivated ? "DEACTIVATED" : "ACTIVE",
//   );
// }

// function roField(label, value) {
//   return el("div", { class: "form-row" },
//     el("div", { class: "form-label" }, label),
//     el("input", {
//       class: "form-input",
//       value: value == null || value === "" ? "—" : String(value),
//       disabled: true,
//       readOnly: true,
//     }),
//   );
// }

// function roTextArea(label, value) {
//   return el("div", { class: "form-row" },
//     el("div", { class: "form-label" }, label),
//     el("textarea", {
//       class: "form-input",
//       disabled: true,
//       readOnly: true,
//       rows: 3,
//     }, value == null || value === "" ? "—" : String(value)),
//   );
// }

// function roSwitch(label, checked, onChange) {
//   return el("div", { class: "form-row" },
//     el("div", { class: "form-label" }, label),
//     el("label", { class: "switch" },
//       el("input", {
//         type: "checkbox",
//         checked: !!checked,
//         onChange: (e) => onChange?.(e.target.checked),
//       }),
//       el("span", { class: "switch-ui" }),
//     ),
//   );
// }

// /* ---------- view ---------- */

// export default function mountUsers(root) {
//   setHeader("Users", "Manage users, activity, tiers, and status");

//   // KPI cards
//   const cardRow = makeCardRow();

//   // Data card (boxed) with header + table
//   const listCard = el("div", { class: "panel data-card" });
//   const cardHeader = el("div", { class: "card-header" },
//     el("div", { class: "card-title" }, "User Management"),
//     el("div", { class: "card-actions" }),
//   );
//   const tableShell = el("div", { class: "table-wrap" }); // scroll if tall
//   listCard.replaceChildren(cardHeader, tableShell);

//   // mount into root
//   root.replaceChildren(cardRow.el, listCard);

//   // Search in the header (no button)
//   let page = 1, per_page = 20, q = "", sort = "-last_login_at";
//   const search = makeSearchBox({
//     placeholder: "Search users…",
//     onInput(value) {
//       q = value;
//       page = 1;
//       loadTable();
//     },
//   });
//   cardHeader.querySelector(".card-actions").replaceChildren(search.el);

//   // Table (no Actions column; row click opens modal)
//   const table = makeTable({
//     className: "data-table",
//     columns: [
//       { key: "user", label: "User", width: "44%", render: row => userCell(row) },
//       { key: "tier", label: "Tier", width: "12%", render: row => tierPill(row.tier) },
//       { key: "scan_count", label: "Scans", width: "12%", format: v => num(v || 0), sortable: true, sortKey: "scan_count" },
//       { key: "last_login_at", label: "Last Login", width: "16%", render: row => ago(row.last_login_at), sortable: true, sortKey: "last_login_at" },
//       { key: "is_deactivated", label: "Status", width: "12%", render: row => statusBadge(row.is_deactivated) },
//     ],
//     onSort(nextSortKey, isDesc) {
//       sort = `${isDesc ? "-" : ""}${nextSortKey}`;
//       page = 1;
//       loadTable();
//     },
//     onRowClick(row) {
//       openUserDetail(row.id);
//     },
//   });
//   tableShell.replaceChildren(table.el);

//   // Paginator
//   const pager = makePaginator({
//     onPage(next) { page = next; loadTable(); },
//   });
//   listCard.appendChild(pager.el);

//   // ---- data loaders ----

//   async function loadCards() {
//     try {
//       const rng = state.period;
//       const data = await getUsersSummary(rng);
//       const c = data.cards || {};
//       const cards = [
//         { title: "Total Users", value: num(c.total_users?.value || 0), delta: null },
//         { title: "Active Users", value: num(c.active_users?.value || 0), delta: c.active_users?.delta_vs_prev },
//         { title: "New Registrations", value: num(c.new_registrations?.value || 0), delta: c.new_registrations?.delta_vs_prev },
//         { title: "Deactivated (New)", value: num(c.deactivated_users?.value || 0), delta: c.deactivated_users?.delta_vs_prev },
//       ];
//       cardRow.update(cards.map(x => ({ title: x.title, value: x.value, delta: x.delta == null ? null : x.delta })));
//     } catch (e) {
//       cardRow.update([
//         { title: "Total Users", value: "—", delta: null },
//         { title: "Active Users", value: "—", delta: null },
//         { title: "New Registrations", value: "—", delta: null },
//         { title: "Deactivated (New)", value: "—", delta: null },
//       ]);
//       throw e;
//     }
//   }

//   async function loadTable() {
//     try {
//       const items = await listUsers({ page, per_page, q, sort });
//       table.setRows(items || []);
//     } catch (e) {
//       table.setRows([]);
//       throw e;
//     }
//   }

//   // ---- user detail modal ----

//   async function openUserDetail(id) {
//     const d = await getUserDetail(id);

//     const body = el("form", {
//       class: "stack gap-3 readonly-form",
//       onSubmit: (e) => e.preventDefault(),
//     },
//       // Identity
//       roField("Username", d.username || "—"),
//       roField("Name", d.name || "—"),
//       roField("Email", d.email),

//       // Access & roles
//       roField("Tier", d.tier || "—"),
//       roField("Roles", (d.roles || []).join(", ") || "—"),
//       roField("Status", d.is_deactivated ? "Deactivated" : "Active"),
//       roSwitch("Blocked", d.is_blocked, async (val) => {
//         try { await setUserBlocked(id, val); toast.success(val ? "User blocked" : "User unblocked"); await loadTable(); }
//         catch (e) { toast.error(e?.message || "Failed to update blocked"); }
//       }),
//       roSwitch("Email Verified", d.email_verified, async (val) => {
//         try { await setUserEmailVerified(id, val); toast.success(val ? "Marked verified" : "Marked unverified"); }
//         catch (e) { toast.error(e?.message || "Failed to update email verification"); }
//       }),

//       // Activity & metadata
//       roField("Scans", num(d.scan_count || 0)),
//       roField("Last Login", d.last_login_at ? new Date(d.last_login_at).toLocaleString() : "—"),
//       roField("Created At", d.created_at ? new Date(d.created_at).toLocaleString() : "—"),

//       // Recent IPs
//       el("div", { class: "form-section" },
//         el("div", { class: "form-label" }, "Recent IPs"),
//         (d.ip_logs && d.ip_logs.length)
//           ? el("div", {
//               class: "ip-table",
//               style: { display: "grid", gridTemplateColumns: "1fr 2fr 1.2fr", gap: "8px 12px", width: "100%" }
//             },
//               el("div", { class: "ip-row ip-head" },
//                 el("div", { class: "ip-cell" }, "IP"),
//                 el("div", { class: "ip-cell" }, "Device / UA"),
//                 el("div", { class: "ip-cell" }, "When"),
//               ),
//               ...d.ip_logs.map(log => el("div", { class: "ip-row" },
//                 el("div", { class: "ip-cell" }, log.ip || "—"),
//                 el("div", { class: "ip-cell" }, log.device || log.user_agent || "—"),
//                 el("div", { class: "ip-cell" }, log.created_at ? new Date(log.created_at).toLocaleString() : "—"),
//               ))
//             )
//           : el("div", { class: "ip-empty" }, "—")
//       ),
//     );

//     const wrapper = el("div", {
//       style: { minWidth: "70vw", maxWidth: "1200px", width: "100%" }
//     }, body);

//     const actions = [
//       { label: "View Scans", onClick: () => navigate(`/admin/scans?user=${id}`) },
//       d.is_deactivated
//         ? { label: "Reactivate", primary: true, onClick: async close => { await reactivateUser(id); toast.success("User reactivated"); await loadTable(); await loadCards(); close(); } }
//         : { label: "Deactivate", danger: true, onClick: async close => {
//             const ok = await confirm("Deactivate this user?");
//             if (!ok) return;
//             await deactivateUser(id);
//             toast.success("User deactivated");
//             await loadTable(); await loadCards();
//             close();
//           }},
//       { label: "Set Tier…", onClick: async close => {
//           const tier = prompt("Enter tier role name (e.g. tier_pro, tier_free):");
//           if (!tier) return;
//           await setUserTier(id, tier);
//           toast.success("Tier updated");
//           await loadTable();
//           close();
//         } },
//       { label: "Close", onClick: close => close() },
//     ];

//     const { open } = await import("../components/modal.js");
//     open({ title: "User Details", body: wrapper, actions });
//   }

//   // refresh hooks
//   async function refresh() {
//     try {
//       await Promise.all([loadCards(), loadTable()]);
//     } catch (err) {
//       console.error(err);
//       toast.error(err?.data?.message || err?.message || "Failed to load Users data");
//     }
//   }

//   refresh();
//   onRefresh(refresh);
//   state.subscribe("period", refresh);
// }




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
  let page = 1, per_page = 20, q = "", sort = "-last_login_at";
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

  const pager = makePaginator({ onPage(next) { page = next; loadTable(); } });
  listCard.appendChild(pager.el);

  async function loadTable() {
    try {
      const items = await listUsers({ page, per_page, q, sort });
      table.setRows(items || []);
    } catch (e) {
      table.setRows([]);
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
