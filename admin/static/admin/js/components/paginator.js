// admin/static/admin/js/components/paginator.js

export function makePaginator({
  page = 1,
  perPage = 20,
  total = 0,
  onPage = () => {},
} = {}) {
  let current = Math.max(1, parseInt(page, 10) || 1);
  let per = Math.max(1, parseInt(perPage, 10) || 20);
  let tot = Math.max(0, parseInt(total, 10) || 0);

  const root = document.createElement("div");
  root.className = "paginator";

  const info = document.createElement("div");
  info.className = "paginator-info";

  const nav = document.createElement("div");
  nav.className = "paginator-nav";

  const btnPrev = button("Prev", () => setPage(current - 1));
  const btnNext = button("Next", () => setPage(current + 1));

  nav.append(btnPrev, btnNext);
  root.append(info, nav);

  function button(label, onClick) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "paginator-btn";
    b.textContent = label;
    b.addEventListener("click", onClick);
    return b;
  }

  function totalPages() {
    return tot > 0 ? Math.max(1, Math.ceil(tot / per)) : current; // if unknown total, keep current
  }

  function render() {
    const pages = totalPages();
    const start = tot ? (current - 1) * per + 1 : "?";
    const end = tot ? Math.min(current * per, tot) : "?";
    const text = tot ? `Showing ${start}–${end} of ${tot}` : `Page ${current}`;
    info.textContent = text;

    btnPrev.disabled = current <= 1;
    btnNext.disabled = tot ? current >= pages : false;
  }

  function setTotal(nextTotal) {
    tot = Math.max(0, parseInt(nextTotal, 10) || 0);
    if (tot && (current - 1) * per >= tot) {
      current = Math.max(1, Math.ceil(tot / per));
    }
    render();
  }

  function setPage(next) {
    const pages = totalPages();
    const target = Math.max(1, tot ? Math.min(next, pages) : next);
    if (target === current) return;
    current = target;
    render();
    onPage(current);
  }

  function setPerPage(next) {
    per = Math.max(1, parseInt(next, 10) || 20);
    render();
  }

  injectOnce(
    "paginator-styles",
    `
    .paginator{display:flex;justify-content:space-between;align-items:center;padding:10px 8px;border-top:1px solid rgba(255,255,255,.06)}
    .paginator-info{opacity:.8}
    .paginator-btn{all:unset;cursor:pointer;padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.15);margin-left:6px}
    .paginator-btn[disabled]{opacity:.4;cursor:not-allowed}
  `
  );

  render();

  return {
    el: root,
    setTotal,
    setPage,
    setPerPage,
    get page() { return current; },
    get perPage() { return per; },
  };
}

function injectOnce(id, css) {
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = css;
  document.head.appendChild(style);
}
