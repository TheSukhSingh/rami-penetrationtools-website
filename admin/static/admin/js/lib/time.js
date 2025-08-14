export function periodToRange(period) {
  const end = new Date();         // now
  const start = new Date(end);
  const daysMap = { '1d': 1, '7d': 7, '30d': 30, '90d': 90 };
  if (period === 'all-time') return { start: null, end: end.toISOString() }; // let server interpret
  const days = daysMap[period] ?? 7;
  start.setUTCDate(start.getUTCDate() - (days - 1));
  return { start: start.toISOString(), end: end.toISOString() };
}
