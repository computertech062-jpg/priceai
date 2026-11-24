// چوونەژوورەوە و خۆتۆمارکردن
import { api } from "../api.js";
import { navigate } from "../app.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { setAuth, store } from "../store.js";
import { $, errorMessage, esc, setBusy, toast } from "../ui.js";

export async function render(el, params, def) {
  const mode = def.mode;
  const next = params.get("next") || "";
  if (store.token) { navigate(next); return; }
  const isReg = mode === "register";
  el.innerHTML = `
    <div class="auth-wrap">
      <form class="card card-raised auth-card" id="auth-form" novalidate>
        <div class="stack gap-8" style="text-align:center;align-items:center">
          <span class="brand-mark" style="width:60px;height:60px">${icons.logo}</span>
          <h1 style="font-size:26px;font-weight:900;margin-top:8px">${esc(t(isReg ? "auth.registerTitle" : "auth.loginTitle"))}</h1>
          <p class="muted">${esc(t(isReg ? "auth.registerSub" : "auth.loginSub"))}</p>
        </div>
        <div class="form-error" id="a-err" role="alert" hidden></div>
        ${isReg ? `<div class="field"><label for="a-name">${esc(t("auth.name"))}</label>
          <input class="input" id="a-name" name="name" autocomplete="name" required minlength="2" maxlength="80"></div>` : ""}
        <div class="field"><label for="a-email">${esc(t("auth.email"))}</label>
          <input class="input ltr" id="a-email" name="email" type="email" autocomplete="email" required dir="ltr" style="text-align:start"></div>
        <div class="field"><label for="a-pw">${esc(t("auth.password"))}</label>
          <div class="pw-wrap"><input class="input ltr" id="a-pw" name="password" type="password" dir="ltr"
            autocomplete="${isReg ? "new-password" : "current-password"}" required minlength="${isReg ? 8 : 1}">
            <button type="button" class="icon-btn" id="a-eye" aria-label="${esc(t("auth.showPw"))}" aria-pressed="false">${icons.eye}</button></div>
          ${isReg ? `<span class="hint">${esc(t("auth.pwHint"))}</span>` : ""}</div>
        <button class="btn btn-primary btn-lg btn-block" type="submit" id="a-submit">${esc(t(isReg ? "auth.register" : "auth.login"))}</button>
        <p class="muted" style="text-align:center;font-size:14px">${esc(t(isReg ? "auth.haveAccount" : "auth.noAccount"))}
          <a href="#/${isReg ? "login" : "register"}${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}" style="font-weight:800">${esc(t(isReg ? "auth.login" : "auth.register"))}</a></p>
      </form>
    </div>`;

  const form = $("#auth-form", el);
  const pw = $("#a-pw", el);
  const eye = $("#a-eye", el);
  eye.addEventListener("click", () => {
    const show = pw.type === "password";
    pw.type = show ? "text" : "password";
    eye.innerHTML = show ? icons.eyeOff : icons.eye;
    eye.setAttribute("aria-pressed", String(show));
    eye.setAttribute("aria-label", t(show ? "auth.hidePw" : "auth.showPw"));
  });
  (isReg ? $("#a-name", el) : $("#a-email", el)).focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#a-err", el);
    err.hidden = true;
    const data = Object.fromEntries(new FormData(form).entries());
    const problems = [];
    if (isReg && (data.name || "").trim().length < 2) problems.push(t("auth.vName"));
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test((data.email || "").trim())) problems.push(t("auth.vEmail"));
    if (isReg && (data.password || "").length < 8) problems.push(t("auth.vPw"));
    if (!isReg && !data.password) problems.push(t("auth.vPwEmpty"));
    form.querySelectorAll(".input").forEach((i) => i.setAttribute("aria-invalid", "false"));
    if (problems.length) {
      err.textContent = problems.join(" · ");
      err.hidden = false;
      return;
    }
    const btn = $("#a-submit", el);
    setBusy(btn, true);
    try {
      const res = isReg ? await api.register(data) : await api.login(data);
      setAuth(res.token, res.user);
      toast(t(isReg ? "auth.welcomeNew" : "auth.welcome", { name: res.user.name }));
      navigate(next);
    } catch (ex) {
      err.textContent = errorMessage(ex);
      err.hidden = false;
      setBusy(btn, false);
    }
  });
}
