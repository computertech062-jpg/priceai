// ئەدای مۆدێل — بۆ بەحس و بەرگریکردن زۆر گرنگە
import { api } from "../api.js";
import { ensureModelInfo, ensureSchema, featureLabel } from "../app.js";
import { hbars, histogramChart, scatterChart } from "../charts.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { esc, money, num, sampleBanner } from "../ui.js";

export async function render(el) {
  const [m, bt] = await Promise.all([ensureModelInfo(), api.forecastBacktest().catch(() => null), ensureSchema()]);
  const best = m.results.find((r) => r.name === m.best_model);
  const sorted = [...m.results].sort((a, b) => a.cv.rmse - b.cv.rmse);
  const imp = m.importance.slice(0, 10);
  const tile = (label, value, sub = "") => `<div class="card stat"><span class="stat-label">${esc(label)}</span>
    <span class="stat-value">${esc(value)}</span>${sub ? `<span class="hint">${esc(sub)}</span>` : ""}</div>`;

  el.innerHTML = `
    <div class="container page">
      <div class="page-head">
        <div><h1 class="page-title">${esc(t("model.title"))}</h1><p class="page-sub">${esc(t("model.sub"))}</p></div>
        <span class="badge badge-accent">${icons.check}${esc(t("model.best"))}: ${esc(m.best_model)}</span>
      </div>
      ${m.is_sample_data ? `<div style="margin-bottom:20px">${sampleBanner()}</div>` : ""}
      <div class="grid-cards" style="margin-bottom:16px">
        ${tile("R²", num(best.test.r2, 4), t("model.r2Hint"))}
        ${tile("MAE", money(best.test.mae), t("model.maeHint"))}
        ${tile("RMSE", money(best.test.rmse), t("model.rmseHint"))}
        ${tile(t("model.coverage"), `${num(m.interval.test_coverage * 100, 1)}%`, t("model.coverageHint", { pct: num(m.interval.pct, 1) }))}
      </div>

      <section class="card stack gap-16" style="margin-bottom:16px" aria-labelledby="m-table">
        <div class="row between wrap gap-8"><h2 class="card-title" id="m-table">${esc(t("model.compareTitle"))}</h2><span class="card-sub">${esc(t("model.compareSub"))}</span></div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>${esc(t("model.algorithm"))}</th><th>CV RMSE</th><th>Test R²</th><th>Test MAE</th><th>Test RMSE</th><th>MAPE</th></tr></thead>
          <tbody>${sorted.map((r) => `
            <tr class="${r.name === m.best_model ? "best" : ""}">
              <td style="font-weight:700">${esc(r.name)} ${r.name === m.best_model ? `<span class="badge badge-accent" style="margin-inline-start:6px">${esc(t("model.selected"))}</span>` : ""}
                <div class="faint num" style="font-size:12px;font-weight:400">${esc(Object.entries(r.params).map(([k, v]) => `${k}=${v}`).join(", "))}</div></td>
              <td class="num">${esc(money(r.cv.rmse))} <span class="faint">± ${esc(num(r.cv.rmse_std, 1))}</span></td>
              <td class="num" style="font-weight:700">${esc(num(r.test.r2, 4))}</td>
              <td class="num">${esc(money(r.test.mae))}</td>
              <td class="num">${esc(money(r.test.rmse))}</td>
              <td class="num">${esc(num(r.test.mape, 1))}%</td>
            </tr>`).join("")}</tbody></table></div>
        <p class="hint">${esc(t("model.selectionNote"))}</p>
      </section>

      <div class="split" style="margin-bottom:16px">
        <section class="side card stack gap-12" aria-labelledby="m-scatter">
          <h2 class="card-title" id="m-scatter">${esc(t("model.scatterTitle"))}</h2>
          <p class="card-sub">${esc(t("model.scatterSub"))}</p>
          ${scatterChart(m.plots.scatter, { ariaLabel: t("model.scatterTitle"), xLabel: t("model.actual"), yLabel: t("model.predicted") })}
        </section>
        <div class="main stack gap-16">
          <section class="card stack gap-12" aria-labelledby="m-resid">
            <h2 class="card-title" id="m-resid">${esc(t("model.residTitle"))}</h2>
            <p class="card-sub">${esc(t("model.residSub"))}</p>
            ${histogramChart(m.plots.residuals.counts, m.plots.residuals.edges, { ariaLabel: t("model.residTitle") })}
          </section>
          <section class="card stack gap-14" aria-labelledby="m-imp">
            <h2 class="card-title" id="m-imp">${esc(t("model.impTitle"))}</h2>
            <p class="card-sub">${esc(t("model.impSub"))}</p>
            ${hbars(imp.map((i) => ({ label: featureLabel(i.feature), value: i.value, display: num(i.value, 3) })))}
          </section>
        </div>
      </div>

      <div class="split">
        <section class="side card stack gap-12" aria-labelledby="m-data">
          <h2 class="card-title" id="m-data">${esc(t("model.dataTitle"))}</h2>
          ${[
            [t("model.file"), m.dataset.file],
            [t("model.rows"), num(m.dataset.rows)],
            [t("model.phones"), num(m.dataset.models)],
            [t("model.brandsN"), num(m.dataset.brands)],
            [t("model.split"), `${num(m.dataset.train_rows)} / ${num(m.dataset.test_rows)}`],
            [t("model.featuresN"), num(m.dataset.features)],
            [t("model.priceRange"), `${money(m.dataset.price.min)} – ${money(m.dataset.price.max)}`],
            [t("model.trainedAt"), m.trained_at.replace("T", " ").slice(0, 16)],
          ].map(([k, v]) => `<div class="row between gap-12" style="border-bottom:1px solid var(--border);padding-bottom:10px"><span class="muted">${esc(k)}</span><span class="num" style="font-weight:700">${esc(v)}</span></div>`).join("")}
        </section>
        <section class="main card stack gap-14" aria-labelledby="m-method">
          <h2 class="card-title" id="m-method">${esc(t("model.methodTitle"))}</h2>
          <ol class="stack gap-10" style="margin:0;padding-inline-start:20px;line-height:1.9">
            ${[1, 2, 3, 4, 5, 6].map((i) => `<li>${esc(t(`model.m${i}`, { pct: num(m.interval.pct, 1), method: m.method.explanation }))}</li>`).join("")}
          </ol>
        </section>
      </div>
      ${forecastSection(bt, tile)}
    </div>`;
}

