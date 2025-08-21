import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Subscriptions",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Subscriptions</h2>
                        <p>subscription management UI coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
