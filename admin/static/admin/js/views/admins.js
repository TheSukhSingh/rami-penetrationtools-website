import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Admins",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Admins</h2>
                        <p>Admin roster and 2FA resets coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