// پێشبینیی نرخ دوای ساڵێک: Backtest لەسەر نرخە ڕاستەقینە کۆنەکان (archive.org)
function forecastSection(bt, tile) {
  if (!bt || !bt.available) return "";
  const seg = Object.entries(bt.by_segment).sort((a, b) => b[1].n - a[1].n);
  const pts = bt.examples.map((e) => [e.real, e.ai]);
  return `
    <section class="card stack gap-16" style="margin-top:16px" aria-labelledby="m-fc">
      <div class="row between wrap gap-8"><h2 class="card-title" id="m-fc">${esc(t("model.fcTitle"))}</h2>
        <span class="card-sub">${esc(t("model.fcSub", { n: bt.n, p: bt.n_phones }))}</span></div>
      <div class="grid-cards">
        ${tile(t("model.fcMape"), `${num(bt.mape, 1)}%`, t("model.fcMapeHint", { m: num(bt.median_ape, 1) }))}
        ${tile(t("model.fcNaive"), `${num(bt.naive_mape, 1)}%`, t("model.fcNaiveHint"))}
        ${tile(t("model.fcCoverage"), `${num(bt.coverage_heldout_pct, 1)}%`, t("model.fcCoverageHint", { pct: num(bt.interval_pct, 1) }))}
      </div>
      <div class="split">
        <div class="side stack gap-8">
          <p class="card-sub">${esc(t("model.fcScatter"))}</p>
          ${scatterChart(pts, { ariaLabel: t("model.fcScatter"), xLabel: t("model.actual"), yLabel: t("model.predicted") })}
        </div>
        <div class="main stack gap-12">
          <div class="table-wrap"><table class="table">
            <thead><tr><th>${esc(t("model.fcSegment"))}</th><th>n</th><th>MAPE</th></tr></thead>
            <tbody>${seg.map(([k, v]) => `<tr><td>${esc(t(`model.seg.${k}`))}</td><td class="num">${v.n}</td><td class="num">${num(v.mape, 1)}%</td></tr>`).join("")}</tbody>
          </table></div>
          <ol class="stack gap-8" style="margin:0;padding-inline-start:20px;line-height:1.8">
            ${[1, 2, 3, 4].map((i) => `<li>${esc(t(`model.fc${i}`))}</li>`).join("")}
          </ol>
        </div>
      </div>
    </section>`;
}
