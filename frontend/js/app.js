// دەستپێکی Frontend: Router، Header، ڕووکار و زمان
import { api } from "./api.js";
import { icons } from "./icons.js";
import { applyLang, lang, t } from "./i18n.js";
import { emit, isAdmin, logout, onChange, persist, store } from "./store.js";
import { $, esc, toast } from "./ui.js";

const routes = {
  "": { page: () => import("./pages/home.js"), title: "nav.home" },
  predict: { page: () => import("./pages/predict.js"), title: "nav.predict" },
  compare: { page: () => import("./pages/compare.js"), title: "nav.compare" },
  history: { page: () => import("./pages/history.js"), title: "nav.history", auth: true },
  dashboard: { page: () => import("./pages/dashboard.js"), title: "nav.dashboard", auth: true },
  model: { page: () => import("./pages/model.js"), title: "nav.model" },
  admin: { page: () => import("./pages/admin.js"), title: "nav.admin", auth: true, admin: true },
  login: { page: () => import("./pages/auth.js"), title: "auth.login", mode: "login" },
  register: { page: () => import("./pages/auth.js"), title: "auth.register", mode: "register" },
};

let current = null;
// ئەو پەڕانەی بەبێ چوونەژوورەوە دەکرێنەوە
const PUBLIC = new Set(["login", "register"]);
const gated = () => store.requireLogin && !store.token;

export function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path, qs = ""] = raw.split("?");
  return { path: path.replace(/\/$/, ""), params: new URLSearchParams(qs) };
}

export function navigate(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
  const target = `#/${path}${qs ? `?${qs}` : ""}`;
  if (location.hash === target) route();
  else location.hash = target;
}

export function href(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  return `#/${path}${qs ? `?${qs}` : ""}`;
}

// ---------- Schema و زانیاریی مۆدێل (یەکجار بار دەکرێن) ----------
let schemaPromise = null;
export function ensureSchema() {
  if (store.schema) return Promise.resolve(store.schema);
  if (!schemaPromise) {
    schemaPromise = api.features().then((s) => { store.schema = s; return s; })
      .catch((e) => { schemaPromise = null; throw e; });
  }
  return schemaPromise;
}
let modelPromise = null;
export function ensureModelInfo() {
  if (store.modelInfo) return Promise.resolve(store.modelInfo);
  if (!modelPromise) {
    modelPromise = api.model().then((m) => { store.modelInfo = m; return m; })
      .catch((e) => { modelPromise = null; throw e; });
  }
  return modelPromise;
}
export function featureLabel(name) {
  const f = store.schema?.features?.find((x) => x.name === name);
  return f ? f.label[lang()] || f.label.en : name;
}

// ---------- Header / Footer / Mobile nav ----------
const NAV = [
  ["", "nav.home", "home"],
  ["predict", "nav.predict", "sparkle"],
  ["compare", "nav.compare", "compare"],
  ["history", "nav.history", "history"],
  ["model", "nav.model", "chart"],
];

function renderChrome() {
  const { path } = parseHash();
  const cur = (p) => (p === path ? 'aria-current="page"' : "");
  const user = store.user;
  const initial = esc((user?.name || "?").trim().charAt(0).toUpperCase());
  $("#site-header").innerHTML = `
    <div class="container">
      <a class="brand" href="#/" aria-label="PriceAI">
        <span class="brand-mark">${icons.logo}</span><span class="brand-name">PriceAI</span>
      </a>
      <nav class="main-nav" aria-label="${esc(t("nav.main"))}">
        ${gated() ? "" : NAV.map(([p, k]) => `<a href="#/${p}" ${cur(p)}>${esc(t(k))}</a>`).join("")}
      </nav>
      <div class="header-actions">
        <div class="seg" role="group" aria-label="${esc(t("nav.language"))}">
          <button type="button" data-lang="ku" aria-pressed="${lang() === "ku"}" lang="ckb">کوردی</button>
          <button type="button" data-lang="ar" aria-pressed="${lang() === "ar"}" lang="ar">عربي</button>
          <button type="button" data-lang="en" aria-pressed="${lang() === "en"}" lang="en" class="num">EN</button>
        </div>
        <button type="button" class="icon-btn" id="theme-btn" aria-label="${esc(t(store.theme === "dark" ? "nav.lightMode" : "nav.darkMode"))}">
          ${store.theme === "dark" ? icons.sun : icons.moon}
        </button>
        ${user ? `
          <div class="user-menu">
            <button type="button" class="avatar" id="user-btn" aria-haspopup="menu" aria-expanded="false" aria-label="${esc(user.name)}">${initial}</button>
            <div class="menu" id="user-menu" role="menu">
              <div class="menu-head"><div style="font-weight:800">${esc(user.name)}</div><div class="faint" style="font-size:13px">${esc(user.email)}</div></div>
              <a role="menuitem" href="#/dashboard">${icons.grid}${esc(t("nav.dashboard"))}</a>
              <a role="menuitem" href="#/history">${icons.history}${esc(t("nav.history"))}</a>
              ${isAdmin() ? `<a role="menuitem" href="#/admin">${icons.users}${esc(t("nav.admin"))}</a>` : ""}
              <button role="menuitem" type="button" id="logout-btn">${icons.logout}${esc(t("nav.logout"))}</button>
            </div>
          </div>` : gated() ? "" : `<a class="btn btn-primary btn-sm hide-mobile" href="#/login">${esc(t("auth.login"))}</a>`}
      </div>
    </div>`;

  const mobileItems = [
    ["", "nav.home", "home"], ["predict", "nav.predictShort", "sparkle"], ["compare", "nav.compare", "compare"],
    ["history", "nav.history", "history"], [user ? "dashboard" : "login", user ? "nav.dashboard" : "auth.login", user ? "grid" : "user"],
  ];
  $("#mobile-nav").setAttribute("aria-label", t("nav.main"));
  $("#mobile-nav").hidden = gated();
  $("#mobile-nav").innerHTML = gated() ? "" : mobileItems.map(([p, k, ic]) =>
    `<a href="#/${p}" ${cur(p)}>${icons[ic]}<span>${esc(t(k))}</span></a>`).join("");

  $("#site-footer").innerHTML = `<div class="container">
      <span>${esc(t("footer.project"))} · ${new Date().getFullYear()}</span>
      <span class="row gap-16">${gated() ? "" : `<a href="#/model">${esc(t("nav.model"))}</a>`}<a href="/docs" target="_blank" rel="noopener">API</a><span class="num">PriceAI</span></span>
    </div>`;
}

