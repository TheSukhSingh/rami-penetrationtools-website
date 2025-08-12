let host;
function ensureHost() {
  if (!host) {
    host = document.createElement('div');
    host.style.position = 'fixed';
    host.style.right = '16px';
    host.style.bottom = '16px';
    host.style.zIndex = '9999';
    document.body.appendChild(host);
  }
}
function show(msg) {
  ensureHost();
  const card = document.createElement('div');
  card.className = 'glass';
  card.style.padding = '12px 16px';
  card.style.marginTop = '8px';
  card.textContent = msg;
  host.appendChild(card);
  setTimeout(() => card.remove(), 3000);
}
export const toast = { info: show, error: show, success: show };
