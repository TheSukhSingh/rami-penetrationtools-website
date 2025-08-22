import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Settings', subtitle: 'Site configuration, authentication, and integrations' });
  root.innerHTML = `
    <div class="panel" style="padding:20px">
      <h2>Settings</h2>
      <p>Feature toggles and configuration coming soon...</p>
    </div>`;
}
export function unmount() {}
