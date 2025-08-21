
export function makeTable({
  columns = [],
  onSort = null,
  onRowClick = null,
  className = "",          // ← NEW
} = {}) {
  // ---- DOM helpers ---------------------------------------------------------
  const $ = (tag, props = {}, ...kids) => {
    const el = document.createElement(tag);
    if (props && typeof props === "object") {
      for (const [k, v] of Object.entries(props)) {
        if (k === "class") el.className = v;
        else if (k === "style" && v && typeof v === "object") {
          Object.assign(el.style, v);
        } else if (k.startsWith("on") && typeof v === "function") {
          el.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (v !== undefined && v !== null) {
          el.setAttribute(k, v);
        }
      }
    }
    for (const kid of kids.flat()) {
      if (kid == null) continue;
      el.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    }
    return el;
  };

  // ---- State ---------------------------------------------------------------
  let rows = [];
  let sortKey = null;
  let sortDesc = false;

  const root = $("div", { class: "data-table-wrapper" });
if (className) {
  String(className)
    .split(/\s+/)
    .filter(Boolean)
    .forEach(c => root.classList.add(c));
}
  const table = $("table", { class: "data-table", role: "grid" });
  const thead = $("thead");
  const tbody = $("tbody");
  table.append(thead, tbody);

  root.appendChild(table);

  // ---- Render header -------------------------------------------------------
  function renderHeader() {
    thead.replaceChildren();

    const tr = $("tr");

    for (const col of columns) {
      const isSortable = !!col.sortable;
      const colSortKey = col.sortKey || col.key;

      const th = $("th", {
        class: [
          "dt-th",
          isSortable ? "sortable" : "",
          sortKey === colSortKey ? (sortDesc ? "sorted desc" : "sorted asc") : "",
        ].filter(Boolean).join(" "),
        scope: "col",
        role: "columnheader",
        style: col.width ? { width: col.width } : undefined,
        "aria-sort":
          sortKey === colSortKey ? (sortDesc ? "descending" : "ascending") : "none",
      });

      const label = $("span", { class: "dt-th-label" }, col.label || col.key);

      if (isSortable) {
        const btn = $(
          "button",
          {
            class: "dt-sort-btn",
            type: "button",
            onClick: () => {
              const nextKey = colSortKey;
              let nextDesc = false;
              if (sortKey === nextKey) {
                nextDesc = !sortDesc; // toggle
              } else {
                // default to DESC for dates/numbers; ASC otherwise (simple heuristic)
                nextDesc = guessDefaultDesc(col.key || "");
              }
              sortKey = nextKey;
              sortDesc = nextDesc;

              // re-render header to update indicators
              renderHeader();

              if (typeof onSort === "function") {
                onSort(nextKey, nextDesc);
              }
            },
          },
          label,
          $("span", {
            class: "dt-sort-indicator",
            "aria-hidden": "true",
            title: "Sort",
          }),
        );
        th.appendChild(btn);
      } else {
        th.appendChild(label);
      }

      tr.appendChild(th);
    }

    thead.appendChild(tr);
  }

  function guessDefaultDesc(key) {
    // If key looks like date/time/id/count/num -> default DESC
    const k = (key || "").toLowerCase();
    return (
      k.includes("date") ||
      k.includes("time") ||
      k.includes("at") ||
      k.includes("id") ||
      k.includes("count") ||
      k.includes("total") ||
      k.includes("num")
    );
  }

  // ---- Render rows ---------------------------------------------------------
  function renderRows() {
    tbody.replaceChildren();

    if (!rows || rows.length === 0) {
      const tr = $("tr", { class: "dt-empty-row" });
      const td = $("td", { class: "dt-empty-cell", colspan: String(columns.length) }, "No data");
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    for (const row of rows) {
      const tr = $("tr", {
        class: ["dt-row", onRowClick ? "clickable" : ""].filter(Boolean).join(" "),
        onClick: onRowClick ? () => onRowClick(row) : undefined,
        tabIndex: onRowClick ? "0" : undefined,
        role: "row",
      });

      for (const col of columns) {
        const raw = safeGet(row, col.key);
        // prefer a full-row renderer if provided, else fall back to formatter
        const content =
          typeof col.render === "function"
            ? col.render(row, raw)              // render(row, raw)
            : typeof col.format === "function"
              ? col.format(raw, row)            // format(value, row)
              : (raw ?? "—");

        const td = $("td", { class: "dt-td" });
        if (content instanceof Node) td.appendChild(content);
        else td.textContent = content;

        tr.appendChild(td);
      }

      tbody.appendChild(tr);
    }
  }

  function safeGet(obj, path) {
    if (!obj || !path) return undefined;
    if (!path.includes(".")) return obj[path];
    return path.split(".").reduce((acc, k) => (acc ? acc[k] : undefined), obj);
  }

  // ---- Public API ----------------------------------------------------------
  function setRows(nextRows = []) {
    rows = Array.isArray(nextRows) ? nextRows : [];
    renderRows();
  }

  // Initial paint
  renderHeader();
  renderRows();

  // Optional tiny styles (scoped by classNames). Remove if you have global CSS.
  injectOnce("data-table-styles", `
    .data-table { width: 100%; border-collapse: collapse; }
    .data-table thead th { text-align: left; font-weight: 600; padding: 10px 8px; border-bottom: 1px solid var(--line, #333); }
    .data-table tbody td { padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .data-table .sortable .dt-sort-btn { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
    .data-table .dt-sort-indicator::after { content: "↕"; font-size: 0.9em; opacity: 0.6; }
    .data-table th.sorted.asc .dt-sort-indicator::after { content: "↑"; opacity: 0.9; }
    .data-table th.sorted.desc .dt-sort-indicator::after { content: "↓"; opacity: 0.9; }
    .data-table .dt-row.clickable { cursor: pointer; }
    .data-table .dt-row.clickable:hover { background: rgba(255,255,255,0.04); }
    .data-table .dt-empty-cell { text-align: center; padding: 14px; opacity: 0.7; }
  `);

  function injectOnce(id, css) {
    if (document.getElementById(id)) return;
    const style = document.createElement("style");
    style.id = id;
    style.textContent = css;
    document.head.appendChild(style);
  }

  return {
    el: root,
    setRows,
    // expose sort state in case you want to read it
    get sortKey() { return sortKey; },
    get sortDesc() { return sortDesc; },
  };
}
