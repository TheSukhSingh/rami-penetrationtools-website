import { el } from '../lib/dom.js';

export function createStatCard({ title, iconSvg }) {
  const root = el('div', { class: 'metric-card glass' },
    el('div', { class: 'metric-header' },
      el('div', { class: 'metric-icon', 'aria-hidden': 'true' }, iconSvg || ''),
      el('h3', {}, title)
    ),
    el('div', { class: 'metric-value' }, '—'),
    el('div', { class: 'metric-change positive' }, '')
  );
  const valueEl = root.querySelector('.metric-value');
  const changeEl = root.querySelector('.metric-change');
  return {
    el: root,
    update({ value, changeText, positive = true }) {
      valueEl.textContent = value;
      changeEl.textContent = changeText || '';
      changeEl.classList.toggle('positive', !!positive);
      changeEl.classList.toggle('negative', !positive);
    }
  };
}
