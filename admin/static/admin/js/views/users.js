import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Analytics Dashboard', subtitle: 'Advanced analytics and performance metrics' });
  root.innerHTML = `
    <div class="panel" style="padding:20px">
      <h2>Users Dashboard</h2>
      <p>Advanced users and reporting features coming soon...</p>
    </div>`;
}
export function unmount() {}
