// مێژووی پێشبینییەکان
import { api } from "../api.js";
import { href } from "../app.js";
import { lineChart } from "../charts.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { $, confirmDialog, debounce, emptyState, errorMessage, esc, money, relTime, toast, verdictBadge } from "../ui.js";

let S = null;
export function destroy() { S = null; }

export async function render(el) {
  S = { el, q: "", verdict: "", page: 1, items: [], total: 0 };
  el.innerHTML = `
    <div class="container page">
      <div class="page-head">
        <div><h1 class="page-title">${esc(t("history.title"))}</h1><p class="page-sub">${esc(t("history.sub"))}</p></div>
        <div class="row gap-10">
          <a class="btn btn-primary" href="#/predict">${icons.plus}${esc(t("history.new"))}</a>
          <button type="button" class="btn btn-ghost" id="h-clear">${icons.trash}${esc(t("history.clear"))}</button>
        </div>
      </div>
      <section class="card stack gap-12" id="h-chart-card" hidden style="margin-bottom:20px">
        <div class="row between"><h2 class="card-title">${esc(t("history.chartTitle"))}</h2><span class="card-sub">${esc(t("history.chartSub"))}</span></div>
        <div id="h-chart"></div>
      </section>
      <section class="card stack gap-16">
        <div class="row wrap gap-12 between">
          <div class="search-box" style="flex:1 1 280px;max-width:420px;border-width:1px">
            ${icons.search}<label class="sr-only" for="h-q">${esc(t("history.search"))}</label>
            <input id="h-q" type="search" placeholder="${esc(t("history.search"))}" dir="auto">
          </div>
          <div class="seg" role="group" aria-label="${esc(t("history.filter"))}">
            ${["", "cheap", "fair", "expensive"].map((v) => `<button type="button" data-verdict="${v}" aria-pressed="${v === ""}">${esc(v ? t(`verdict.${v}`) : t("history.all"))}</button>`).join("")}
          </div>
        </div>
        <div id="h-list"></div>
        <div id="h-more" style="text-align:center"></div>
      </section>
    </div>`;
  const search = debounce(() => { S.q = $("#h-q", el).value; load(true); }, 250);
  $("#h-q", el).addEventListener("input", search);
  el.querySelectorAll("[data-verdict]").forEach((b) => b.addEventListener("click", () => {
    S.verdict = b.dataset.verdict;
    el.querySelectorAll("[data-verdict]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    load(true);
  }));
  $("#h-clear", el).addEventListener("click", async () => {
    const ok = await confirmDialog({ title: t("history.clearTitle"), body: t("history.clearBody"), confirm: t("history.clear"), danger: true });
    if (!ok) return;
    try { await api.clearHistory(); toast(t("history.cleared")); load(true); } catch (e) { toast(errorMessage(e), "error"); }
  });
  await load(true);
}

async function load(reset) {
  if (!S) return;
  if (reset) { S.page = 1; S.items = []; $("#h-list", S.el).innerHTML = skeleton(); }
  try {
    const res = await api.history({ q: S.q, verdict: S.verdict, page: S.page, size: 20 });
    if (!S) return;
    S.items = S.items.concat(res.items);
    S.total = res.total;
    paint();
  } catch (e) {
    $("#h-list", S.el).innerHTML = emptyState({ icon: icons.alert, title: t("err.pageTitle"), body: errorMessage(e) });
  }
}

const skeleton = () => Array.from({ length: 4 }, () => `<div class="skeleton" style="height:56px;margin-bottom:10px"></div>`).join("");

function paint() {
  const list = $("#h-list", S.el);
  $("#h-clear", S.el).hidden = !S.items.length && !S.q && !S.verdict;
  if (!S.items.length) {
    list.innerHTML = S.q || S.verdict
      ? emptyState({ icon: icons.search, title: t("history.noMatch") })
      : emptyState({ icon: icons.history, title: t("history.emptyTitle"), body: t("history.emptyBody"),
        action: `<a class="btn btn-primary" href="#/predict">${esc(t("history.new"))}</a>` });
    $("#h-more", S.el).innerHTML = "";
    $("#h-chart-card", S.el).hidden = true;
    return;
  }
  list.innerHTML = `<div class="table-wrap"><table class="table">
    <thead><tr><th>${esc(t("history.phone"))}</th><th>${esc(t("history.specs"))}</th><th>${esc(t("predict.estimated"))}</th>
      <th>${esc(t("predict.rangeTitle"))}</th><th>${esc(t("history.result"))}</th><th>${esc(t("history.when"))}</th><th><span class="sr-only">${esc(t("common.actions"))}</span></th></tr></thead>
    <tbody>${S.items.map((p) => `
      <tr>
        <td class="num" style="font-weight:700">${esc(p.phone_name)}</td>
        <td class="num muted">${esc(p.ram_gb ?? "—")} / ${esc(p.storage_gb ?? "—")} GB</td>
        <td class="num" style="font-weight:700">${esc(money(p.price))}</td>
        <td class="num muted">${esc(money(p.low))} – ${esc(money(p.high))}</td>
        <td>${p.asked_price ? `<div class="row gap-8">${verdictBadge(p.verdict)}<span class="faint num" style="font-size:12.5px">${esc(money(p.asked_price))}</span></div>` : '<span class="faint">—</span>'}</td>
        <td class="faint" style="white-space:nowrap">${esc(relTime(p.created_at))}</td>
        <td><div class="row gap-6" style="justify-content:flex-end">
          <a class="btn btn-soft btn-sm" href="${esc(href("predict", { history: p.id }))}">${esc(t("history.open"))}</a>
          <button type="button" class="icon-btn" data-del="${p.id}" aria-label="${esc(t("common.delete"))}">${icons.trash}</button>
        </div></td>
      </tr>`).join("")}</tbody></table></div>`;
  list.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
    const ok = await confirmDialog({ title: t("history.deleteTitle"), confirm: t("common.delete"), danger: true });
    if (!ok) return;
    try {
      await api.deleteHistory(b.dataset.del);
      S.items = S.items.filter((x) => String(x.id) !== b.dataset.del);
      S.total -= 1;
      paint();
      toast(t("history.deleted"));
    } catch (e) { toast(errorMessage(e), "error"); }
  }));
  const more = $("#h-more", S.el);
  more.innerHTML = S.items.length < S.total
    ? `<button type="button" class="btn btn-ghost" id="h-load">${esc(t("history.loadMore", { n: S.total - S.items.length }))}</button>` : "";
  $("#h-load", S.el)?.addEventListener("click", () => { S.page += 1; load(false); });

  const pts = S.items.slice(0, 20).reverse().map((p) => ({ label: p.phone_name, value: p.price }));
  const card = $("#h-chart-card", S.el);
  card.hidden = pts.length < 2;
  if (pts.length >= 2) $("#h-chart", S.el).innerHTML = lineChart(pts, { ariaLabel: t("history.chartTitle") });
}
