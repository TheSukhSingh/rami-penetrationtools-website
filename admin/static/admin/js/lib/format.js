export const num = (n) => n.toLocaleString();
export const pct = (x) => (x > 0 ? `+${x}%` : `${x}%`);

export function ago(ts) {
  if (!ts) return "—";
  const d = typeof ts === "string" ? new Date(ts) : ts;
  if (!d || isNaN(d)) return "—";
  const diff = Date.now() - d.getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min${m > 1 ? "s" : ""} ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hour${h > 1 ? "s" : ""} ago`;
  const dys = Math.floor(h / 24);
  return `${dys} day${dys > 1 ? "s" : ""} ago`;
}
