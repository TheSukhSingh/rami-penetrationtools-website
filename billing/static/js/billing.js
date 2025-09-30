(async function () {
  const $ = (sel) => document.querySelector(sel);

  function fmtMic(mic) {
    if (typeof mic !== 'number') return '0';
    return (mic).toLocaleString('en-US');
  }
  function fmtWhen(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toUTCString().replace(' GMT','');
  }
  function fmtRel(seconds) {
    if (seconds == null) return '—';
    if (seconds < 0) seconds = 0;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }
  function pct(n, d) {
    if (!d || d <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((n / d) * 100)));
  }

  async function loadStatus() {
    const r = await getJSON('/billing/status');
    if (!r.ok) throw new Error('status failed');
    const s = r.data;
    const pro = s.pro_active;
    const badge = pro ? `<span class="pill pro">Pro</span>` :
                        (s.billing_status === 'past_due' ? `<span class="pill pastdue">Past due</span>` : `<span class="pill">Free</span>`);
    const days = (s.period?.days_to_renewal ?? null);
    const countdown = (days != null) ? ` · renews in ${days}d` : '';
    $('#statusRow').innerHTML = `${badge} ${s.billing_status || 'free'}${countdown}`;
    return s;
  }

  async function loadBalance() {
    const r = await getJSON('/credits/balance');
    if (!r.ok) throw new Error('balance failed');
    const b = r.data;
    $('#dailyMic').textContent = fmtMic(b.daily_mic);
    $('#monthlyMic').textContent = fmtMic(b.monthly_mic);
    $('#topupMic').textContent = fmtMic(b.topup_mic);
    $('#resetAt').textContent = fmtWhen(b.next_daily_reset_utc);
    $('#resetIn').textContent = fmtRel(b.seconds_to_reset);
    return b;
  }

  async function loadUsage() {
    const cfg = await getJSON('/credits/config');
    const usage = await getJSON('/credits/usage');
    if (!cfg.ok || !usage.ok) throw new Error('usage/config failed');

    const periodStart = usage.data.period.start, periodEnd = usage.data.period.end;
    const used = usage.data.monthly_used_mic;
    const cap = cfg.data.pro_monthly_mic; // show Pro cap even if free/past_due (helps UX)
    const percent = pct(used, cap);
    $('#usageNumbers').textContent = `${fmtMic(used)} / ${fmtMic(cap)} mic this period (${new Date(periodStart).toUTCString().slice(5,16)} → ${new Date(periodEnd).toUTCString().slice(5,16)})`;
    $('#usageBar').style.width = `${percent}%`;
  }

  async function loadPacks() {
    // prefer explicit config; fallback to /billing/packs
    const cfg = await getJSON('/billing/config');
    const packs = (cfg.ok ? cfg.data.packs : null) || (await getJSON('/billing/packs')).data.packs || [];
    const row = $('#packsRow');
    row.innerHTML = '';
    packs.forEach(p => {
      const btn = document.createElement('button');
      btn.className = 'btn';
      btn.textContent = `${p.code} (${fmtMic(p.credits_mic)} mic)`;
      btn.addEventListener('click', async () => {
        const r = await postJSON(`/billing/checkout/topup/${p.code}`, { success_url: window.location.origin, cancel_url: window.location.origin });
        if (r.ok) window.open(r.data.checkout_url, '_blank');
        else alert('Checkout failed');
      });
      row.appendChild(btn);
    });
  }

  async function loadInvoices() {
    const r = await getJSON('/billing/invoices?status=paid&limit=10');
    const ul = $('#invoicesList');
    ul.innerHTML = '';
    if (!r.ok || !r.data.items.length) {
      ul.innerHTML = `<li class="muted">No paid invoices yet.</li>`;
      return;
    }
    r.data.items.forEach(inv => {
      const li = document.createElement('li');
      const left = document.createElement('div');
      left.innerHTML = `<div><strong>${inv.number || inv.id}</strong> · ${(inv.total/100).toFixed(2)} ${inv.currency?.toUpperCase() || 'USD'}</div>
                        <div class="small muted">${new Date(inv.created*1000).toUTCString().replace(' GMT','')}</div>`;
      const right = document.createElement('div');
      right.innerHTML = `<a href="${inv.hosted_invoice_url}" target="_blank">View</a> · <a href="${inv.invoice_pdf}" target="_blank">PDF</a>`;
      li.appendChild(left); li.appendChild(right);
      ul.appendChild(li);
    });
  }

  // wire actions
  $('#btnPortal').addEventListener('click', async () => {
    const r = await postJSON('/billing/portal', { return_url: window.location.origin });
    if (r.ok) window.open(r.data.portal_url, '_blank'); else alert('Portal failed');
  });

  // dev simulate buttons
  $('#simPaid').addEventListener('click', async () => {
    const r = await postJSON('/billing/dev/simulate-invoice-paid', {});
    $('#simOut').textContent = JSON.stringify(r.data || r, null, 2);
    await Promise.all([loadBalance(), loadUsage(), loadInvoices(), loadStatus()]);
  });
  $('#simFailed').addEventListener('click', async () => {
    const r = await postJSON('/billing/dev/simulate-invoice-failed', {});
    $('#simOut').textContent = JSON.stringify(r.data || r, null, 2);
    await Promise.all([loadBalance(), loadUsage(), loadInvoices(), loadStatus()]);
  });
  $('#simTopup').addEventListener('click', async () => {
    const r = await postJSON('/billing/dev/simulate-topup/topup_100', {});
    $('#simOut').textContent = JSON.stringify(r.data || r, null, 2);
    await Promise.all([loadBalance(), loadUsage()]);
  });

  // initial load
  await loadStatus();
  await loadBalance();
  await loadUsage();
  await loadPacks();
  await loadInvoices();
})();
