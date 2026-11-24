// یارمەتیدەرەکانی ڕووکار: escape، فۆرماتی ژمارە، toast، modal، جوڵەی ژمارە
import { icons } from "./icons.js";
import { isRtl, t, lang } from "./i18n.js";

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

// هەموو داتایەک کە لە دەرەوە دێت پێش خستنە ناو HTML دەبێت escape بکرێت
export function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

export function money(v, opts = {}) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Math.round(Number(v));
  const s = Math.abs(n).toLocaleString("en-US");
  const sign = n < 0 ? "−" : opts.sign && n > 0 ? "+" : "";
  return `${sign}$${s}`;
}

export function num(v, digits = 0) {
  if (v === null || v === undefined || v === "") return "—";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function pct(v, digits = 1, sign = false) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  return `${sign && n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(digits)}%`;
}

export function relTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (lang() !== "en") { // کوردی و عەرەبی: دەقەکانی time.* (ژمارەی لاتینی)
    if (sec < 60) return t("time.now");
    if (sec < 3600) return t("time.minutes", { n: Math.floor(sec / 60) });
    if (sec < 86400) return t("time.hours", { n: Math.floor(sec / 3600) });
    if (sec < 86400 * 2) return t("time.yesterday");
    if (sec < 86400 * 30) return t("time.days", { n: Math.floor(sec / 86400) });
    return d.toISOString().slice(0, 10);
  }
  if (sec < 60) return "just now";
  if (sec < 3600) return rtf.format(-Math.floor(sec / 60), "minute");
  if (sec < 86400) return rtf.format(-Math.floor(sec / 3600), "hour");
  if (sec < 86400 * 30) return rtf.format(-Math.floor(sec / 86400), "day");
  return d.toISOString().slice(0, 10);
}

export function debounce(fn, ms = 250) {
  let id;
  const wrapped = (...args) => { clearTimeout(id); id = setTimeout(() => fn(...args), ms); };
  wrapped.cancel = () => clearTimeout(id);
  return wrapped;
}

const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// ژمارەکە بە جوڵە لە from بۆ to دەگۆڕێت
export function countUp(el, to, { from = 0, duration = 700, format = money } = {}) {
  if (!el) return;
  if (reduceMotion() || from === to) { el.textContent = format(to); return; }
  const start = performance.now();
  const token = Symbol();
  el._countToken = token;
  const step = (now) => {
    if (el._countToken !== token) return;
    const p = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = format(from + (to - from) * eased);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ---------- Toast ----------
export function toast(message, type = "ok") {
  const box = document.getElementById("toasts");
  if (!box) return;
  const el = document.createElement("div");
  el.className = `toast ${type === "error" ? "error" : ""}`;
  el.setAttribute("role", type === "error" ? "alert" : "status");
  el.innerHTML = `${type === "error" ? icons.alert : icons.check}<span>${esc(message)}</span>`;
  box.appendChild(el);
  setTimeout(() => { el.classList.add("leaving"); setTimeout(() => el.remove(), 220); }, 3200);
}

// ---------- Modal (پشتڕاستکردنەوە) ----------
export function confirmDialog({ title, body = "", confirm, cancel, danger = false }) {
  return new Promise((resolve) => {
    const last = document.activeElement;
    const wrap = document.createElement("div");
    wrap.className = "modal-backdrop";
    wrap.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <h2 id="modal-title">${esc(title)}</h2>
        ${body ? `<p class="muted">${esc(body)}</p>` : ""}
        <div class="row gap-10" style="justify-content:flex-end;margin-top:6px">
          <button class="btn btn-ghost" data-act="no">${esc(cancel || t("common.cancel"))}</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-act="yes">${esc(confirm || t("common.confirm"))}</button>
        </div>
      </div>`;
    const close = (val) => {
      wrap.remove();
      document.removeEventListener("keydown", onKey);
      last?.focus?.();
      resolve(val);
    };
    const onKey = (e) => { if (e.key === "Escape") close(false); };
    wrap.addEventListener("click", (e) => {
      if (e.target === wrap) close(false);
      const act = e.target.closest("[data-act]")?.dataset.act;
      if (act) close(act === "yes");
    });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(wrap);
    wrap.querySelector('[data-act="yes"]').focus();
  });
}

export function setBusy(btn, busy) {
  if (!btn) return;
  if (busy) {
    btn.dataset.label = btn.innerHTML;
    btn.setAttribute("aria-busy", "true");
    btn.innerHTML = `<span class="spinner" aria-hidden="true"></span><span>${esc(t("common.loading"))}</span>`;
  } else {
    btn.removeAttribute("aria-busy");
    if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
  }
}

export function errorMessage(err) {
  const code = err?.code;
  if ((code === "invalid_feature" || code === "spec_conflict") && err.field) return t(`err.${code}`, { field: err.fieldLabel || err.field });
  if (code && t(`err.${code}`) !== `err.${code}`) return t(`err.${code}`);
  if (err?.status === 422) return t("err.validation");
  if (err?.network) return t("err.network");
  return t("err.generic");
}

export function emptyState({ icon = icons.sparkle, title, body = "", action = "" }) {
  return `<div class="empty fade-in"><div class="empty-ico">${icon}</div><h3>${esc(title)}</h3>
    ${body ? `<p style="max-width:420px">${esc(body)}</p>` : ""}${action}</div>`;
}

export function verdictBadge(status) {
  if (!status) return `<span class="badge badge-neutral">—</span>`;
  return `<span class="badge badge-${status}"><span class="dot"></span>${esc(t(`verdict.${status}`))}</span>`;
}

export function sampleBanner() {
  return `<div class="banner" role="note">${icons.info}<span>${esc(t("common.sampleData"))}</span></div>`;
}

// تیر بە پێی ئاڕاستەی زمان
export const arrow = () => (isRtl() ? "←" : "→");
