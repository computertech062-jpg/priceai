// دۆخی گشتیی ئەپەکە: بەکارهێنەر، token، ڕێکخستنەکان
const KEY = "priceai";

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch { return {}; }
}
function write(data) {
  try { localStorage.setItem(KEY, JSON.stringify(data)); } catch { /* storage نییە */ }
}

const saved = read();
const listeners = new Set();

export const store = {
  token: saved.token || null,
  user: saved.user || null,
  theme: saved.theme || "dark",
  lang: saved.lang || "ku",
  schema: null,         // /api/features
  modelInfo: null,      // /api/model
  compareQueue: [],     // مۆبایلەکان بۆ بەراوردکردن
  pendingPrediction: null,
  requireLogin: true,   // لە /api/config وەردەگیرێت: پێش چوونەژوورەوە تەنها پەڕەی login
};

export function persist() {
  write({ token: store.token, user: store.user, theme: store.theme, lang: store.lang });
}

export function setAuth(token, user) {
  store.token = token;
  store.user = user;
  persist();
  emit();
}

export function logout() {
  store.token = null;
  store.user = null;
  persist();
  emit();
}

export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function emit() { listeners.forEach((fn) => fn(store)); }
export const isAdmin = () => store.user?.role === "admin";
