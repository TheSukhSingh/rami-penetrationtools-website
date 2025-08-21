// admin/static/admin/js/components/modal.js

export function open({
  title = "",
  body = "",
  actions = [],
  width = 560,
  onClose = null,
} = {}) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.tabIndex = -1;

  const modal = document.createElement("div");
  modal.className = "modal";
  modal.style.maxWidth = width + "px";

  const header = document.createElement("div");
  header.className = "modal-header";
  const h = document.createElement("h3");
  h.textContent = title || "";
  const x = document.createElement("button");
  x.type = "button";
  x.className = "modal-close";
  x.title = "Close";
  x.textContent = "×";
  header.append(h, x);

  const content = document.createElement("div");
  content.className = "modal-content";
  if (typeof body === "string") {
    content.innerHTML = body;
  } else if (body instanceof Node) {
    content.appendChild(body);
  }

  const footer = document.createElement("div");
  footer.className = "modal-footer";

  const apiClose = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
    if (typeof onClose === "function") onClose();
  };

  (actions || []).forEach((a) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = a.label || "OK";
    btn.className = [
      "modal-btn",
      a.primary ? "primary" : "",
      a.danger ? "danger" : "",
    ]
      .filter(Boolean)
      .join(" ");
    btn.addEventListener("click", () => {
      if (typeof a.onClick === "function") a.onClick(apiClose);
      else apiClose();
    });
    footer.appendChild(btn);
  });

  modal.append(header, content, footer);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  function onKey(e) {
    if (e.key === "Escape") apiClose();
  }
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) apiClose();
  });
  x.addEventListener("click", apiClose);

  injectOnce(
    "modal-styles",
    `
    .modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000}
    .modal{width:100%;max-width:560px;background:#111;border:1px solid rgba(255,255,255,.08);border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.4)}
    .modal-header{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid rgba(255,255,255,.06)}
    .modal-header h3{margin:0;font-size:16px}
    .modal-close{all:unset;cursor:pointer;font-size:22px;line-height:1;opacity:.75;padding:4px}
    .modal-close:hover{opacity:1}
    .modal-content{padding:16px;max-height:65vh;overflow:auto}
    .modal-footer{display:flex;gap:10px;justify-content:flex-end;padding:12px 16px;border-top:1px solid rgba(255,255,255,.06)}
    .modal-btn{all:unset;cursor:pointer;padding:8px 12px;border-radius:10px;border:1px solid rgba(255,255,255,.12)}
    .modal-btn.primary{border-color:transparent;background:#2a6df4}
    .modal-btn.danger{border-color:transparent;background:#c62828}
  `
  );

  // return a small API if you ever want it
  return { close: apiClose, el: overlay };
}

export function confirm(message = "Are you sure?", { title = "Confirm" } = {}) {
  return new Promise((resolve) => {
    open({
      title,
      body: typeof message === "string" ? message : "",
      actions: [
        { label: "Cancel", onClick: (close) => { close(); resolve(false); } },
        { label: "OK", primary: true, onClick: (close) => { close(); resolve(true); } },
      ],
    });
  });
}

function injectOnce(id, css) {
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = css;
  document.head.appendChild(style);
}
