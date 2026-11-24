// بەراوردکردنی 2 یان 3 مۆبایل
import { api } from "../api.js";
import { ensureSchema, featureLabel, href } from "../app.js";
import { phoneSearch } from "../components/phoneSearch.js";
import { icons } from "../icons.js";
import { lang, t } from "../i18n.js";
import { store } from "../store.js";
import { $, emptyState, errorMessage, esc, money, num, pct, setBusy, toast, verdictBadge } from "../ui.js";

let S = null;
const ROWS = ["ram_gb", "storage_gb", "chipset_tier", "main_camera_mp", "front_camera_mp", "battery_mah",
  "fast_charge_w", "screen_inch", "refresh_rate_hz", "display_type", "has_5g", "has_nfc", "weight_g", "release_year"];
const LOWER_IS_BETTER = new Set(["weight_g"]);

export function destroy() { S = null; }

export async function render(el) {
  const schema = await ensureSchema();
  S = { el, schema, slots: [] };
  const queued = store.compareQueue.splice(0);
  for (const q of queued) S.slots.push({ phone: null, variant: 0, want: q.config, features: q.features, name: q.phone_name, phoneId: q.phone_id, asked: "" });
  while (S.slots.length < 2) S.slots.push(emptySlot());

  el.innerHTML = `
    <div class="container page">
      <div class="page-head">
        <div><h1 class="page-title">${esc(t("compare.title"))}</h1><p class="page-sub">${esc(t("compare.sub"))}</p></div>
      </div>
      <div class="compare-slots" id="c-slots"></div>
      <div class="row wrap gap-12" style="margin-top:20px">
        <button type="button" class="btn btn-primary btn-lg" id="c-go">${icons.compare}${esc(t("compare.go"))}</button>
        <button type="button" class="btn btn-ghost" id="c-add">${icons.plus}${esc(t("compare.addSlot"))}</button>
      </div>
      <div id="c-result" style="margin-top:32px" aria-live="polite"></div>
    </div>`;
  // بارکردنی زانیاریی مۆبایلە ڕیزکراوەکان
  await Promise.all(S.slots.map(async (s) => {
    if (!s.phoneId) return;
    s.phone = await api.phone(s.phoneId).catch(() => null);
    if (!s.phone) { Object.assign(s, emptySlot()); return; } // مۆبایلەکە ئیتر لە کاتالۆگدا نییە
    // تایبەتمەندییەکانی مۆبایلی ناو کاتالۆگ لە داتاکەوە دێن (قفڵن)
    s.variant = configIndex(s.phone, s.want?.ram_gb, s.want?.storage_gb);
    s.features = featuresOf(s.phone, s.variant);
  }));
  renderSlots();
  $("#c-add", el).addEventListener("click", () => { if (S.slots.length < 3) { S.slots.push(emptySlot()); renderSlots(); } });
  $("#c-go", el).addEventListener("click", () => run($("#c-go", el)));
  if (S.slots.filter(ready).length >= 2) run();
}

const emptySlot = () => ({ phone: null, variant: 0, features: null, name: "", phoneId: null, asked: "" });
const ready = (s) => !!s.features;

