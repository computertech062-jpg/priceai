// پەیوەندی بە Backend (REST API)
import { store, logout } from "./store.js";

const BASE = "/api";

export class ApiError extends Error {
  constructor(status, detail, network = false) {
    super(typeof detail === "string" ? detail : detail?.code || `HTTP ${status}`);
    this.status = status;
    this.network = network;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) Object.assign(this, detail);
  }
}

async function request(method, path, { body, query, signal } = {}) {
  let url = BASE + path;
  if (query) {
    const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== ""));
    const s = qs.toString();
    if (s) url += `?${s}`;
  }
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (store.token) headers.Authorization = `Bearer ${store.token}`;
  let res;
  try {
    res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined, signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(0, null, true);
  }
  let data = null;
  try { data = await res.json(); } catch { /* وەڵامی بەتاڵ */ }
  if (!res.ok) {
    const detail = data?.detail;
    if (res.status === 401) {
      if (store.token) logout();
      // سیستەمەکە چوونەژوورەوەی پێویستە: بگەڕێوە بۆ پەڕەی login (جگە لە خودی پەڕەی login/register)
      const here = location.hash.replace(/^#\/?/, "");
      if (store.requireLogin && !/^(login|register)\b/.test(here)) {
        location.hash = `#/login${here ? `?next=${encodeURIComponent(here)}` : ""}`;
      }
    }
    throw new ApiError(res.status, detail);
  }
  return data;
}

export const api = {
  config: () => request("GET", "/config"),
  features: () => request("GET", "/features"),
  search: (q, signal) => request("GET", "/phones/search", { query: { q, limit: 8 }, signal }),
  phone: (id) => request("GET", `/phones/${encodeURIComponent(id)}`),
  brands: () => request("GET", "/phones/brands"),
  forecast: (id, ram, storage, aiPrice) => request("GET", `/phones/${encodeURIComponent(id)}/forecast`, { query: { ram, storage, ai_price: aiPrice } }),
  forecastBacktest: () => request("GET", "/forecast/backtest"),
  priceHistory: (id, ram, storage) => request("GET", `/phones/${encodeURIComponent(id)}/price-history`, { query: { ram, storage } }),
  predict: (payload, signal) => request("POST", "/predict", { body: payload, signal }),
  compare: (items) => request("POST", "/compare", { body: { items } }),
  register: (data) => request("POST", "/auth/register", { body: data }),
  login: (data) => request("POST", "/auth/login", { body: data }),
  me: () => request("GET", "/auth/me"),
  history: (query) => request("GET", "/history", { query }),
  historyItem: (id) => request("GET", `/history/${id}`),
  deleteHistory: (id) => request("DELETE", `/history/${id}`),
  clearHistory: () => request("DELETE", "/history"),
  dashboard: () => request("GET", "/dashboard"),
  model: () => request("GET", "/model"),
  adminUsers: (q) => request("GET", "/admin/users", { query: { q } }),
  adminUpdateUser: (id, data) => request("PATCH", `/admin/users/${id}`, { body: data }),
  adminDeleteUser: (id) => request("DELETE", `/admin/users/${id}`),
  adminPredictions: () => request("GET", "/admin/predictions"),
  health: () => request("GET", "/health"),
};
