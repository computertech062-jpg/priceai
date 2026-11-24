// پەڕەی سەرەکی
import { api } from "../api.js";
import { ensureModelInfo, navigate } from "../app.js";
import { phoneSearch } from "../components/phoneSearch.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { arrow, esc, money, num, sampleBanner } from "../ui.js";

const POPULAR = ["iPhone 17 Pro", "Galaxy S25", "Redmi Note 15", "Pixel 10"];

export async function render(el) {
  el.innerHTML = `
    <div id="home-banner" class="container" style="padding-top:16px"></div>
    <section class="container hero">
      <div class="hero-copy">
        <span class="pill"><span class="dot"></span>${esc(t("home.pill"))}</span>
        <h1>${esc(t("home.title1"))} <em>${esc(t("home.title2"))}</em></h1>
        <p class="hero-lead">${esc(t("home.lead"))}</p>
        <div id="home-search" style="max-width:600px"></div>
        <div class="row wrap gap-8" style="font-size:13px">
          <span class="faint">${esc(t("home.popular"))}</span>
          ${POPULAR.map((q) => `<button type="button" class="chip" data-q="${esc(q)}" style="border:0;cursor:pointer">${esc(q)}</button>`).join("")}
        </div>
      </div>
      <div class="hero-visual">${previewCard()}</div>
    </section>

    <section class="brands-strip" aria-label="${esc(t("home.brandsLabel"))}">
      <div class="container">
        <span class="faint" style="font-size:14px">${esc(t("home.brands"))}</span>
        <div class="brands-list ltr" id="brands"></div>
      </div>
    </section>

    <section class="section container">
      <div class="stack gap-12" style="max-width:640px;margin-bottom:44px">
        <span class="section-label">${esc(t("home.howLabel"))}</span>
        <h2>${esc(t("home.howTitle"))}</h2>
      </div>
      <div class="grid-cards" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">
        ${[1, 2, 3].map((i) => `
          <div class="card feature-card">
            <span class="step-num">0${i}</span>
            <h3 style="font-size:20px;font-weight:800">${esc(t(`home.step${i}`))}</h3>
            <p class="muted">${esc(t(`home.step${i}Body`))}</p>
          </div>`).join("")}
      </div>
    </section>

    <section class="section section-soft">
      <div class="container">
        <div class="stack gap-12" style="max-width:640px;margin-bottom:44px">
          <span class="section-label">${esc(t("home.featLabel"))}</span>
          <h2>${esc(t("home.featTitle"))}</h2>
        </div>
        <div class="grid-cards" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
          ${[
            ["wand", "accent", "autofill"], ["scale", "orange", "verdict"], ["sliders", "mint", "whatif"],
            ["chart", "blue", "explain"], ["compare", "accent", "compare"], ["layers", "blue", "similar"],
          ].map(([ic, c, k]) => `
            <div class="card feature-card">
              <span class="feature-ico ico-${c}">${icons[ic]}</span>
              <h3 style="font-size:19px;font-weight:800">${esc(t(`home.f.${k}`))}</h3>
              <p class="muted">${esc(t(`home.f.${k}Body`))}</p>
            </div>`).join("")}
        </div>
      </div>
    </section>

    <section class="section container">
      <div class="split" style="align-items:center;gap:48px">
        <div class="side stack gap-16">
          <span class="section-label">${esc(t("home.trustLabel"))}</span>
          <h2>${esc(t("home.trustTitle"))}</h2>
          <p class="muted" style="font-size:17px">${esc(t("home.trustBody"))}</p>
          <a href="#/model" class="row gap-8" style="font-weight:800">${esc(t("home.trustLink"))} ${arrow()}</a>
        </div>
        <div class="main grid-cards" id="home-metrics" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
          ${[1, 2, 3, 4].map(() => `<div class="card"><div class="skeleton" style="height:60px"></div></div>`).join("")}
        </div>
      </div>
    </section>

    <section class="container" style="padding-bottom:88px">
      <div class="cta">
        <div class="stack gap-10" style="max-width:620px">
          <h2 style="font-size:clamp(26px,3vw,36px);font-weight:900">${esc(t("home.ctaTitle"))}</h2>
          <p>${esc(t("home.ctaBody"))}</p>
        </div>
        <a class="btn btn-lg" href="#/predict">${esc(t("home.ctaBtn"))}</a>
      </div>
    </section>`;

  phoneSearch(el.querySelector("#home-search"), {
    submitLabel: t("home.searchBtn"),
    onSelect: (p) => navigate("predict", { phone: p.id }),
    onSubmitText: (q) => navigate("predict", { q }),
  });
  el.querySelectorAll("[data-q]").forEach((b) => b.addEventListener("click", () => navigate("predict", { q: b.dataset.q })));

  api.brands().then((d) => {
    const box = el.querySelector("#brands");
    if (box) box.innerHTML = d.brands.slice(0, 9).map((b) => `<span>${esc(b)}</span>`).join("");
  }).catch(() => {});

  ensureModelInfo().then((m) => {
    const box = el.querySelector("#home-metrics");
    if (!box) return;
    if (m.is_sample_data) el.querySelector("#home-banner").innerHTML = sampleBanner();
    const best = m.results.find((r) => r.name === m.best_model);
    box.innerHTML = [
      ["R²", num(best.test.r2, 3)],
      ["MAE", money(best.test.mae)],
      [t("home.mPhones"), num(m.dataset.models)],
      [t("home.mCoverage"), `${num(m.interval.test_coverage * 100, 0)}%`],
    ].map(([l, v]) => `<div class="card stat"><span class="stat-label">${esc(l)}</span><span class="stat-value">${esc(v)}</span></div>`).join("");
  }).catch(() => {
    const box = el.querySelector("#home-metrics");
    if (box) box.innerHTML = `<div class="card muted">${esc(t("err.model_unavailable"))}</div>`;
  });
}