function renderSlots() {
  const box = $("#c-slots", S.el);
  $("#c-add", S.el).hidden = S.slots.length >= 3;
  box.innerHTML = S.slots.map((s, i) => `
    <div class="card stack gap-16" data-slot="${i}">
      <div class="row between gap-8">
        <span class="row gap-10"><span class="slot-num">${i + 1}</span><strong>${esc(t("compare.phone", { n: i + 1 }))}</strong></span>
        ${S.slots.length > 2 ? `<button type="button" class="icon-btn" data-remove="${i}" aria-label="${esc(t("common.remove"))}">${icons.x}</button>` : ""}
      </div>
      <div data-search></div>
      ${s.phone ? `
        <div class="field"><label for="c-var-${i}">${esc(t("predict.whichVariant"))}</label>
          <div class="select-wrap"><select class="select num" id="c-var-${i}" data-variant="${i}">
            ${s.phone.configs.map((c, j) => `<option value="${j}" ${j === s.variant ? "selected" : ""}>\u2066${c.ram_gb} GB · ${c.storage_gb >= 1024 ? `${c.storage_gb / 1024} TB` : `${c.storage_gb} GB`}${c.verified ? "" : " ≈"}\u2069</option>`).join("")}
          </select></div></div>` : s.features ? `<span class="badge badge-neutral" style="align-self:flex-start">${esc(t("compare.customSpecs"))}</span>` : ""}
      <div class="field"><label for="c-ask-${i}">${esc(t("compare.asked"))}</label>
        <div class="input-group"><input class="input input-num" id="c-ask-${i}" data-asked="${i}" type="number" min="0" inputmode="decimal" value="${esc(s.asked)}" placeholder="${esc(t("compare.optional"))}"><span class="unit">USD</span></div>
      </div>
    </div>`).join("");

  S.slots.forEach((s, i) => {
    const slotEl = box.querySelector(`[data-slot="${i}"]`);
    phoneSearch(slotEl.querySelector("[data-search]"), {
      value: s.name,
      placeholder: t("compare.searchPh"),
      onSelect: async (p) => {
        try {
          const phone = await api.phone(p.id);
          const idx = configIndex(phone);
          Object.assign(s, { phone, phoneId: phone.id, name: phone.name, variant: idx });
          s.features = featuresOf(phone, idx);
          renderSlots();
        } catch (e) { toast(errorMessage(e), "error"); }
      },
    });
  });
  box.querySelectorAll("[data-variant]").forEach((sel) => sel.addEventListener("change", () => {
    const s = S.slots[Number(sel.dataset.variant)];
    s.variant = Number(sel.value);
    s.features = featuresOf(s.phone, s.variant);
  }));
  box.querySelectorAll("[data-asked]").forEach((inp) => inp.addEventListener("input", () => { S.slots[Number(inp.dataset.asked)].asked = inp.value; }));
  box.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => { S.slots.splice(Number(b.dataset.remove), 1); renderSlots(); }));
}

// تەنها جۆرە ڕاستەقینەکانی مۆبایلەکە (RAM + بیرگە)؛ بنەڕەت: یەکەم جۆر کە نرخی بازاڕی هەیە
function configIndex(phone, ram, storage) {
  const cs = phone.configs || [];
  let i = ram || storage
    ? cs.findIndex((c) => String(c.ram_gb) === String(ram) && String(c.storage_gb) === String(storage)) : -1;
  if (i < 0) i = cs.findIndex((c) => c.price_usd);
  if (i < 0) i = cs.findIndex((c) => c.verified);
  return Math.max(0, i);
}

function featuresOf(phone, idx) {
  const c = phone.configs[idx];
  return { ...phone.specs, ram_gb: c.ram_gb, storage_gb: c.storage_gb };
}

async function run(btn) {
  const slots = S.slots.filter(ready);
  if (slots.length < 2) { toast(t("compare.needTwo"), "error"); return; }
  const items = slots.map((s) => ({
    features: s.features, phone_id: s.phoneId, phone_name: s.name,
    asked_price: parseFloat(s.asked) > 0 ? parseFloat(s.asked) : null,
  }));
  setBusy(btn, true);
  const out = $("#c-result", S.el);
  out.innerHTML = `<div class="card"><div class="skeleton" style="height:300px"></div></div>`;
  try {
    const res = await api.compare(items);
    if (!S) return;
    renderResult(res, slots);
  } catch (e) {
    out.innerHTML = `<div class="card">${emptyState({ icon: icons.alert, title: t("err.pageTitle"), body: errorMessage(e) })}</div>`;
  } finally { setBusy(btn, false); }
}

function fmt(name, v) {
  const f = S.schema.features.find((x) => x.name === name);
  if (v === null || v === undefined) return "—";
  if (f.kind === "binary") return Number(v) ? t("common.yes") : t("common.no");
  if (name === "chipset_tier") return (f.tiers?.[lang()] || [])[Number(v) - 1] || v;
  if (name === "storage_gb") return v >= 1024 ? `${v / 1024} TB` : `${v} GB`;
  if (name === "release_year") return String(v);
  if (f.kind === "numeric") return `${num(v, f.step < 1 ? 1 : 0)} ${f.unit || ""}`.trim();
  return v;
}

