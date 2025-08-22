import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Analytics Dashboard', subtitle: 'Usage trends, retention, and tool performance' });
  root.innerHTML = `
    <div class="panel" style="padding:20px">
      <h2>Analytics Dashboard</h2>
      <p>Advanced analytics and reporting features coming soon...</p>
    </div>`;
}
export function unmount() {}
