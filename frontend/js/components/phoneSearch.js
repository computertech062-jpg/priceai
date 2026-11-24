// گەڕان بە ناوی مۆبایل لەگەڵ پێشنیاری خۆکار (Autocomplete / Combobox)
import { api } from "../api.js";
import { icons } from "../icons.js";
import { t } from "../i18n.js";
import { debounce, esc } from "../ui.js";

let uid = 0;

function highlight(name, q) {
  const safe = esc(name);
  const words = q.trim().split(/\s+/).filter((w) => w.length > 0).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return safe;
  try {
    return safe.replace(new RegExp(`(${words.join("|")})`, "gi"), "<mark>$1</mark>");
  } catch { return safe; }
}

function variantsLabel(p) {
  const st = [...new Set((p.configs || p.variants).map((v) => v.storage_gb))].map((s) => (s >= 1024 ? `${s / 1024}TB` : `${s}GB`));
  return [p.release_year, st.join(" / ")].filter(Boolean).join(" · ");
}

/**
 * @param {HTMLElement} root
 * @param {{placeholder?:string, value?:string, onSelect:(phone)=>void, onManual?:()=>void, submitLabel?:string, onSubmitText?:(q)=>void, size?:'lg'|'md'}} opts
 */
export function phoneSearch(root, opts) {
  const id = `ps-${++uid}`;
  root.classList.add("search");
  root.innerHTML = `
    <label class="sr-only" for="${id}">${esc(t("search.label"))}</label>
    <div class="search-box">
      ${icons.search}
      <input id="${id}" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false"
        aria-controls="${id}-list" autocomplete="off" spellcheck="false" dir="auto"
        placeholder="${esc(opts.placeholder || t("search.placeholder"))}" value="${esc(opts.value || "")}">
      ${opts.submitLabel ? `<button type="button" class="btn btn-primary">${esc(opts.submitLabel)}</button>` : ""}
    </div>
    <ul class="search-list" id="${id}-list" role="listbox" hidden></ul>`;
  const input = root.querySelector("input");
  const list = root.querySelector("ul");
  const submit = root.querySelector(".search-box .btn");
  let results = [];
  let active = -1;
  let ctrl = null;
  let lastQ = "";

  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; input.removeAttribute("aria-activedescendant"); };
  const open = () => { list.hidden = false; input.setAttribute("aria-expanded", "true"); };

  function paint(q) {
    if (!results.length) {
      list.innerHTML = `<li class="search-empty" role="option" aria-disabled="true" aria-selected="false">
          <strong>${esc(t("search.noResults"))}</strong>
          <span class="faint" style="font-size:13px">${esc(t("search.noResultsHint"))}</span>
          ${opts.onManual ? `<button type="button" class="btn btn-soft btn-sm" data-manual style="align-self:flex-start">${icons.sliders}${esc(t("search.manual"))}</button>` : ""}
        </li>`;
      open();
      return;
    }
    list.innerHTML = results.map((p, i) => `
      <li role="option" id="${id}-o${i}" data-i="${i}" aria-selected="${i === active}">
        <span class="row gap-12" style="min-width:0">
          <span class="phone-ico">${icons.phone}</span>
          <span class="stack" style="min-width:0"><span class="s-name">${highlight(p.name, q)}</span><span class="s-meta">${esc(variantsLabel(p))}</span></span>
        </span>
        <span class="faint" style="font-size:12.5px">${esc(p.chipset || "")}</span>
      </li>`).join("");
    open();
  }

  const doSearch = debounce(async (q) => {
    if (ctrl) ctrl.abort();
    if (q.trim().length < 1) { results = []; close(); return; }
    ctrl = new AbortController();
    try {
      const data = await api.search(q, ctrl.signal);
      if (q !== input.value) return;
      results = data.results || [];
      active = results.length ? 0 : -1;
      paint(q);
    } catch (e) {
      if (e.name !== "AbortError") close();
    }
  }, 180);

  function choose(i) {
    const p = results[i];
    if (!p) return;
    input.value = p.name;
    lastQ = p.name;
    close();
    opts.onSelect?.(p);
  }

  input.addEventListener("input", () => { lastQ = input.value; doSearch(input.value); });
  input.addEventListener("focus", () => { if (input.value && results.length && lastQ === input.value) paint(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!results.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + results.length) % results.length;
      paint(input.value);
      input.setAttribute("aria-activedescendant", `${id}-o${active}`);
      list.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (!list.hidden && active >= 0) choose(active);
      else if (opts.onSubmitText) opts.onSubmitText(input.value);
    } else if (e.key === "Escape") {
      close();
    }
  });
  list.addEventListener("mousedown", (e) => e.preventDefault());
  list.addEventListener("click", (e) => {
    if (e.target.closest("[data-manual]")) { close(); opts.onManual?.(); return; }
    const li = e.target.closest("[data-i]");
    if (li) choose(Number(li.dataset.i));
  });
  input.addEventListener("blur", () => setTimeout(close, 120));
  submit?.addEventListener("click", () => {
    if (results.length && !list.hidden && active >= 0) choose(active);
    else if (opts.onSubmitText) opts.onSubmitText(input.value);
    else input.focus();
  });

  return {
    input,
    setValue(v) { input.value = v; lastQ = v; },
    focus() { input.focus(); },
    async searchFirst(q) {
      const data = await api.search(q);
      return (data.results || [])[0] || null;
    },
  };
}
