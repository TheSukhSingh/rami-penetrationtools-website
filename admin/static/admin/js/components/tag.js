// admin/static/admin/js/components/tag.js

export function makeTag(text, { variant = "default", title } = {}) {
  const span = document.createElement("span");
  span.className = `tag tag--${variant}`;
  if (title) span.title = title;
  span.textContent = text ?? "";
  injectOnce(
    "tag-styles",
    `
    .tag{display:inline-block;font-size:12px;line-height:1;padding:6px 8px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06)}
    .tag--success{background:rgba(24,160,88,.18);border-color:rgba(24,160,88,.4)}
    .tag--warning{background:rgba(240,160,24,.18);border-color:rgba(240,160,24,.4)}
    .tag--danger{background:rgba(198,40,40,.18);border-color:rgba(198,40,40,.4)}
    .tag--info{background:rgba(42,109,244,.18);border-color:rgba(42,109,244,.4)}
  `
  );
  return span;
}

function injectOnce(id, css) {
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = css;
  document.head.appendChild(style);
}