function previewCard() {
  const rows = [["storage", 72, "up"], ["camera", 48, "up"], ["chipset", 30, "down"]];
  return `
    <div class="card card-raised" style="width:100%;max-width:440px;padding:28px;border-radius:26px" aria-hidden="true">
      <div class="row between" style="margin-bottom:20px">
        <div class="stack gap-4"><span class="faint" style="font-size:13px">${esc(t("home.previewLabel"))}</span>
          <span class="num" style="font-weight:700;font-size:20px">Galaxy A55</span></div>
        <span class="badge badge-fair"><span class="dot"></span>${esc(t("verdict.fair"))}</span>
      </div>
      <div class="row wrap gap-8" style="margin-bottom:22px">
        ${["8 GB RAM", "256 GB", "50 MP", "5000 mAh"].map((c) => `<span class="chip">${c}</span>`).join("")}
      </div>
      <div class="faint" style="font-size:14px">${esc(t("predict.estimated"))}</div>
      <div class="result-price" style="font-size:60px;text-align:start;margin:6px 0 20px">$ ···</div>
      <div class="range" style="margin-bottom:22px"><div class="fill" style="left:30%;width:40%"></div><div class="knob" style="left:50%"></div></div>
      <div class="stack gap-12" style="border-top:1px solid var(--border);padding-top:18px">
        <strong style="font-size:14px">${esc(t("predict.why"))}</strong>
        ${rows.map(([k, w, dir]) => `
          <div class="row gap-10" style="font-size:13px">
            <span class="muted" style="width:96px">${esc(t(`home.prev.${k}`))}</span>
            <div class="hbar-track grow"><div class="hbar-fill" style="width:${w}%;background:var(--${dir === "up" ? "blue" : "orange"})"></div></div>
            <span style="color:var(--${dir === "up" ? "blue" : "orange"}-text);font-weight:800">${dir === "up" ? "▲" : "▼"}</span>
          </div>`).join("")}
      </div>
    </div>`;
}
