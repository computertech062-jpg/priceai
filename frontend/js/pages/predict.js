// پەڕەی پێشبینیی نرخ — گرنگترین پەڕەی سیستەمەکە
import { api } from "../api.js";
import { ensureSchema, featureLabel, href, navigate } from "../app.js";
import { timeChart } from "../charts.js";
import { phoneSearch } from "../components/phoneSearch.js";
import { icons } from "../icons.js";
import { isRtl, lang, t } from "../i18n.js";
import { store } from "../store.js";
import { $, countUp, debounce, emptyState, errorMessage, esc, money, num, pct, sampleBanner, setBusy, toast } from "../ui.js";

const PRIMARY = ["brand", "release_year", "ram_gb", "storage_gb", "chipset_tier"];
const VARIANT_FIELDS = ["ram_gb", "storage_gb"];

// پێشبینی تەنها بۆ مۆبایلێکی ڕاستەقینەی ناو کاتالۆگ (S.phone) دەکرێت:
//  - تایبەتمەندییەکان لە داتاکەوە دێن و قفڵن (تەنها بۆ پیشاندان).
//  - تەنها یەکێک لە جۆرە ڕاستەقینەکانی (RAM + بیرگە) هەڵدەبژێردرێت — S.phone.configs[S.config].
//  - تا مۆبایلێک هەڵنەبژێردرێت، هیچ فۆرم و پێشبینییەک نییە.

let S = null; // دۆخی پەڕەکە

export function destroy() {
  S?.ctrl?.abort();
  S?.live?.cancel?.();
  S = null;
}

export async function render(el, params) {
  const schema = await ensureSchema();
  S = {
    el, schema, values: {}, phone: null, config: 0,
    asked: params.get("asked") || "", result: null, ctrl: null,
  };
  schema.features.forEach((f) => { S.values[f.name] = f.default ?? null; });

  el.innerHTML = `
    <div class="container page">
      <div class="page-head">
        <div><h1 class="page-title">${esc(t("predict.title"))}</h1><p class="page-sub">${esc(t("predict.sub"))}</p></div>
      </div>
      ${schema.is_sample_data ? `<div style="margin-bottom:20px">${sampleBanner()}</div>` : ""}
      <div class="split">
        <section class="side card stack gap-20" aria-labelledby="form-title" id="form-card">
          <h2 id="form-title" class="sr-only">${esc(t("predict.formTitle"))}</h2>
          <div class="field">
            <span class="field-label">${esc(t("predict.phoneName"))}</span>
            <div id="p-search"></div>
            <div id="p-phone-info"></div>
          </div>
          <div id="p-variants"></div>
          <div id="p-fields" class="stack gap-20"></div>
          <button type="button" class="btn btn-primary btn-lg btn-block" id="p-go" hidden>${icons.sparkle}${esc(t("predict.go"))}</button>
          <p class="hint" style="text-align:center" id="p-save-note" hidden></p>
        </section>
        <div class="main stack gap-24" id="p-result" aria-live="polite">
          <div class="card">${emptyState({ icon: icons.phone, title: t("predict.emptyTitle"), body: t("predict.emptyBody") })}</div>
        </div>
      </div>
    </div>`;

  S.search = phoneSearch($("#p-search", el), {
    onSelect: (p) => loadPhone(p.id, {}, true),
  });
  $("#p-go", el).addEventListener("click", () => predict({ save: true, button: $("#p-go", el) }));
  S.live = debounce(() => predict({ save: false, live: true }), 380);
  renderSaveNote();

  // ---- بارکردن لە URL ----
  try {
    if (params.get("phone")) {
      await loadPhone(params.get("phone"), { ram: params.get("ram"), storage: params.get("storage") }, true);
    } else if (params.get("history")) {
      // پێشبینییەکی پێشوو: هەمان مۆبایل و هەمان جۆر (ئەگەر هێشتا لە کاتالۆگدا هەبێت)
      const item = await api.historyItem(params.get("history"));
      const f = item.features || {};
      S.asked = item.asked_price ? String(item.asked_price) : "";
      const phone = item.phone_id ? await api.phone(item.phone_id).catch(() => null) : null;
      if (phone) {
        await loadPhone(phone.id, { ram: f.ram_gb, storage: f.storage_gb }, false);
        await predict({ save: false });
      } else {
        S.search.setValue(item.phone_name || "");
        S.search.focus();
        toast(t("err.phone_not_found"), "error");
      }
    } else if (params.get("q")) {
      S.search.setValue(params.get("q"));
      const first = await S.search.searchFirst(params.get("q"));
      if (first) await loadPhone(first.id, {}, true);
      else { S.search.focus(); toast(t("search.noResults"), "error"); }
    } else {
      S.search.focus();
    }
  } catch (e) {
    toast(errorMessage(e), "error");
  }
}

// ---------------- مۆبایل و جۆرەکانی ----------------
async function loadPhone(id, { ram, storage } = {}, run = false) {
  try {
    const phone = await api.phone(id);
    if (!S) return;
    S.phone = phone;
    S.search.setValue(phone.name);
    $("#p-go", S.el).hidden = false;
    $("#p-save-note", S.el).hidden = false;
    applyConfig(pickConfig(phone, ram, storage));
    renderPhoneInfo();
    renderVariants();
    renderFields();
    if (run) await predict({ save: true });
  } catch (e) {
    toast(errorMessage(e), "error");
  }
}

