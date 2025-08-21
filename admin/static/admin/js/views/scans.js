import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Scans",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Scans</h2>
                        <p>Scan history and activity timeline coming soon...</p>
                    </div>
                </div>`;
}
export function unmount() {}
