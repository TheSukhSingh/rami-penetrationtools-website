
import { setHeader, onRefresh, state } from "../lib/state.js";
import { el } from "../lib/dom.js";
import { num, pct, ago } from "../lib/format.js";
import { getScansSummary, listScans, getScanDetail } from "../api/scans.js";
import { makeCardRow } from "../components/cards.js";
import { makeTable } from "../components/table.js";
import { makeSearchBox } from "../components/searchbox.js";
import { makePaginator } from "../components/paginator.js";
import { toast } from "../components/toast.js";

// ---- helpers ----
function baselineLabel(period) {
  switch (period) {
    case "1d":  return "from yesterday";
    case "7d":  return "from previous week";
    case "30d": return "from previous month";
    case "90d": return "from previous quarter";
    default:    return "vs previous period";
  }
}
function truncate(s, n = 15) {
  if (!s) return "—";
  s = String(s);
  return s.length > n ? s.slice(0, n) + "…" : s;
}
function fmtDuration(ms) {
  if (ms == null) return "—";
  const sec = ms / 1000;
  if (sec < 1) return `${ms} ms`;
  if (sec < 60) return `${sec.toFixed(1)} s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

// ---- mini renderers to match Users UI ----
function initialsFromAny(u) {
  const s = String(u?.email || u?.username || u?.id || "").trim();
  if (!s) return "U";
  const local = s.includes("@") ? s.split("@")[0] : s;
  const letters = local.replace(/[^a-z0-9]/gi, "").toUpperCase();
  return (letters[0] || "U") + (letters[1] || "");
}
function userMini(u) {
  if (!u) return el("div", { class: "user-cell" }, "—");
  return el("div", { class: "user-cell" },
    el("div", { class: "user-avatar" }, initialsFromAny(u)),
    el("div", { class: "user-info" },
      el("div", { class: "user-email" }, u.email || u.username || String(u.id)),
      el("div", { class: "user-subtle" }, u.username ? `@${u.username}` : "—"),
    ),
  );
}
function statusBadge(status) {
  const ok = String(status || "").toLowerCase() === "success";
  return el("span", { class: `badge ${ok ? "badge-active" : "badge-deactivated"}` },
    ok ? "SUCCESS" : "FAILURE"
  );
}

// ---- main view ----
export default function mountScans(root) {
  setHeader("Scans", "History, success rate, and live activity");

  const cardRow = makeCardRow();

  // data-card shell (same pattern as users.js)
  const listCard = el("div", { class: "panel data-card" });
  const cardHeader = el(
    "div",
    { class: "card-header" },
    el("div", { class: "card-title" }, "Scan History"),
    el("div", { class: "card-actions" }) // search + filters live here
  );
  const tableShell = el("div", { class: "table-wrap" }); // scroll if tall
  listCard.replaceChildren(cardHeader, tableShell);

  root.replaceChildren(cardRow.el, listCard);

  // --- Cards ---
  async function loadCards() {
    try {
      const rng = state.period; // "1d" | "7d" | "30d" | "90d" | "all"
      const data = await getScansSummary(rng);
      const c = data.cards || {};
      const suffix = ` ${baselineLabel(rng)}`;

      const cards = [
        {
          title: "Total Scans",
          value: num(c.scan_count?.value ?? 0),
          delta: pct(c.scan_count?.delta_vs_prev ?? 0) + suffix,
          positive: (c.scan_count?.delta_vs_prev ?? 0) >= 0,
        },
        {
          title: "Active Scans",
          value: num(c.active_now?.value ?? 0),
          delta: "live now",
          positive: true,
        },
        {
          title: "Failed Scans",
          value: num(c.failures?.value ?? 0),
          // fewer failures is good
          delta: pct(c.failures?.delta_vs_prev ?? 0) + suffix,
          positive: (c.failures?.delta_vs_prev ?? 0) <= 0,
        },
        {
          title: "Success Rate",
          value: pct((c.success_rate?.value ?? 0) * 100),
          delta: pct(c.success_rate?.delta_vs_prev ?? 0) + suffix,
          positive: (c.success_rate?.delta_vs_prev ?? 0) >= 0,
        },
      ];

      cardRow.update(cards.map(x => ({
        title: x.title, value: x.value, delta: x.delta, positive: x.positive,
      })));
    } catch (e) {
      cardRow.update([
        { title: "Total Scans", value: "—", delta: null },
        { title: "Active Scans", value: "—", delta: null },
        { title: "Failed Scans", value: "—", delta: null },
        { title: "Success Rate", value: "—", delta: null },
      ]);
      throw e;
    }
  }

  // --- Table (search + filters in header) ---
  let page = 1, per_page = 20, q = "", tool = "", status = "", sort = "-scanned_at", hasMore = true;

  const search = makeSearchBox({
    placeholder: "Search (tool, command, file, user)…",
    onInput(value) { q = value; page = 1; loadTable(); },
  });

  const toolInput = el("input", {
    class: "search",
    type: "text",
    placeholder: "Tool (slug)",
    oninput: (e) => { tool = e.target.value.trim(); },
  });

  const statusSel = el("select", { class: "sel" },
    el("option", { value: "" }, "All statuses"),
    el("option", { value: "success" }, "Success"),
    el("option", { value: "failure" }, "Failure"),
  );
  statusSel.onchange = (e) => { status = e.target.value; };

  const applyBtn = el("button", { class: "btn" }, "Apply");
  applyBtn.onclick = () => { page = 1; loadTable(); };

  cardHeader.querySelector(".card-actions").replaceChildren(
    search.el, toolInput, statusSel, applyBtn
  );

  const table = makeTable({
    className: "data-table",
    columns: [
      { key: "id",         label: "Scan ID",  width: "12%" },
      { key: "user",       label: "User",     width: "22%", render: row => userMini(row.user) },
      { key: "tool",       label: "Tool",     width: "12%" },
      { key: "target",     label: "Target",   width: "22%", format: v => truncate(v, 18) },
      {
        key: "location",
        label: "Location",
        width: "16%",
        format: loc => (loc?.ip ? [loc.city, loc.country].filter(Boolean).join(", ") || loc.ip : "—"),
      },
      { key: "status",     label: "Status",   width: "10%", render: row => statusBadge(row.status) },
      { key: "scanned_at", label: "When",     width: "6%",  render: row => row.scanned_at ? ago(row.scanned_at) : "—", sortable: true, sortKey: "scanned_at" },
    ],
    onSort(nextSortKey, isDesc) {
      sort = `${isDesc ? "-" : ""}${nextSortKey}`;
      page = 1;
      loadTable();
    },
    onRowClick(row) {
      openScanDetail(row.id);
    },
  });
  tableShell.replaceChildren(table.el);

const pager = makePaginator({
  onPage(next) {
    const goingForward = next > page;
    if (goingForward && !hasMore) return; // block next if no more results
    page = next;
    loadTable();
  },
});



  listCard.appendChild(pager.el);

async function loadTable() {
  try {
    const res = await listScans({ page, per_page, q, tool, status, sort });

    const items = Array.isArray(res) ? res : (res.items || []);
    const total = Array.isArray(res) ? undefined : (res.meta?.total ?? res.total);

    table.setRows(items || []);

    if (typeof total === "number") {
      pager.setTotal(total, per_page, page);                 // updates buttons if your paginator supports it
      hasMore = page * per_page < total;                     // next exists only if more remain
    } else {
      hasMore = (items?.length || 0) === per_page;           // fallback: full page ⇒ maybe more
    }
  } catch (err) {
    console.error(err);
    table.setRows([]);
    hasMore = false;                                         // be conservative
    toast.error(err?.data?.message || err?.message || "Failed to load Scans");
  }
}

  // --- Detail modal (reuse modal component for consistency) ---
  async function openScanDetail(id) {
    try {
      const d = await getScanDetail(id);
      const pre = el("pre", { style: "max-height:60vh;overflow:auto;margin:0" }, JSON.stringify(d, null, 2));
      const box = el("div", { class: "panel", style: "max-width: 900px" },
        el("h3", {}, `Scan ${id}`),
        pre
      );
      const { open } = await import("../components/modal.js");
      open({
        title: "Scan Details",
        body: box,
        actions: [
          { label: "Close", onClick: close => close() },
        ],
      });
    } catch (err) {
      console.error(err);
      toast.error(err?.data?.message || err?.message || "Failed to load Scan detail");
    }
  }

  // --- Wire to global period + refresh ticker ---
  async function refresh() {
    try {
      await Promise.all([loadCards(), loadTable()]);
    } catch (err) {
      console.error(err);
      toast.error(err?.data?.message || err?.message || "Failed to load Scans");
    }
  }
  refresh();

  onRefresh(refresh);
  state.subscribe("period", refresh);
}