// جۆری داواکراو، ئەگەرنا یەکەم جۆر کە نرخی بازاڕی هەیە، ئەگەرنا یەکەم جۆری پشتڕاستکراو
function pickConfig(phone, ram, storage) {
  const cs = phone.configs || [];
  let i = -1;
  if (ram || storage) {
    i = cs.findIndex((c) => (!ram || String(c.ram_gb) === String(ram)) && (!storage || String(c.storage_gb) === String(storage)));
  }
  if (i < 0) i = cs.findIndex((c) => c.price_usd);
  if (i < 0) i = cs.findIndex((c) => c.verified);
  return Math.max(0, i);
}

function applyConfig(idx) {
  const p = S.phone;
  S.config = idx;
  // هەموو تایبەتمەندییەکان لە داتاکەوە، تەنانەت ئەوانەی نەزانراون (null)
  S.schema.features.forEach((f) => { if (f.name in p.specs) S.values[f.name] = p.specs[f.name]; });
  const c = p.configs[idx];
  S.values.ram_gb = c.ram_gb;
  S.values.storage_gb = c.storage_gb;
}

function clearPhone() {
  S.ctrl?.abort();
  S.phone = null;
  S.result = null;
  S.liveOn = false;
  renderPhoneInfo();
  renderVariants();
  renderFields();
  $("#p-go", S.el).hidden = true;
  $("#p-save-note", S.el).hidden = true;
  const res = $("#p-result", S.el);
  res.parentElement.classList.remove("has-result");
  res.innerHTML = `<div class="card">${emptyState({ icon: icons.phone, title: t("predict.emptyTitle"), body: t("predict.emptyBody") })}</div>`;
}

function renderPhoneInfo() {
  const box = $("#p-phone-info", S.el);
  if (!box) return;
  if (S.phone) {
    box.innerHTML = `<div class="row wrap between gap-8" style="margin-top:4px">
        <span class="autofill-note">${icons.check}${esc(t("predict.autofilled"))}</span>
        <button type="button" class="link-btn" id="p-clear" style="font-size:13px">${esc(t("predict.clear"))}</button>
      </div>`;
    $("#p-clear", box).addEventListener("click", () => { S.search.setValue(""); clearPhone(); S.search.focus(); });
  } else {
    box.innerHTML = "";
  }
}

function storageLabel(gb) { return gb >= 1024 ? `${gb / 1024} TB` : `${gb} GB`; }

