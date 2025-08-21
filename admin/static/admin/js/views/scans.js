import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Scan History', subtitle: 'Scan history and activity timeline coming soon...' });
  root.innerHTML = `
    <div class="panel" style="padding:20px">
      <h2>Scan History</h2>
      <p>Scan history and activity timeline coming soon...</p>
    </div>`;
}
export function unmount() {}
