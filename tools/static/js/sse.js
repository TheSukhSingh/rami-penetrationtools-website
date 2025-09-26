export function connectRunSSE(runId, { onEvent, onError } = {}) {
  let es = null;
  let triedRefresh = false;

  const open = () => {
    es = new EventSource(`/tools/api/runs/${runId}/events`);
    es.addEventListener('snapshot', e => {
      try { onEvent?.('snapshot', JSON.parse(e.data)); } catch {}
    });
    es.addEventListener('update', e => {
      try { onEvent?.('update', JSON.parse(e.data)); } catch {}
    });
    es.onerror = async (e) => {
      try { es.close(); } catch {}
      if (!triedRefresh && typeof refreshTokens === 'function') {
        triedRefresh = true;
        try { const r = await refreshTokens({ silent: true }); if (r?.ok) return open(); } catch {}
      }
      onError?.(e);
      window.dispatchEvent(new CustomEvent('auth:required', { detail: { url: location.pathname } }));
    };
  };

  open();
  return () => { try { es?.close(); } catch {} };
}