function renderResult(res, slots) {
  const items = res.items;
  const best = res.best_value_index;
  const cheapest = items.reduce((a, r, i) => (r.price < items[a].price ? i : a), 0);
  const winners = (name) => {
    const f = S.schema.features.find((x) => x.name === name);
    if (f.kind === "categorical") return new Set();
    const vals = items.map((r) => Number(r.features[name]));
    if (vals.some((v) => Number.isNaN(v)) || new Set(vals).size === 1) return new Set();
    const target = LOWER_IS_BETTER.has(name) ? Math.min(...vals) : Math.max(...vals);
    return new Set(vals.map((v, i) => (v === target ? i : -1)).filter((i) => i >= 0));
  };
  const col = (i) => `<th scope="col" style="min-width:180px">
      <div class="stack gap-6"><span class="num" style="color:var(--text);font-weight:700;font-size:15px">${esc(items[i].phone_name)}</span>
      ${best === i ? `<span class="badge badge-fair" style="align-self:flex-start">${icons.check}${esc(t("compare.bestValue"))}</span>` : ""}</div></th>`;

  $("#c-result", S.el).innerHTML = `
    <section class="card stack gap-20 fade-in" aria-labelledby="cmp-title">
      <div class="row wrap between gap-12">
        <h2 class="card-title" id="cmp-title">${esc(t("compare.resultTitle"))}</h2>
        <span class="card-sub">${esc(t("compare.legend"))}</span>
      </div>
      <div class="table-wrap">
        <table class="table cmp-table">
          <thead><tr><th scope="col">${esc(t("compare.spec"))}</th>${items.map((_, i) => col(i)).join("")}</tr></thead>
          <tbody>
            <tr><th scope="row">${esc(t("predict.estimated"))}</th>${items.map((r, i) => `<td class="num ${i === cheapest ? "win" : ""}" style="font-size:22px;font-weight:700">${esc(money(r.price))}</td>`).join("")}</tr>
            <tr><th scope="row">${esc(t("predict.rangeTitle"))}</th>${items.map((r) => `<td class="num muted">${esc(money(r.low))} – ${esc(money(r.high))}</td>`).join("")}</tr>
            <tr><th scope="row">${esc(t("compare.asked"))}</th>${items.map((r) => `<td>${r.verdict ? `<div class="stack gap-4"><span class="num">${esc(money(r.verdict.asked))}</span>${verdictBadge(r.verdict.status)}<span class="faint num" style="font-size:12.5px">${esc(pct(r.verdict.diff_pct, 0, true))}</span></div>` : '<span class="faint">—</span>'}</td>`).join("")}</tr>
            ${ROWS.map((name) => {
              const w = winners(name);
              return `<tr><th scope="row">${esc(featureLabel(name))}</th>${items.map((r, i) => `<td class="${w.has(i) ? "win" : ""}"><bdi>${esc(fmt(name, r.features[name]))}</bdi></td>`).join("")}</tr>`;
            }).join("")}
            <tr><th scope="row">${esc(t("compare.topFactors"))}</th>${items.map((r) => `<td><div class="stack gap-4" style="font-size:13px">${r.explanation.items.slice(0, 3).map((x) =>
              `<span><span style="color:var(--${x.phi >= 0 ? "blue" : "orange"}-text);font-weight:800;display:inline-block" class="num">${esc(money(x.usd, { sign: true }))}</span> ${esc(featureLabel(x.feature))}</span>`).join("")}</div></td>`).join("")}</tr>
            <tr class="no-print"><th scope="row"></th>${items.map((r, i) => {
              const s = slots[i];
              const link = s.phone ? href("predict", { phone: s.phone.id, ram: r.features.ram_gb, storage: r.features.storage_gb }) : href("predict", { f: JSON.stringify(r.features) });
              return `<td><a class="btn btn-soft btn-sm" href="${esc(link)}">${esc(t("compare.details"))}</a></td>`;
            }).join("")}</tr>
          </tbody>
        </table>
      </div>
      ${best === null ? `<p class="hint">${esc(t("compare.tipAsked"))}</p>` : ""}
    </section>`;
}
