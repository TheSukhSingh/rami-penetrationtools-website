export const qs = (s, r = document) => r.querySelector(s);
export const qsa = (s, r = document) => Array.from(r.querySelectorAll(s));
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => (k === 'class' ? node.className = v : node.setAttribute(k, v)));
  children.flat().forEach(c => node.append(c.nodeType ? c : document.createTextNode(c)));
  return node;
}

export function initParticles() {
  const host = document.getElementById('particles');
  if (!host) return;
  for (let i = 0; i < 12; i++) {
    const p = el('div', { class: 'particle' });
    p.style.left = `${Math.random() * 100}%`;
    p.style.top = `${Math.random() * 100}%`;
    p.style.animationDelay = `${Math.random() * 4}s`;
    p.style.animationDuration = `${3 + Math.random() * 2}s`;
    host.appendChild(p);
  }
}
