import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Settings",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Settings</h2>
                        <p>settings coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
