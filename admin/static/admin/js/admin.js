import { initRouter, navigate, setActiveNav } from './router.js';
import { initState, setPeriod, subscribe } from './lib/state.js';
import { initParticles } from './lib/dom.js';
import { toast } from './components/toast.js';

function wireTopbar() {
  const group = document.getElementById('timeFilters');
  if (!group) return;

  group.addEventListener('click', (e) => {
    const btn = e.target.closest('.time-filter');
    if (!btn) return;
    const period = btn.dataset.period;

    // toggle UI
    group.querySelectorAll('.time-filter').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    setPeriod(period); // updates global state and notifies views
  });
}

function wireSidebar() {
  document.body.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-nav]');
    if (!a) return;
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
  wireSidebar();
  wireLogout();

  initRouter({
    '/admin': 'overview',
    '/admin/overview': 'overview',
    '/admin/analytics': 'analytics',
    '/admin/users': 'users',
    '/admin/scans': 'scans',
    '/admin/tools': 'tools',
    '/admin/blogs': 'blogs',
    '/admin/admins': 'admins',
    '/admin/audit': 'audit',
    '/admin/settings': 'settings'
  });

  // keep header title/subtitle synced with current view if a view sets them
  subscribe(['pageTitle','pageSubtitle'], (s) => {
    if (s.pageTitle)  document.getElementById('pageTitle').textContent = s.pageTitle;
    if (s.pageSubtitle) document.getElementById('pageSubtitle').textContent = s.pageSubtitle;
  });

  // global error handler (optional)
  window.addEventListener('unhandledrejection', (ev) => {
    toast.error(ev.reason?.message || 'Something went wrong');
  });
}

document.addEventListener('DOMContentLoaded', boot);
