import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Admins Dashboard', subtitle: 'Admin accounts, roles, 2FA, and privileges' });

      root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Admins Dashboard</h2>
                        <p>Advanced analytics and reporting features coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
