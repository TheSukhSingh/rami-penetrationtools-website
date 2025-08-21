import { setHeader } from "../lib/state.js";

export async function mount(root) {
  setHeader({
    title: "Blogs",
    subtitle: "Advanced analytics and performance metrics",
  });
  root.innerHTML = `
    <div class="tab-content" id="analytics">
                    <div class="coming-soon glass">
                        <h2>Blogs</h2>
                        <p>Blog moderation and publishing coming soon..</p>
                    </div>
                </div>`;
}
export function unmount() {}
