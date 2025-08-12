export function periodToRange(period) {
  const end = new Date();
  const start = new Date(end);
  const map = { '7d': 7, '30d': 30, '90d': 90 };
  const days = map[period] ?? 7;
  start.setUTCDate(start.getUTCDate() - (days - 1));
  return { start: start.toISOString(), end: end.toISOString() };
}
