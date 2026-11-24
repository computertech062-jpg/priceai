// بەڕێوەبردنی بەکارهێنەران (تەنها Admin)
import { api } from "../api.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { store } from "../store.js";
import { $, confirmDialog, debounce, emptyState, errorMessage, esc, money, relTime, toast, verdictBadge } from "../ui.js";

let S = null;
export function destroy() { S = null; }

export async function render(el) {
  S = { el, users: [] };
  el.innerHTML = `
    <div class="container page">
      <div class="page-head"><div><h1 class="page-title">${esc(t("admin.title"))}</h1><p class="page-sub">${esc(t("admin.sub"))}</p></div></div>
      <section class="card stack gap-16" style="margin-bottom:16px">
        <div class="row wrap between gap-12">
          <h2 class="card-title">${esc(t("admin.users"))} <span class="faint num" id="a-count"></span></h2>
          <div class="search-box" style="flex:0 1 340px;border-width:1px">${icons.search}
            <label class="sr-only" for="a-q">${esc(t("admin.search"))}</label>
            <input id="a-q" type="search" placeholder="${esc(t("admin.search"))}" dir="auto"></div>
        </div>
        <div id="a-users"><div class="skeleton" style="height:200px"></div></div>
      </section>
      <section class="card stack gap-16">
        <h2 class="card-title">${esc(t("admin.recent"))}</h2>
        <div id="a-preds"><div class="skeleton" style="height:160px"></div></div>
      </section>
    </div>`;
  $("#a-q", el).addEventListener("input", debounce(() => loadUsers($("#a-q", el).value), 250));
  await Promise.all([loadUsers(""), loadPreds()]);
}

async function loadUsers(q) {
  try {
    const res = await api.adminUsers(q);
    if (!S) return;
    S.users = res.items;
    paintUsers();
  } catch (e) {
    $("#a-users", S.el).innerHTML = emptyState({ icon: icons.alert, title: t("err.pageTitle"), body: errorMessage(e) });
  }
}

function paintUsers() {
  $("#a-count", S.el).textContent = `(${S.users.length})`;
  const box = $("#a-users", S.el);
  if (!S.users.length) { box.innerHTML = emptyState({ icon: icons.users, title: t("history.noMatch") }); return; }
  box.innerHTML = `<div class="table-wrap"><table class="table">
    <thead><tr><th>${esc(t("admin.name"))}</th><th>${esc(t("admin.email"))}</th><th>${esc(t("admin.role"))}</th><th>${esc(t("admin.predictions"))}</th><th>${esc(t("admin.joined"))}</th><th>${esc(t("admin.active"))}</th><th><span class="sr-only">${esc(t("common.actions"))}</span></th></tr></thead>
    <tbody>${S.users.map((u) => {
      const self = u.id === store.user?.id;
      return `<tr>
        <td style="font-weight:700">${esc(u.name)} ${self ? `<span class="badge badge-neutral">${esc(t("admin.you"))}</span>` : ""}</td>
        <td class="num muted">${esc(u.email)}</td>
        <td><div class="select-wrap" style="width:130px"><label class="sr-only" for="role-${u.id}">${esc(t("admin.role"))}</label>
          <select class="select" id="role-${u.id}" data-role="${u.id}" ${self ? "disabled" : ""} style="min-height:40px">
            <option value="user" ${u.role === "user" ? "selected" : ""}>${esc(t("admin.roleUser"))}</option>
            <option value="admin" ${u.role === "admin" ? "selected" : ""}>Admin</option></select></div></td>
        <td class="num">${u.predictions}</td>
        <td class="faint">${esc(relTime(u.created_at))}</td>
        <td><button type="button" class="switch" role="switch" data-active="${u.id}" aria-checked="${u.is_active}" aria-label="${esc(t("admin.active"))}: ${esc(u.name)}" ${self ? "disabled" : ""}></button></td>
        <td>${self ? "" : `<button type="button" class="icon-btn" data-del="${u.id}" aria-label="${esc(t("common.delete"))}: ${esc(u.name)}">${icons.trash}</button>`}</td>
      </tr>`;
    }).join("")}</tbody></table></div>`;

  box.querySelectorAll("[data-role]").forEach((s) => s.addEventListener("change", () => update(s.dataset.role, { role: s.value })));
  box.querySelectorAll("[data-active]").forEach((b) => b.addEventListener("click", () => {
    const on = b.getAttribute("aria-checked") !== "true";
    update(b.dataset.active, { is_active: on });
  }));
  box.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    const u = S.users.find((x) => String(x.id) === b.dataset.del);
    const ok = await confirmDialog({ title: t("admin.deleteTitle", { name: u.name }), body: t("admin.deleteBody"), confirm: t("common.delete"), danger: true });
    if (!ok) return;
    try {
      await api.adminDeleteUser(u.id);
      S.users = S.users.filter((x) => x.id !== u.id);
      paintUsers();
      toast(t("admin.deleted"));
    } catch (e) { toast(errorMessage(e), "error"); }
  }));
}

async function update(id, data) {
  try {
    const u = await api.adminUpdateUser(id, data);
    const i = S.users.findIndex((x) => String(x.id) === String(id));
    if (i >= 0) S.users[i] = { ...S.users[i], ...u };
    paintUsers();
    toast(t("admin.updated"));
  } catch (e) {
    toast(errorMessage(e), "error");
    paintUsers();
  }
}

async function loadPreds() {
  try {
    const res = await api.adminPredictions();
    if (!S) return;
    const box = $("#a-preds", S.el);
    box.innerHTML = res.items.length ? `<div class="table-wrap"><table class="table">
      <thead><tr><th>${esc(t("admin.user"))}</th><th>${esc(t("history.phone"))}</th><th>${esc(t("predict.estimated"))}</th><th>${esc(t("history.result"))}</th><th>${esc(t("history.when"))}</th></tr></thead>
      <tbody>${res.items.map((p) => `<tr><td>${esc(p.user_name)}</td><td class="num" style="font-weight:700">${esc(p.phone_name)}</td>
        <td class="num">${esc(money(p.price))}</td><td>${verdictBadge(p.verdict)}</td><td class="faint">${esc(relTime(p.created_at))}</td></tr>`).join("")}</tbody></table></div>`
      : emptyState({ icon: icons.history, title: t("history.emptyTitle") });
  } catch (e) {
    $("#a-preds", S.el).innerHTML = `<p class="muted">${esc(errorMessage(e))}</p>`;
  }
}
