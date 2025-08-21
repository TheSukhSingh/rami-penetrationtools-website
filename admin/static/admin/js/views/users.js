import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Users",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Users</h2>
                        <p>User management UI coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