function bindChrome() {
  document.addEventListener("click", async (e) => {
    const langBtn = e.target.closest("[data-lang]");
    if (langBtn) {
      store.lang = langBtn.dataset.lang;
      persist();
      applyLang(store.lang);
      renderChrome();
      route();
      return;
    }
    if (e.target.closest("#theme-btn")) {
      store.theme = store.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = store.theme;
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", store.theme === "dark" ? "#0B0E19" : "#F5F6FB");
      persist();
      renderChrome();
      $("#theme-btn")?.focus();
      return;
    }
    const userBtn = e.target.closest("#user-btn");
    const menu = $("#user-menu");
    if (userBtn && menu) {
      const open = !menu.classList.contains("open");
      menu.classList.toggle("open", open);
      userBtn.setAttribute("aria-expanded", String(open));
      return;
    }
    if (e.target.closest("#logout-btn")) {
      logout();
      toast(t("auth.loggedOut"));
      navigate("");
      return;
    }
    if (menu && !e.target.closest(".user-menu")) {
      menu.classList.remove("open");
      $("#user-btn")?.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("#user-menu")?.classList.remove("open");
  });
}

// ---------- Router ----------
export async function route() {
  const { path, params } = parseHash();
  const def = routes[path];
  const app = $("#app");
  renderChrome();
  if (current?.destroy) { try { current.destroy(); } catch { /* */ } }
  current = null;

  if (!def) {
    app.innerHTML = `<div class="container page"><div class="card">${(await import("./ui.js")).emptyState({
      title: t("notFound.title"), body: t("notFound.body"),
      action: `<a class="btn btn-primary" href="#/">${esc(t("nav.home"))}</a>` })}</div></div>`;
    document.title = `${t("notFound.title")} · PriceAI`;
    return;
  }
  // سیستەمەکە چوونەژوورەوەی پێویستە: یەکەم پەڕە login ـە
  if ((def.auth || gated()) && !store.token && !PUBLIC.has(path)) {
    const here = location.hash.replace(/^#\/?/, "");
    navigate("login", here ? { next: here } : {});
    return;
  }
  if (def.admin && !isAdmin()) {
    toast(t("err.admin_only"), "error");
    navigate("dashboard");
    return;
  }
  document.title = `${t(def.title)} · PriceAI`;
  app.innerHTML = `<div class="container page"><div class="skeleton" style="height:42px;width:260px;margin-bottom:24px"></div><div class="skeleton" style="height:320px"></div></div>`;
  try {
    const mod = await def.page();
    // ئەگەر لە کاتی بارکردندا بەکارهێنەر چووبێتە پەڕەیەکی تر
    if (parseHash().path !== path) return;
    current = mod;
    await mod.render(app, params, def);
  } catch (err) {
    console.error(err);
    app.innerHTML = `<div class="container page"><div class="card">${(await import("./ui.js")).emptyState({
      icon: icons.alert, title: t("err.pageTitle"), body: t("err.network"),
      action: `<button class="btn btn-primary" onclick="location.reload()">${esc(t("common.retry"))}</button>` })}</div></div>`;
  }
  if (!params.get("keepScroll")) window.scrollTo({ top: 0 });
}

async function boot() {
  applyLang(store.lang);
  document.documentElement.dataset.theme = store.theme;
  // ئایا چوونەژوورەوە پێویستە؟ (ئەگەر سێرڤەر وەڵامی نەدایەوە، وا دادەنرێت کە پێویستە)
  try { store.requireLogin = !!(await api.config()).require_login; } catch { store.requireLogin = true; }
  bindChrome();
  onChange(() => renderChrome());
  window.addEventListener("hashchange", route);
  // پشکنینی token (ئەگەر بەسەرچووبێت دەردەچێت)
  if (store.token) {
    api.me().then((u) => { store.user = u; persist(); emit(); }).catch(() => {});
  }
  route();
}

boot();
