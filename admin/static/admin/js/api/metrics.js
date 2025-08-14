import { getJSON } from '../lib/http.js';

export function getOverview(range, { signal } = {}) {
  return getJSON('/overview', { params: { range }, signal });
}
