// Tiny client-side router + security & sessions widgets for /account/*
// Uses authFetch (from requesting.js) for all API calls.
(function () {
  const viewRoot = document.getElementById('view-root');

  const routes = {
    profile: '/account/profile',
    security: '/account/security',
    sessions: '/account/sessions',
    notifications: '/account/notifications',
    privacy: '/account/privacy',
  };

  function sectionFromUrl(pathname) {
    const seg = pathname.split('/').filter(Boolean); // ["account","sessions"]
    return seg[1] || 'profile';
  }

  function showToast(msg, type = 'info') {
    // Swap with your toast system
    console[(type === 'error' ? 'error' : 'log')](`[${type}] ${msg}`);
  }

  // --- authFetch helpers ----------------------------------------------------
  function withFragment(url) {
    // Preserve existing query params
    return url.includes('?') ? `${url}&fragment=1` : `${url}?fragment=1`;
  }

  async function getFragmentHTML(url, fetchOptions = {}) {
    // Always send X-Fragment and use authFetch with a visible auth prompt on failure
    const options = {
      ...fetchOptions,
      headers: { 'X-Fragment': '1', ...(fetchOptions.headers || {}) },
      // If refresh fails, we WANT the UI to prompt login (auth:required)
      silent: false,
      credentials: 'include',
    };

    // authFetch is provided by requesting.js and loaded in main.html
    const res = await authFetch(withFragment(url), options);
    if (!res.ok) {
      // If a refresh failed, requesting.js should have dispatched 'auth:required'
      const msg = `Failed to load (${res.status})`;
      throw new Error(msg);
    }
    return res.text();
  }

  // --- Router ---------------------------------------------------------------
  async function loadSection(section, { replace = false } = {}) {
    const url = routes[section] || routes.profile;

    try {
      const html = await getFragmentHTML(url);
      viewRoot.innerHTML = html;

      // update active tab
      document.querySelectorAll('.nav-tab').forEach(a =>
        a.classList.toggle('active', a.dataset.section === section)
      );

      // history
      if (replace) history.replaceState({ section }, '', url);
      else history.pushState({ section }, '', url);

      // wire fresh content
      bindAjaxForms(viewRoot);
      bindSecurityWidgets(viewRoot);
      bindSessionsWidgets(viewRoot);
      bindNotificationsWidgets(viewRoot);
      maybeShowFlash(viewRoot);
    } catch (err) {
      showToast(err.message || 'Failed to load section', 'error');
    }
  }

  function maybeShowFlash(root) {
    root.querySelectorAll('[data-flash-message]').forEach(el => {
      const cat = el.dataset.flashCategory || 'success';
      const msg = el.textContent.trim();
      if (msg) showToast(msg, cat);
      el.remove();
    });
  }

  // Intercept forms marked with data-ajax, submit via authFetch (FormData-safe)
  function bindAjaxForms(root) {
    root.querySelectorAll('form[data-ajax]').forEach(form => {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);

        try {
          const html = await getFragmentHTML(form.action, {
            method: (form.getAttribute('method') || 'POST').toUpperCase(),
            body: formData, // authFetch will detect FormData and NOT force JSON headers
          });

          viewRoot.innerHTML = html;

          // re-bind after render
          bindAjaxForms(viewRoot);
          bindSecurityWidgets(viewRoot);
          bindSessionsWidgets(viewRoot);
          bindNotificationsWidgets(viewRoot);
          maybeShowFlash(viewRoot);
        } catch (err) {
          showToast(err.message || 'Request failed', 'error');
        }
      });
    });
  }

  function handleNavClicks() {
    document.querySelectorAll('.nav-tab').forEach(a => {
      a.addEventListener('click', (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        e.preventDefault();
        loadSection(a.dataset.section);
      });
    });
  }

  // --- Privacy helpers (trigger forms handled by bindAjaxForms) -------------
  window.requestExport = function () {
    const form = document.getElementById('exportForm');
    if (!form) return;
    form.requestSubmit();
  };

  window.requestDeletion = function () {
    const form = document.getElementById('deleteForm');
    if (!form) return;
    if (confirm('This will permanently delete your account after the grace period. Continue?')) {
      form.requestSubmit();
    }
  };

  window.addEventListener('popstate', () => {
    const section = sectionFromUrl(location.pathname);
    loadSection(section, { replace: true }).catch(() => {});
  });

  document.addEventListener('DOMContentLoaded', () => {
    handleNavClicks();
    const initial = sectionFromUrl(location.pathname);
    loadSection(initial, { replace: true });
  });

  /* ---------------- Security helpers ---------------- */
  window._tfaNotImplemented = () => showToast('Two-Factor Auth actions are not implemented yet.', 'info');

  function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.type = (input.type === 'password') ? 'text' : 'password';
    const root = btn || (document.querySelector(`.password-toggle[data-target="${inputId}"]`));
    if (root) {
      const open = root.querySelector('.eye-open');
      const closed = root.querySelector('.eye-closed');
      if (open && closed) {
        const showOpen = (input.type === 'password');
        open.style.display = showOpen ? '' : 'none';
        closed.style.display = showOpen ? 'none' : '';
      }
    }
  }

  function computeStrength(pwd) {
    if (!pwd) return 0;
    let score = 0;
    if (pwd.length >= 8) score++;
    if (pwd.length >= 12) score++;
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
    if (/\d/.test(pwd) && /\W/.test(pwd)) score++;
    return Math.max(0, Math.min(score, 4));
  }

  function strengthLabel(score) {
    return ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong'][score] || 'Weak';
  }

  function updateStrengthUI(root, pwd) {
    const wrap = root.querySelector('#passwordStrength');
    if (!wrap) return;
    const fill = wrap.querySelector('.strength-fill');
    const text = wrap.querySelector('.strength-text');
    const score = computeStrength(pwd);
    const pct = [0, 25, 50, 75, 100][score];
    if (fill) fill.style.width = pct + '%';
    if (text) text.textContent = 'Password strength: ' + strengthLabel(score);
  }

  function bindSecurityWidgets(root) {
    root.querySelectorAll('.password-toggle').forEach(btn => {
      const target = btn.getAttribute('data-target');
      btn.addEventListener('click', () => togglePassword(target, btn));
    });

    const newPw = root.querySelector('#newPassword');
    const confirmPw = root.querySelector('#confirmPassword');

    if (newPw) {
      newPw.addEventListener('input', () => {
        updateStrengthUI(root, newPw.value);
        if (confirmPw) {
          confirmPw.setCustomValidity(
            confirmPw.value && confirmPw.value !== newPw.value ? 'Passwords do not match' : ''
          );
        }
      });
    }

    if (confirmPw) {
      confirmPw.addEventListener('input', () => {
        const np = root.querySelector('#newPassword');
        if (!np) return;
        confirmPw.setCustomValidity(
          confirmPw.value && confirmPw.value !== np.value ? 'Passwords do not match' : ''
        );
      });
    }
  }

  /* ---------------- Sessions widgets ---------------- */
  function bindSessionsWidgets(root) {
    const table = root.querySelector('.sessions-table');
    if (!table) return; // not on sessions page

    const selectAll = table.querySelector('#selectAll');
    const checkboxes = Array.from(table.querySelectorAll('.session-checkbox'));
    const revokeSelectedBtn = root.querySelector('#revokeSelectedBtn');

    function refreshBulkState() {
      const anyChecked = checkboxes.some(cb => cb.checked && !cb.disabled);
      if (revokeSelectedBtn) revokeSelectedBtn.disabled = !anyChecked;
    }

    if (selectAll) {
      selectAll.addEventListener('change', () => {
        checkboxes.forEach(cb => { if (!cb.disabled) cb.checked = selectAll.checked; });
        refreshBulkState();
      });
    }

    checkboxes.forEach(cb => cb.addEventListener('change', refreshBulkState));

    // Ensure the submit button in #revokeSelectedForm submits the table's form data too
    const outerForm = root.querySelector('#revokeSelectedForm');
    const tableForm = root.querySelector('#revokeSelectedScope');

    if (outerForm && tableForm && revokeSelectedBtn) {
      // Mirror submit from the button to the table form, which holds the inputs
      outerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        tableForm.requestSubmit();
      });
    }

    refreshBulkState();
  }

  /* ---------------- Notifications widgets ---------------- */
  function bindNotificationsWidgets(root) {
    const form = root.querySelector('#notificationsForm');
    if (!form) return;

    // Masters that are actually submitted to backend
    const master = {
      security: form.querySelector('#securityMaster'),
      product: form.querySelector('#productMaster'),
      marketing: form.querySelector('#marketingMaster'),
    };

    // Sub-toggles grouped by category
    const subs = {
      security: ['#loginAlerts', '#passwordAlerts', '#tfaAlerts'].map(s => form.querySelector(s)).filter(Boolean),
      product: ['#newTools', '#featureUpdates'].map(s => form.querySelector(s)).filter(Boolean),
      marketing: ['#promotions', '#newsletter'].map(s => form.querySelector(s)).filter(Boolean),
    };

    function syncMaster(group) {
      const anyOn = subs[group].some(cb => cb && cb.checked);
      if (master[group]) master[group].checked = !!anyOn;
    }

    // Initial sync (in case server changed master values)
    Object.keys(subs).forEach(g => syncMaster(g));

    // Wire change handlers
    Object.keys(subs).forEach(g => {
      subs[g].forEach(cb => cb && cb.addEventListener('change', () => syncMaster(g)));
    });

    // Unsubscribe from all marketing: uncheck subs, sync, then submit
    const unSubBtn = form.querySelector('#unsubscribeAllMarketingBtn');
    if (unSubBtn) {
      unSubBtn.addEventListener('click', () => {
        subs.marketing.forEach(cb => { if (cb) cb.checked = false; });
        syncMaster('marketing');
        form.requestSubmit(); // posted via data-ajax
      });
    }
  }

})();