function renderVariants() {
  const box = $("#p-variants", S.el);
  if (!box) return;
  const cs = S.phone?.configs || [];
  if (!cs.length) { box.innerHTML = ""; return; }
  const anyGuess = cs.some((c) => !c.verified);
  box.innerHTML = `
    <div class="field">
      <span class="field-label" id="var-label">${esc(t("predict.whichVariant"))}</span>
      <div class="variant-list ltr" role="group" aria-labelledby="var-label">
        ${cs.map((c, i) => `<button type="button" class="chip-btn${c.verified ? "" : " chip-guess"}" data-v="${i}" aria-pressed="${i === S.config}"
          ${c.verified ? "" : `title="${esc(t("predict.guessTitle"))}"`}>${c.ram_gb} GB · ${storageLabel(c.storage_gb)}${c.verified ? "" : " ≈"}</button>`).join("")}
      </div>
      ${anyGuess ? `<span class="hint">≈ ${esc(t("predict.guessNote"))}</span>` : ""}
      <details class="hint" style="margin-top:2px">
        <summary style="cursor:pointer;color:var(--accent-text);font-weight:600">${esc(t("predict.howToFind"))}</summary>
        <div class="stack gap-4" style="margin-top:8px;line-height:1.8">
          <span><strong>Android:</strong> ${esc(t("predict.findAndroid"))}</span>
          <span><strong>iPhone:</strong> ${esc(t("predict.findIphone"))}</span>
        </div>
      </details>
    </div>`;
  box.querySelectorAll("[data-v]").forEach((b) => b.addEventListener("click", () => {
    applyConfig(Number(b.dataset.v));
    box.querySelectorAll("[data-v]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    renderFields();
    if (S.result) S.live(); else predict({ save: true });
  }));
}

// ---------------- فۆرمی تایبەتمەندییەکان ----------------
function fieldHtml(f) {
  const v = S.values[f.name];
  const id = `f-${f.name}`;
  const label = esc(f.label[lang()] || f.label.en);
  // تایبەتمەندییەکانی مۆبایلی ناو کاتالۆگ لە داتاکەوە دێن و ناگۆڕدرێن: تەنها پیشاندان
  const dis = "disabled";
  if (f.kind === "binary") {
    return `<div class="switch-row"><span id="${id}-l" style="font-weight:700">${label}</span>
      <button type="button" class="switch" role="switch" name="${f.name}" aria-labelledby="${id}-l" aria-checked="${Number(v) === 1}" disabled></button></div>`;
  }
  if (f.kind === "categorical") {
    const opts = [...(f.options || [])];
    if (v && !opts.includes(v)) opts.unshift(v);
    return `<div class="field"><label for="${id}">${label}</label><div class="select-wrap">
      <select class="select" id="${id}" name="${f.name}" ${dis}>${opts.map((o) => `<option value="${esc(o)}" ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></div></div>`;
  }
  if (f.name === "chipset_tier") {
    const tiers = f.tiers?.[lang()] || f.tiers?.en || [];
    return `<div class="field"><span class="field-label" id="${id}-l">${label}</span>
      <div class="tier-group" role="group" aria-labelledby="${id}-l">
        ${tiers.map((name, i) => `<button type="button" class="chip-btn" data-field="${f.name}" data-val="${i + 1}" aria-pressed="${Number(v) === i + 1}" ${dis}>${esc(name)}</button>`).join("")}
      </div>${S.phone?.chipset ? `<span class="hint">${esc(t("predict.chipset"))}: <span class="num">${esc(S.phone.chipset)}</span></span>` : ""}</div>`;
  }
  if (f.choices) {
    const choices = [...f.choices];
    if (v !== null && v !== undefined && !choices.includes(Number(v))) choices.push(Number(v));
    choices.sort((a, b) => a - b);
    const fmt = (c) => (f.name === "storage_gb" ? storageLabel(c) : `${c} ${f.unit}`);
    return `<div class="field"><span class="field-label" id="${id}-l">${label}</span>
      <div class="chips ltr" role="group" aria-labelledby="${id}-l" style="justify-content:${isRtl() ? "flex-end" : "flex-start"}">
        ${choices.map((c) => `<button type="button" class="chip-btn" data-field="${f.name}" data-val="${c}" aria-pressed="${Number(v) === c}" ${dis}>${esc(fmt(c))}</button>`).join("")}
      </div><span class="field-error" id="${id}-err" hidden></span></div>`;
  }
  return `<div class="field"><label for="${id}">${label}</label>
    <div class="input-group"><input class="input input-num" id="${id}" name="${f.name}" type="number" inputmode="decimal"
      min="${f.min}" max="${f.max}" step="${f.step}" value="${v ?? ""}" dir="ltr" ${dis}
      ${v === null || v === undefined ? `placeholder="${esc(t("predict.unknown"))}"` : ""}>
      ${f.unit ? `<span class="unit">${esc(f.unit)}</span>` : ""}</div>
    <span class="field-error" id="${id}-err" hidden></span></div>`;
}

function renderFields() {
  const box = $("#p-fields", S.el);
  if (!box) return;
  if (!S.phone) { box.innerHTML = ""; return; } // پێش هەڵبژاردنی مۆبایل هیچ تایبەتمەندییەک نییە
  const byName = Object.fromEntries(S.schema.features.map((f) => [f.name, f]));
  // RAM و بیرگە تەنها لە لیستی جۆرە ڕاستەقینەکانەوە (سەرەوە) هەڵدەبژێردرێن
  const primary = PRIMARY.filter((n) => !VARIANT_FIELDS.includes(n)).map((n) => byName[n]).filter(Boolean);
  const rest = S.schema.features.filter((f) => !PRIMARY.includes(f.name));
  const groups = {};
  rest.forEach((f) => { (groups[f.group] ||= []).push(f); });
  const wasOpen = $("#p-more", box)?.open ?? false;
  const [brand, year, ...others] = primary;
  box.classList.add("locked");
  box.innerHTML = `
    <div class="lock-note"><span>${esc(t("predict.locked"))}</span></div>
    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px">${[brand, year].filter(Boolean).map(fieldHtml).join("")}</div>
    ${others.map(fieldHtml).join("")}
    <details class="disclosure" id="p-more" ${wasOpen ? "open" : ""}>
      <summary>${esc(t("predict.moreSpecs"))}${icons.chevron}</summary>
      <div class="stack gap-20" style="margin-top:16px">
        ${Object.entries(groups).map(([g, fs]) => `
          <div class="stack gap-12">
            <span class="faint" style="font-size:13px;font-weight:700">${esc(S.schema.groups[g]?.[lang()] || g)}</span>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px">${fs.map(fieldHtml).join("")}</div>
          </div>`).join("")}
      </div>
    </details>`;

}

function renderSaveNote() {
  const n = $("#p-save-note", S.el);
  if (!n) return;
  n.innerHTML = store.user ? esc(t("predict.savedNote"))
    : `${esc(t("predict.guestNote"))} <a href="#/login?next=predict">${esc(t("auth.login"))}</a>`;
}

// ---------------- پێشبینی ----------------
async function predict({ save = false, live = false, button = null } = {}) {
  if (!S || !S.phone) return; // تەنها بۆ مۆبایلێکی ناو کاتالۆگ
  S.ctrl?.abort();
  S.ctrl = new AbortController();
  const asked = parseFloat(S.asked);
  const payload = {
    features: S.values,
    asked_price: Number.isFinite(asked) && asked > 0 ? asked : null,
    phone_id: S.phone.id,
    phone_name: S.phone.name,
    save: save && !!store.user,
    explain: true,
    similar: true,
  };
  if (!S.result) renderLoading();
  else $("#r-card", S.el)?.setAttribute("aria-busy", "true");
  if (button) setBusy(button, true);
  try {
    const r = await api.predict(payload, S.ctrl.signal);
    if (!S) return;
    const prev = S.result;
    S.result = r;
    if (!prev || !$("#r-card", S.el)) buildResult();
    if (live) S.liveOn = true;
    updateResult(r, prev);
    if (payload.save && r.prediction_id) toast(t("predict.saved"));
    if (!live && prev && window.innerWidth < 960) $("#p-result", S.el)?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    if (e.name === "AbortError") return;
    if (e.field) e.fieldLabel = featureLabel(e.field);
    toast(errorMessage(e), "error");
    if (!S.result) $("#p-result", S.el).innerHTML = `<div class="card">${emptyState({ icon: icons.alert, title: t("err.pageTitle"), body: errorMessage(e) })}</div>`;
  } finally {
    if (button) setBusy(button, false);
    $("#r-card", S.el)?.removeAttribute("aria-busy");
  }
}

function renderLoading() {
  $("#p-result", S.el).innerHTML = `
    <div class="card card-raised stack gap-20">
      <div class="skeleton" style="height:18px;width:40%"></div>
      <div class="skeleton" style="height:76px;width:60%"></div>
      <div class="skeleton" style="height:12px"></div>
      <div class="skeleton" style="height:120px"></div>
    </div>
    <div class="card"><div class="skeleton" style="height:220px"></div></div>`;
}

function buildResult() {
  S.historyKey = null; // بەشی مێژوو نوێ دروست دەبێتەوە
  $("#p-result", S.el).parentElement.classList.add("has-result");
  $("#p-result", S.el).innerHTML = `
    <div class="print-only" style="margin-bottom:8px"><h1 style="font-size:24px">PriceAI — ${esc(t("predict.reportTitle"))}</h1>
      <p class="faint" id="r-print-date"></p></div>

    <section class="card card-raised stack gap-24 fade-in" id="r-card" aria-labelledby="r-title">
      <div class="row wrap between gap-16" style="align-items:flex-start">
        <div class="stack gap-6" style="min-width:0">
          <h2 id="r-title" class="num" style="font-size:20px;font-weight:700"></h2>
          <div class="row wrap gap-8" id="r-chips"></div>
        </div>
        <div class="row gap-8 no-print">
          <button type="button" class="icon-btn" id="r-share" aria-label="${esc(t("predict.share"))}" title="${esc(t("predict.share"))}">${icons.share}</button>
          <button type="button" class="icon-btn" id="r-compare" aria-label="${esc(t("predict.addCompare"))}" title="${esc(t("predict.addCompare"))}">${icons.compare}</button>
          <button type="button" class="btn btn-ghost btn-sm" id="r-pdf">${icons.download}PDF</button>
        </div>
      </div>
      <div class="stack gap-8">
        <div class="row wrap gap-12" style="align-items:center">
          <span class="muted" style="font-size:14px">${esc(t("predict.estimated"))}</span>
          <span class="badge badge-accent no-print" id="r-live" hidden><span class="live-dot"></span>${esc(t("predict.live"))}</span>
        </div>
        <div class="row wrap gap-16" style="align-items:baseline">
          <span class="result-price" id="r-price">$0</span>
          <span class="delta" id="r-delta"></span>
        </div>
        <div class="hint" id="r-market" hidden></div>
      </div>
      <div class="stack gap-10">
        <div class="row between" style="font-size:14px">
          <strong>${esc(t("predict.rangeTitle"))}</strong>
          <span class="num muted ltr" id="r-range"></span>
        </div>
        <div class="range" role="img" id="r-range-bar"><div class="fill" id="r-fill"></div><div class="knob" id="r-knob"></div></div>
        <p class="hint" id="r-conf"></p>
      </div>
    </section>

    <section class="card stack gap-16" aria-labelledby="v-title">
      <div class="row wrap between gap-12">
        <label for="v-asked" id="v-title" style="font-size:17px;font-weight:800">${esc(t("predict.askedTitle"))}</label>
        <div class="input-group has-lead" style="width:170px">
          <span class="unit lead">$</span>
          <input class="input input-num" id="v-asked" type="number" inputmode="decimal" min="0" placeholder="${esc(t("predict.askedPh"))}"
            style="font-size:18px;font-weight:700">
        </div>
      </div>
      <p class="hint">${esc(t("predict.askedHint"))}</p>
      <div class="gauge-wrap" aria-hidden="true">
        <div class="gauge"><div class="z-cheap"></div><div class="z-fair"></div><div class="z-exp"></div></div>
        <div class="gauge-marker" id="v-marker" hidden></div>
      </div>
      <div class="gauge-labels"><span>${esc(t("verdict.cheap"))}</span><span>${esc(t("verdict.fair"))}</span><span>${esc(t("verdict.expensive"))}</span></div>
      <div class="verdict-box v-none" id="v-box"></div>
    </section>

    <section class="card stack gap-18" aria-labelledby="x-title">
      <div class="row wrap between gap-8">
        <h2 id="x-title" class="card-title">${esc(t("predict.why"))}</h2>
        <span class="card-sub" id="x-method"></span>
      </div>
      <p class="explain-text" id="x-text"></p>
      <div class="stack gap-12" id="x-bars"></div>
      <div class="legend">
        <span><i style="background:var(--blue)"></i>${esc(t("predict.raised"))}</span>
        <span><i style="background:var(--orange)"></i>${esc(t("predict.lowered"))}</span>
      </div>
      <p class="hint" id="x-base"></p>
    </section>

    <section class="card stack gap-16" aria-labelledby="h-title" id="h-card" hidden>
      <div class="row wrap between gap-8">
        <h2 id="h-title" class="card-title">${esc(t("timeline.title"))}</h2>
        <span class="card-sub" id="h-type"></span>
      </div>
      <div class="h-stats" id="f-stats"></div>
      <p class="hint" id="f-ai" hidden></p>
      <div id="h-chart"></div>
      <div class="legend" id="h-legend"></div>
      <div class="stack gap-8" id="f-why">
        <strong>${esc(t("timeline.why"))}</strong>
        <ul class="f-reasons" id="f-reasons"></ul>
      </div>
      <p class="hint" id="f-battery" hidden></p>
      <div class="stack gap-10" id="h-block" hidden>
        <strong>${esc(t("history.title"))}</strong>
        <div class="h-stats" id="h-stats"></div>
        <p class="explain-text" id="h-text"></p>
        <p class="hint" id="h-note"></p>
      </div>
      <p class="hint" id="f-accuracy"></p>
    </section>

    <section class="stack gap-14 no-print" aria-labelledby="s-title">
      <h2 id="s-title" class="card-title">${esc(t("predict.similar"))}</h2>
      <div class="grid-cards" id="s-list" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr))"></div>
    </section>`;

  const asked = $("#v-asked", S.el);
  asked.value = S.asked;
  asked.addEventListener("input", () => { S.asked = asked.value; updateVerdict(); });
  $("#r-pdf", S.el).addEventListener("click", () => {
    $("#r-print-date", S.el).textContent = new Date().toLocaleString(lang() === "en" ? "en-US" : "en-GB");
    window.print();
  });
  $("#r-share", S.el).addEventListener("click", share);
  $("#r-compare", S.el).addEventListener("click", addToCompare);
}

function valueLabel(name, value) {
  const f = S.schema.features.find((x) => x.name === name);
  if (!f || value === null || value === undefined) return "—";
  if (f.kind === "binary") return Number(value) === 1 ? t("common.yes") : t("common.no");
  if (f.name === "chipset_tier") return (f.tiers?.[lang()] || [])[Number(value) - 1] || String(value);
  if (f.name === "storage_gb") return storageLabel(Number(value));
  if (f.name === "release_year") return String(Math.round(value));
  if (f.kind === "numeric") return `${num(value, f.step < 1 ? 1 : 0)}${f.unit ? ` ${f.unit}` : ""}`;
  return String(value);
}

function updateResult(r, prev) {
  $("#r-title", S.el).textContent = S.phone.name;
  $("#r-chips", S.el).innerHTML = [
    `${r.features.ram_gb ?? "—"} GB RAM`, valueLabel("storage_gb", r.features.storage_gb),
    valueLabel("main_camera_mp", r.features.main_camera_mp), valueLabel("battery_mah", r.features.battery_mah),
  ].map((c) => `<span class="chip">${esc(c)}</span>`).join("");

  countUp($("#r-price", S.el), r.price, { from: prev ? prev.price : Math.round(r.price * 0.6), duration: prev ? 450 : 900 });
  const d = prev ? r.price - prev.price : 0;
  const delta = $("#r-delta", S.el);
  delta.className = `delta ${d > 0 ? "up" : d < 0 ? "down" : ""}`;
  delta.textContent = prev && d !== 0 ? `${money(d, { sign: true })} ${t("predict.vsPrev")}` : "";
  $("#r-live", S.el).hidden = !S.liveOn;
  updateMarket(r);

  $("#r-range", S.el).textContent = `${money(r.low)} – ${money(r.high)}`;
  const lo = r.low * 0.7;
  const hi = r.high * 1.3;
  const pos = (v) => `${(((v - lo) / (hi - lo)) * 100).toFixed(2)}%`;
  $("#r-fill", S.el).style.left = pos(r.low);
  $("#r-fill", S.el).style.width = `${(((r.high - r.low) / (hi - lo)) * 100).toFixed(2)}%`;
  $("#r-knob", S.el).style.left = pos(r.price);
  $("#r-range-bar", S.el).setAttribute("aria-label", `${money(r.low)} – ${money(r.high)}`);
  $("#r-conf", S.el).textContent = t("predict.confidence", { n: r.confidence, model: r.model });

  updateVerdict();
  updateExplanation(r);
  updateSimilar(r);
  updateHistory();
}

// ---------------- نرخ بە پێی کات: مێژوو (archive.org) + پێشبینیی ئەمڕۆ و دوای ساڵێک ----------------
async function updateHistory() {
  const card = $("#h-card", S.el);
  if (!card || !S.phone) return;
  const c = S.phone.configs[S.config] || {};
  const key = `${S.phone.id}|${c.ram_gb}|${c.storage_gb}`;
  if (S.historyKey === key) return;
  S.historyKey = key;
  const [h, f] = await Promise.all([
    api.priceHistory(S.phone.id, c.ram_gb, c.storage_gb).catch(() => ({ available: false })),
    api.forecast(S.phone.id, c.ram_gb, c.storage_gb, S.result?.price).catch(() => ({ available: false })),
  ]);
  if (!S || S.historyKey !== key) return;
  if (!h.available && !f.available) { card.hidden = true; return; }
  card.hidden = false;
  const ym = (d) => d.slice(0, 7);
  const iso = (x) => `⁦${x}⁩`;
  const tone = (v) => (v < 0 ? "down" : v > 0 ? "up" : "");
  const stat = ([label, value, cls, sub]) => `<div class="h-stat"><span class="faint">${esc(label)}</span>`
    + `<strong class="num ltr ${cls}">${esc(value)}</strong>${sub ? `<span class="faint num ltr">${esc(sub)}</span>` : ""}</div>`;
  $("#h-type", S.el).textContent = h.available ? `${t(`history.type.${h.price_type}`)} · ${h.source}` : "";

  // ---- نرخی مۆدێلی سەرەکیی AI (تەنها تایبەتمەندییەکان). ئەگەر پێشبینییەکە خۆی لەوەوە دەست پێبکات، دووبارە نییە.
  const aiNow = S.result?.price;
  const model = f.available && f.basis !== "ai" && aiNow
    ? { now: aiNow, next: Math.round(aiNow * (f.next_year.price / f.today.price)) }
    : null;

  // ---- پێشبینی
  $("#f-why", S.el).hidden = !f.available;
  if (f.available) {
    const o = f.observed;
    $("#f-stats", S.el).innerHTML = [
      [t(`timeline.basis.${f.basis}`, { d: ym(o.date) }), money(o.price), "", t("history.age", { n: o.age_months })],
      [t("timeline.today", { d: ym(f.today.date) }), money(f.today.price), "", `${money(f.today.low)} – ${money(f.today.high)}`],
      [t("timeline.nextYear", { d: ym(f.next_year.date) }), money(f.next_year.price), tone(f.change_pct),
        `${pct(f.change_pct, 1, true)} · ${money(f.next_year.low)} – ${money(f.next_year.high)}`],
      ...(model ? [[t("timeline.aiModel"), money(model.now), "", t("timeline.aiModelSub", { v: money(model.next) })]] : []),
    ].map(stat).join("");
    const aiBox = $("#f-ai", S.el);
    aiBox.hidden = !model;
    if (model) {
      aiBox.textContent = t("timeline.aiNote", {
        ai: iso(money(model.now)), d: iso(pct(((model.now - f.today.price) / f.today.price) * 100, 1, true)),
      });
    }
    const pc = f.peer_change_pct;
    const reasons = [
      t("timeline.rPeers", {
        name: S.phone.name, a: f.today.age_months, n: f.n_peers, m: iso(pct(pc.median, 1, true)),
        lo: iso(pct(pc.p10, 1, true)), hi: iso(pct(pc.p90, 1, true)),
        peers: f.peers.slice(0, 5).map((x) => x.replace(/^(Apple|Samsung|Xiaomi|Google) /, "")).join(", "),
      }),
      t(f.today.age_months < 6 ? "timeline.rLaunch" : f.today.age_months < 18 ? "timeline.rSuccessor" : "timeline.rMature"),
      t(`timeline.scope.${f.scope}`),
    ];
    $("#f-reasons", S.el).innerHTML = reasons.map((x) => `<li>${esc(x)}</li>`).join("");
    const bat = $("#f-battery", S.el);
    bat.hidden = !f.battery;
    if (f.battery) bat.textContent = t("timeline.battery", { h: iso(`${f.battery.health_pct}%`), c: f.battery.rated_cycles });
    $("#f-accuracy", S.el).textContent = f.accuracy?.mape != null
      ? t("timeline.accuracy", {
        e: iso(pct(f.accuracy.mape, 1)), naive: iso(pct(f.accuracy.naive_mape, 1)), n: f.accuracy.n,
        cov: iso(pct(f.accuracy.coverage_heldout_pct, 0)),
      })
      : "";
  } else {
    $("#f-ai", S.el).hidden = true;
    $("#f-stats", S.el).innerHTML = "";
    $("#f-battery", S.el).hidden = true;
    $("#f-accuracy", S.el).textContent = "";
  }

  // ---- گراف: نرخە ڕاستەقینەکان (هێڵی پڕ) + پێشبینی (هێڵی پچڕپچڕ و مەودا)
  const real = h.available ? h.points.map((p) => ({
    date: p.date, value: p.price_usd,
    title: `${ym(p.date)}: ${money(p.price_usd)} (৳${num(p.price_bdt)} · ${t("history.age", { n: p.age_months })})`,
  })) : [];
  const fc = f.available ? [
    { date: f.observed.date, value: f.observed.price, low: f.observed.price, high: f.observed.price,
      title: `${ym(f.observed.date)}: ${money(f.observed.price)}` },
    { ...f.today, value: f.today.price,
      title: `${t("timeline.today", { d: ym(f.today.date) })}: ${money(f.today.price)} (${money(f.today.low)} – ${money(f.today.high)})` },
    { ...f.next_year, value: f.next_year.price,
      title: `${t("timeline.nextYear", { d: ym(f.next_year.date) })}: ${money(f.next_year.price)} (${money(f.next_year.low)} – ${money(f.next_year.high)})` },
  ] : [];
  const realBefore = fc.length ? real.filter((p) => p.date < fc[0].date) : real;
  const released = f.released || h.release_date;
  $("#h-chart", S.el).innerHTML = timeChart(realBefore, {
    ariaLabel: t("timeline.title"), forecast: fc,
    model: model ? [
      { date: f.today.date, value: model.now, title: `${t("timeline.aiModel")}: ${money(model.now)}` },
      { date: f.next_year.date, value: model.next, title: `${t("timeline.aiModelSub", { v: money(model.next) })}` },
    ] : [],
    marks: released ? [{ date: released, label: t("history.released") }] : [],
  });
  $("#h-legend", S.el).innerHTML = [
    realBefore.length || fc.length ? `<span><i style="background:var(--accent)"></i>${esc(t("timeline.legendReal"))}</span>` : "",
    fc.length ? `<span><i style="background:var(--mint)"></i>${esc(t("timeline.legendAi"))}</span>` : "",
    model ? `<span><i style="background:var(--blue)"></i>${esc(t("timeline.legendModel"))}</span>` : "",
  ].join("");

  // ---- پوختەی مێژوو
  $("#h-block", S.el).hidden = !h.available;
  if (h.available) {
    const s = h.summary;
    const first = h.points[0];
    const last = h.points[h.points.length - 1];
    $("#h-stats", S.el).innerHTML = [
      [t("history.first", { d: ym(first.date) }), money(first.price_usd), ""],
      [t("history.last", { d: ym(last.date) }), money(last.price_usd), ""],
      [t("history.change", { n: s.months }), pct(s.change_pct, 1, true), tone(s.change_pct)],
      [t("history.yearly"), pct(s.yearly_pct, 1, true), tone(s.yearly_pct)],
    ].map(stat).join("");
    $("#h-text", S.el).textContent = t(s.change_pct < 0 ? "history.fell" : "history.rose", {
      name: S.phone.name, n: s.months, p: iso(pct(Math.abs(s.change_pct), 1)), y: iso(pct(Math.abs(s.yearly_pct), 1)),
    });
    const notes = [t("history.fxNote", { usd: iso(pct(s.change_pct, 1, true)), local: iso(pct(s.change_pct_local, 1, true)) })];
    if (!h.exact_variant) notes.unshift(t("history.otherVariant", { v: `${h.ram_gb ? `${h.ram_gb} GB · ` : ""}${storageLabel(h.storage_gb)}` }));
    $("#h-note", S.el).textContent = notes.join(" ");
  }
}

// نرخی ڕاستەقینەی بازاڕ (تەنها بۆ مۆبایلی ناو کاتالۆگ کە نرخی ئەم جۆرەی هەیە، و داتای ڕاستەقینە)
function updateMarket(r) {
  const box = $("#r-market", S.el);
  const v = S.phone ? S.phone.configs[S.config] : null;
  if (!box) return;
  if (!v || !v.price_usd || r.is_sample_data) { box.hidden = true; return; }
  const meta = [v.source, v.n_sources > 1 ? t("predict.marketShops", { n: v.n_sources }) : null, v.price_date].filter(Boolean);
  const gap = Math.round(((r.price - v.price_usd) / v.price_usd) * 100);
  box.innerHTML = `<strong>${esc(t("predict.market"))}: <span class="num">${esc(money(v.price_usd))}</span></strong>`
    + (meta.length ? ` <span class="faint">· ${esc(meta.join(" · "))}</span>` : "")
    + `<br><span class="faint">${esc(t("predict.marketVs", { d: `${gap > 0 ? "+" : ""}${gap}%` }))}</span>`;
  box.hidden = false;
}

function updateVerdict() {
  const r = S.result;
  if (!r) return;
  const box = $("#v-box", S.el);
  const marker = $("#v-marker", S.el);
  const asked = parseFloat(S.asked);
  if (!Number.isFinite(asked) || asked <= 0) {
    box.className = "verdict-box v-none";
    box.innerHTML = `<span>${esc(t("predict.askedEmpty"))}</span>`;
    marker.hidden = true;
    return;
  }
  const diff = ((asked - r.price) / r.price) * 100;
  const status = asked > r.high ? "expensive" : asked < r.low ? "cheap" : "fair";
  let p;
  if (status === "cheap") p = Math.max(3, ((asked - r.low * 0.6) / (r.low * 0.4)) * 33.33);
  else if (status === "fair") p = 33.33 + ((asked - r.low) / Math.max(1, r.high - r.low)) * 33.33;
  else p = Math.min(97, 66.66 + ((asked - r.high) / (r.high * 0.4)) * 33.33);
  marker.hidden = false;
  marker.style.left = `${p}%`;
  box.className = `verdict-box v-${status}`;
  box.innerHTML = `<strong>${esc(t(`verdict.${status}`))}</strong><span>${esc(t(`verdict.${status}Note`, { pct: pct(Math.abs(diff), 0) }))}</span>`;
}

function updateExplanation(r) {
  const ex = r.explanation;
  if (!ex) return;
  const items = ex.items.filter((i) => Math.abs(i.phi) > 1e-4).slice(0, 8);
  const max = Math.max(1e-9, ...items.map((i) => Math.abs(i.phi)));
  $("#x-bars", S.el).innerHTML = items.map((i) => {
    const w = `${((Math.abs(i.phi) / max) * 100).toFixed(1)}%`;
    const up = i.phi >= 0;
    return `<div class="shap-row">
      <span class="shap-label">${esc(featureLabel(i.feature))}<small><bdi>${esc(valueLabel(i.feature, i.value))}</bdi></small></span>
      <div class="shap-track" role="img" aria-label="${esc(`${featureLabel(i.feature)}: ${money(i.usd, { sign: true })}`)}">
        <div class="neg">${up ? "" : `<div class="shap-bar" style="width:${w}"></div>`}</div>
        <div class="pos">${up ? `<div class="shap-bar" style="width:${w}"></div>` : ""}</div>
      </div>
      <span class="shap-val ${up ? "up" : "down"}" title="${esc(pct(i.pct, 1, true))}">${esc(money(i.usd, { sign: true }))}</span>
    </div>`;
  }).join("");
  // ڕستەی پوختە: ناوەندی داتاکە ← جیاوازی ← گەورەترین هۆکارەکان (دۆلارەکان کۆ دەبنەوە بۆ نرخ − ناوەند)
  const iso = (x) => `⁦${x}⁩`;
  const part = (i) => `${featureLabel(i.feature)} (⁨${valueLabel(i.feature, i.value)}⁩)`;
  const diff = r.price - ex.base_price;
  const sign = diff >= 0 ? 1 : -1;
  const main = ex.items.filter((i) => i.usd * sign > 0).sort((a, b) => b.usd * sign - a.usd * sign).slice(0, 3);
  const other = ex.items.filter((i) => i.usd * sign < 0).sort((a, b) => a.usd * sign - b.usd * sign)[0];
  const listOf = (xs) => {
    const s = xs.map((i) => `${part(i)} ${iso(money(i.usd, { sign: true }))}`);
    return s.length > 1 ? `${s.slice(0, -1).join(t("predict.listSep"))}${t("predict.listAnd")}${s[s.length - 1]}` : s.join("");
  };
  let text;
  if (Math.abs(diff) < Math.max(5, ex.base_price * 0.03) || !main.length) {
    text = t("predict.sumSame", { base: iso(money(ex.base_price)) });
  } else {
    text = t(diff > 0 ? "predict.sumMore" : "predict.sumLess", {
      base: iso(money(ex.base_price)), diff: iso(money(Math.abs(diff))), list: listOf(main),
    });
    // هۆکاری پێچەوانە تەنها ئەگەر بەڕاستی گرنگ بێت (≥ 10% ی جیاوازییەکە)
    if (other && Math.abs(other.usd) >= Math.max(5, Math.abs(diff) * 0.1)) {
      text += " " + t(diff > 0 ? "predict.sumOtherDown" : "predict.sumOtherUp", { f: part(other), usd: iso(money(Math.abs(other.usd))) });
    }
  }
  $("#x-text", S.el).textContent = text;
  $("#x-method", S.el).textContent = ex.method.startsWith("shap") ? `SHAP · ${ex.method.replace("shap.", "")}` : t("predict.methodSampling");
  $("#x-base", S.el).textContent = t("predict.baseNote", { base: `\u2066${money(ex.base_price)}\u2069` });
}

function updateSimilar(r) {
  const list = $("#s-list", S.el);
  const items = r.similar || [];
  if (!items.length) { list.innerHTML = `<p class="muted">${esc(t("predict.noSimilar"))}</p>`; return; }
  list.innerHTML = items.map((s) => `
    <button type="button" class="phone-card" data-id="${esc(s.id)}" data-ram="${esc(s.ram_gb)}" data-storage="${esc(s.storage_gb)}">
      <span class="p-name">${esc(s.name)}</span>
      <span class="faint" style="font-size:13px"><bdi class="num">${esc(s.ram_gb)} GB · ${esc(storageLabel(s.storage_gb))}</bdi></span>
      <span class="hint">${esc(t("predict.datasetPrice"))}</span>
      <span class="p-price">${esc(money(s.price_usd))}</span>
    </button>`).join("");
  list.querySelectorAll("[data-id]").forEach((b) => b.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    loadPhone(b.dataset.id, { ram: b.dataset.ram, storage: b.dataset.storage }, true);
  }));
}

// ---------------- هاوبەشکردن و بەراوردکردن ----------------
function shareParams() {
  const asked = parseFloat(S.asked);
  const extra = Number.isFinite(asked) && asked > 0 ? { asked } : {};
  const c = S.phone.configs[S.config];
  return { phone: S.phone.id, ram: c.ram_gb, storage: c.storage_gb, ...extra };
}

async function share() {
  const url = `${location.origin}${location.pathname}${href("predict", shareParams())}`;
  const title = `${S.phone?.name || "PriceAI"} — ${money(S.result.price)}`;
  try {
    if (navigator.share) { await navigator.share({ title, url }); return; }
  } catch { /* بەکارهێنەر هەڵیوەشاندەوە */ return; }
  try {
    await navigator.clipboard.writeText(url);
    toast(t("predict.linkCopied"));
  } catch {
    window.prompt(t("predict.copyLink"), url);
  }
}

function addToCompare() {
  const q = store.compareQueue;
  if (!S.phone) return;
  if (q.length >= 3) { toast(t("compare.full"), "error"); return; }
  const c = S.phone.configs[S.config];
  q.push({ phone_id: S.phone.id, phone_name: S.phone.name, features: { ...S.values },
    config: { ram_gb: c.ram_gb, storage_gb: c.storage_gb } });
  toast(t("compare.added", { n: q.length }));
  if (q.length >= 2) navigate("compare");
}
