import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Analytics Dashboard",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Analytics Dashboard</h2>
                        <p>Advanced analytics and reporting features coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
