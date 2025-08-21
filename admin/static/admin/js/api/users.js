import { getJSON, postJSON } from "../lib/http.js";

export async function getUsersSummary(range, { signal } = {}) {
  const res = await getJSON("/users/summary", { params: { range }, signal });
  return res.data; // {cards, range, computed_at}
}

export async function listUsers({ page = 1, per_page = 20, q = "", sort = "-last_login_at" } = {}, { signal } = {}) {
  const res = await getJSON("/users", { params: { page, per_page, q, sort }, signal });
  return res.data; // items array
}

export async function getUserDetail(id, { signal } = {}) {
  const res = await getJSON(`/users/${id}`, { signal });
  return res.data;
}

export async function deactivateUser(id) {
  const res = await postJSON(`/users/${id}/deactivate`, {});
  return res.data;
}

export async function reactivateUser(id) {
  const res = await postJSON(`/users/${id}/reactivate`, {});
  return res.data;
}

export async function setUserTier(id, tier) {
  const res = await postJSON(`/users/${id}/tier`, { tier });
  return res.data;
}


export async function setUserBlocked(id, value) {
  const res = await postJSON(`/users/${id}/blocked`, { value });
  return res.data;
}

export async function setUserEmailVerified(id, value) {
  const res = await postJSON(`/users/${id}/email_verified`, { value });
  return res.data;
}