import { initRouter, navigate, setActiveNav } from './router.js';
import { initState, setPeriod, subscribe, getState } from './lib/state.js';
import { initParticles } from './lib/dom.js';
import { toast } from './components/toast.js';

let pollTimer = null;

function dispatchRefresh() {
  window.dispatchEvent(new CustomEvent('admin:refresh'));
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  dispatchRefresh();                        // fire immediately
  pollTimer = setInterval(dispatchRefresh, 60_000); // then every 60s
}

function wireTopbar() {
  const group = document.getElementById('timeFilters');
  if (!group) return;

  group.addEventListener('click', (e) => {
    const btn = e.target.closest('.time-filter');
    if (!btn) return;
    const period = btn.dataset.period;

    // toggle UI
    group.querySelectorAll('.time-filter').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-selected', 'false')

    });

    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true')
    setPeriod(period); // updates global state and notifies views
  });
}

function wireSidebar() {
  document.body.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-nav]');
    if (!a) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    const path = a.getAttribute('href');
    navigate(path);
    setActiveNav(path);
  });
}

function wireLogout() {
  const btn = document.querySelector('[data-logout]');
  if (!btn) return;
  btn.addEventListener('click', () => {
    btn.innerHTML = '<div class="loading-spinner"></div>';
    setTimeout(() => (window.location.href = '/logout'), 700);
  });
}

async function boot() {
  initParticles();
  initState();       // restores last period; notifies subscribers

  wireTopbar();
  const s = getState();
  const btn = document.querySelector(`.time-filter[data-period="${s.period}"]`);
  if (btn) {
    document.querySelectorAll('#timeFilters .time-filter').forEach(b => {
      const isActive = b === btn;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
  }

  wireSidebar();
  wireLogout();

  initRouter({
    '/admin': 'overview',
    '/admin/analytics': 'analytics',
    '/admin/users': 'users',
    '/admin/scans': 'scans',
    '/admin/tools': 'tools',
    '/admin/blogs': 'blogs',
    '/admin/admins': 'admins',
    '/admin/audit': 'audit',
    '/admin/settings': 'settings'
  });
  startPolling();
  // keep header title/subtitle synced with current view if a view sets them
  subscribe(['pageTitle', 'pageSubtitle'], (s) => {
    if (s.pageTitle) document.getElementById('pageTitle').textContent = s.pageTitle;
    if (s.pageSubtitle) document.getElementById('pageSubtitle').textContent = s.pageSubtitle;
  });
  subscribe(['period'], () => startPolling());


  // global error handler (optional)
  window.addEventListener('unhandledrejection', (ev) => {
    toast.error(ev.reason?.message || 'Something went wrong');
  });
}

document.addEventListener('DOMContentLoaded', boot);
