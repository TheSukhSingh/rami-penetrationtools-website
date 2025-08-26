import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Tools', subtitle: 'Configure tools, defaults, limits, and versions' });
  root.innerHTML = `
    <div class="panel" style="padding:20px">
      <h2>Tools</h2>
      <p>Tools list and usage analytics coming soon...</p>
    </div>`;
}
export function unmount() {}
