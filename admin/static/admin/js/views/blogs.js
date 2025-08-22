import { setHeader } from '../lib/state.js';

export async function mount(root) {
  setHeader({ title: 'Blogs', subtitle: 'Create posts; manage drafts, categories, and publishing' });
  root.innerHTML = `
    <div class="panel" style="padding:20px">
      <h2>Blogs</h2>
      <p>Advanced analytics and reporting features coming soon...</p>
    </div>`;
}
export function unmount() {}
