// admin/static/admin/js/api/metrics.js
import { getJSON } from '../lib/http.js';

export async function getOverview(range, { signal } = {}) {
  const res = await getJSON('/overview', { params: { range }, signal });
  return res.data; // unwrap { ok, data, meta } -> return inner data
}
