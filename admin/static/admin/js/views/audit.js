import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Audit",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Audit</h2>
                        <p>Admin action audit trail coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
