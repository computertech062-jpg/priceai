// داشبۆرد
import { api } from "../api.js";
import { href } from "../app.js";
import { barChart, donutChart, hbars } from "../charts.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { store } from "../store.js";
import { arrow, emptyState, errorMessage, esc, money, num, relTime, sampleBanner, verdictBadge } from "../ui.js";

export async function render(el) {
  const d = await api.dashboard().catch((e) => ({ error: e }));
  if (d.error) {
    el.innerHTML = `<div class="container page"><div class="card">${emptyState({ icon: icons.alert, title: t("err.pageTitle"), body: errorMessage(d.error) })}</div></div>`;
    return;
  }
  const name = store.user?.name?.split(" ")[0] || "";
  const tile = (icon, label, value, extra = "") => `
    <div class="card stat"><span class="stat-label"><span class="stat-ico">${icons[icon]}</span>${esc(label)}</span>
      <span class="stat-value" ${extra}>${esc(value)}</span></div>`;
  const series = d.series.map((s) => ({ label: s.date.slice(5).replace("-", "/"), value: s.count, title: `${s.date}: ${s.count}` }));
  const v = d.verdicts;
  const vTotal = v.cheap + v.fair + v.expensive;

  el.innerHTML = `
    <div class="container page">
      <div class="page-head">
        <div><h1 class="page-title">${esc(t("dash.hello", { name }))}</h1><p class="page-sub">${esc(t("dash.sub"))}</p></div>
        <a class="btn btn-primary" href="#/predict">${icons.plus}${esc(t("history.new"))}</a>
      </div>
      ${d.model.is_sample_data ? `<div style="margin-bottom:20px">${sampleBanner()}</div>` : ""}
      <div class="grid-cards" style="margin-bottom:16px">
        ${tile("sparkle", t("dash.total"), num(d.total))}
        ${tile("target", t("dash.avg"), money(d.avg_price))}
        ${tile("history", t("dash.today"), num(d.today))}
        ${tile("chart", t("dash.r2"), d.model.r2 !== null ? num(d.model.r2, 3) : "—", 'style="color:var(--mint-text)"')}
      </div>
      ${d.admin ? `
        <div class="grid-cards" style="margin-bottom:16px">
          ${tile("users", t("dash.users"), num(d.admin.users))}
          ${tile("shield", t("dash.activeUsers"), num(d.admin.active_users))}
          ${tile("database", t("dash.allPredictions"), num(d.admin.predictions))}
          <a class="card stat" href="#/admin" style="color:var(--text)"><span class="stat-label"><span class="stat-ico">${icons.users}</span>${esc(t("nav.admin"))}</span>
            <span style="font-weight:800">${esc(t("dash.manage"))} ${arrow()}</span></a>
        </div>` : ""}

      <div class="split" style="margin-bottom:16px">
        <section class="main card stack gap-16" aria-labelledby="d-chart">
          <div class="row between wrap gap-8"><h2 class="card-title" id="d-chart">${esc(t("dash.chartTitle"))}</h2><span class="card-sub">${esc(t("dash.chartSub"))}</span></div>
          ${barChart(series, { ariaLabel: t("dash.chartTitle") })}
        </section>
        <section class="side card stack gap-20" aria-labelledby="d-verd">
          <h2 class="card-title" id="d-verd">${esc(t("dash.verdicts"))}</h2>
          ${vTotal ? `<div class="row gap-20 wrap">
            ${donutChart([
              { value: v.cheap, color: "var(--blue)", label: t("verdict.cheap") },
              { value: v.fair, color: "var(--mint)", label: t("verdict.fair") },
              { value: v.expensive, color: "var(--orange)", label: t("verdict.expensive") },
            ], { center: String(vTotal), ariaLabel: t("dash.verdicts") })}
            <div class="stack gap-10">${["cheap", "fair", "expensive"].map((k) => `<div class="row gap-10">${verdictBadge(k)}<span class="num" style="font-weight:700">${v[k]}</span></div>`).join("")}</div>
          </div>` : `<p class="muted">${esc(t("dash.noVerdicts"))}</p>`}
          <div class="stack gap-12">
            <h3 style="font-size:15px;font-weight:800">${esc(t("dash.brands"))}</h3>
            ${d.brands.length ? hbars(d.brands.map((b) => ({ label: b.brand, value: b.count, display: `${b.pct}%` }))) : `<p class="muted">—</p>`}
          </div>
        </section>
      </div>

      <section class="card stack gap-16" aria-labelledby="d-recent">
        <div class="row between wrap gap-8"><h2 class="card-title" id="d-recent">${esc(t("dash.recent"))}</h2><a href="#/history" style="font-weight:700">${esc(t("dash.viewAll"))}</a></div>
        ${d.recent.length ? `<div class="table-wrap"><table class="table"><thead><tr>
            <th>${esc(t("history.phone"))}</th><th>${esc(t("history.specs"))}</th><th>${esc(t("predict.estimated"))}</th><th>${esc(t("history.result"))}</th><th>${esc(t("history.when"))}</th></tr></thead>
          <tbody>${d.recent.map((p) => `<tr>
            <td class="num" style="font-weight:700"><a href="${esc(href("predict", { history: p.id }))}" style="color:var(--text)">${esc(p.phone_name)}</a></td>
            <td class="num muted">${esc(p.ram_gb ?? "—")} / ${esc(p.storage_gb ?? "—")} GB</td>
            <td class="num" style="font-weight:700">${esc(money(p.price))}</td>
            <td>${verdictBadge(p.verdict)}</td>
            <td class="faint">${esc(relTime(p.created_at))}</td></tr>`).join("")}</tbody></table></div>`
          : emptyState({ icon: icons.sparkle, title: t("history.emptyTitle"), body: t("history.emptyBody"), action: `<a class="btn btn-primary" href="#/predict">${esc(t("history.new"))}</a>` })}
      </section>
    </div>`;
}
