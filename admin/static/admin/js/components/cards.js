// import { el } from '../lib/dom.js';

// export function createStatCard({ title, iconSvg }) {
//   const root = el('div', { class: 'metric-card glass' },
//     el('div', { class: 'metric-header' },
//       el('div', { class: 'metric-icon', 'aria-hidden': 'true' }, iconSvg || ''),
//       el('h3', {}, title)
//     ),
//     el('div', { class: 'metric-value' }, '—'),
//     el('div', { class: 'metric-change positive' }, '')
//   );
//   const valueEl = root.querySelector('.metric-value');
//   const changeEl = root.querySelector('.metric-change');
//   return {
//     el: root,
//     update({ value, changeText, positive = true }) {
//       valueEl.textContent = value;
//       changeEl.textContent = changeText || '';
//       changeEl.classList.toggle('positive', !!positive);
//       changeEl.classList.toggle('negative', !positive);
//     }
//   };
// }


import { el } from "../lib/dom.js";

export function makeCardRow() {
  const row = el("div", { class: "cards-row panel" });
  injectOnce(
    "cards-styles",
    `
    .cards-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
    .metric-card{border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:14px 14px;background:#111;display:flex;flex-direction:column;gap:10px;min-height:96px}
    .metric-header{display:flex;align-items:center;gap:10px}
    .metric-icon{width:24px;height:24px;opacity:.8}
    .metric-value{font-size:24px;font-weight:700;line-height:1}
    .metric-change{font-size:12px;opacity:.9}
    .metric-change.negative{color:#e25555}
    .metric-change.positive{color:#4caf50}
    `
  );

  /** @type {ReturnType<typeof createStatCard>[]} */
  let cards = [];

  function ensureCards(n) {
    // create/diff number of cards to match n
    while (cards.length < n) {
      const c = createStatCard({ title: "" });
      cards.push(c);
      row.appendChild(c.el);
    }
    while (cards.length > n) {
      const c = cards.pop();
      c.el.remove();
    }
  }

  function update(configs = []) {
    ensureCards(configs.length);
    configs.forEach((cfg, i) => {
      const c = cards[i];
      c.setTitle(cfg.title ?? "");
      c.update({
        value: cfg.value ?? "—",
        delta: cfg.delta,
      });
    });
  }

  return { el: row, update };
}

export function createStatCard({ title = "", iconSvg = "" } = {}) {
  const root = el(
    "div",
    { class: "metric-card glass" },
    el(
      "div",
      { class: "metric-header" },
      el("div", { class: "metric-icon", "aria-hidden": "true" }, iconSvg || ""),
      el("h3", {}, title)
    ),
    el("div", { class: "metric-value" }, "—"),
    el("div", { class: "metric-change" }, "")
  );

  const titleEl = root.querySelector("h3");
  const valueEl = root.querySelector(".metric-value");
  const changeEl = root.querySelector(".metric-change");

  function setTitle(t) {
    titleEl.textContent = t || "";
  }

  function update({ value, delta, changeText, positive } = {}) {
    valueEl.textContent = value ?? "—";

    let text = changeText;
    let isPositive = positive;

    if (delta !== undefined && delta !== null) {
      if (typeof delta === "number") {
        text = `${delta > 0 ? "+" : ""}${delta.toFixed(2)}%`;
        isPositive = delta >= 0;
      } else if (typeof delta === "string") {
        text = delta;
        const s = delta.trim();
        if (isPositive === undefined) {
          isPositive = !s.startsWith("-");
        }
      }
    }

    if (text === null || text === undefined || text === "") {
      changeEl.textContent = "";
      changeEl.classList.remove("positive", "negative");
      changeEl.style.display = "none";
    } else {
      changeEl.textContent = text;
      changeEl.style.display = "";
      changeEl.classList.toggle("positive", !!isPositive);
      changeEl.classList.toggle("negative", isPositive === false);
    }
  }

  return { el: root, setTitle, update };
}


function injectOnce(id, css) {
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = css;
  document.head.appendChild(style);
}
