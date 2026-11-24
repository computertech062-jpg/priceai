// گرافە سادەکان بە SVG (بەبێ کتێبخانەی دەرەکی، بۆ ئەوەی بەبێ ئینتەرنێتیش کار بکات)
import { esc, money, num } from "./ui.js";

const W = 640;

function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

function ticks(max, count = 4) {
  return Array.from({ length: count + 1 }, (_, i) => (max / count) * i);
}

/** گرافی ستوونی. data: [{label, value, title}] */
export function barChart(data, { height = 220, highlightLast = true, ariaLabel = "", format = (v) => num(v) } = {}) {
  const pad = { t: 12, r: 8, b: 28, l: 36 };
  const max = niceMax(Math.max(1, ...data.map((d) => d.value)));
  const iw = W - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const bw = iw / data.length;
  const every = Math.ceil(data.length / 7);
  const grid = ticks(max).map((v) => {
    const y = pad.t + ih - (v / max) * ih;
    return `<line class="grid-line" x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}"/>
      <text x="${pad.l - 8}" y="${y + 4}" text-anchor="end">${esc(format(v))}</text>`;
  }).join("");
  const bars = data.map((d, i) => {
    const h = Math.max(d.value > 0 ? 3 : 0, (d.value / max) * ih);
    const x = pad.l + i * bw + bw * 0.18;
    const y = pad.t + ih - h;
    const fill = highlightLast && i === data.length - 1 ? "var(--accent)" : "color-mix(in srgb, var(--accent) 38%, var(--surface-3))";
    const label = i % every === 0 || i === data.length - 1
      ? `<text x="${x + bw * 0.32}" y="${height - 8}" text-anchor="middle">${esc(d.label)}</text>` : "";
    return `<g><rect x="${x}" y="${y}" width="${bw * 0.64}" height="${h}" rx="5" style="fill:${fill}"><title>${esc(d.title || `${d.label}: ${format(d.value)}`)}</title></rect>${label}</g>`;
  }).join("");
  return `<div class="chart"><svg viewBox="0 0 ${W} ${height}" role="img" aria-label="${esc(ariaLabel)}">${grid}${bars}</svg></div>`;
}

/** نرخی ڕاستەقینە بەرامبەر پێشبینیکراو. points: [[actual, predicted]] */
export function scatterChart(points, { size = 420, ariaLabel = "", xLabel = "", yLabel = "" } = {}) {
  const pad = { t: 14, r: 14, b: 42, l: 54 };
  const max = niceMax(Math.max(1, ...points.flat()));
  const iw = size - pad.l - pad.r;
  const ih = size - pad.t - pad.b;
  const sx = (v) => pad.l + (v / max) * iw;
  const sy = (v) => pad.t + ih - (v / max) * ih;
  const grid = ticks(max).map((v) => `
    <line class="grid-line" x1="${pad.l}" x2="${size - pad.r}" y1="${sy(v)}" y2="${sy(v)}"/>
    <text x="${pad.l - 8}" y="${sy(v) + 4}" text-anchor="end">${esc(money(v))}</text>
    <text x="${sx(v)}" y="${size - pad.b + 18}" text-anchor="middle">${esc(money(v))}</text>`).join("");
  const dots = points.map(([a, p]) =>
    `<circle cx="${sx(a)}" cy="${sy(p)}" r="4" style="fill:var(--accent);fill-opacity:.55"><title>${esc(`${money(a)} → ${money(p)}`)}</title></circle>`).join("");
  return `<div class="chart"><svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(ariaLabel)}">
    ${grid}
    <line x1="${sx(0)}" y1="${sy(0)}" x2="${sx(max)}" y2="${sy(max)}" style="stroke:var(--mint);stroke-width:2;stroke-dasharray:6 6"/>
    ${dots}
    <text x="${pad.l + iw / 2}" y="${size - 4}" text-anchor="middle" style="font-size:12px">${esc(xLabel)}</text>
    <text x="14" y="${pad.t + ih / 2}" text-anchor="middle" transform="rotate(-90 14 ${pad.t + ih / 2})" style="font-size:12px">${esc(yLabel)}</text>
  </svg></div>`;
}

/** هیستۆگرامی هەڵەکان */
export function histogramChart(counts, edges, { height = 240, ariaLabel = "" } = {}) {
  const pad = { t: 12, r: 8, b: 30, l: 36 };
  const max = niceMax(Math.max(1, ...counts));
  const iw = W - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const bw = iw / counts.length;
  const grid = ticks(max).map((v) => {
    const y = pad.t + ih - (v / max) * ih;
    return `<line class="grid-line" x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}"/><text x="${pad.l - 8}" y="${y + 4}" text-anchor="end">${num(v)}</text>`;
  }).join("");
  const bars = counts.map((c, i) => {
    const h = (c / max) * ih;
    const mid = (edges[i] + edges[i + 1]) / 2;
    const fill = Math.abs(mid) < (edges[1] - edges[0]) ? "var(--mint)" : "var(--accent)";
    return `<rect x="${pad.l + i * bw + 1}" y="${pad.t + ih - h}" width="${bw - 2}" height="${h}" rx="3" style="fill:${fill};fill-opacity:.8"><title>${esc(`${money(edges[i])} … ${money(edges[i + 1])}: ${c}`)}</title></rect>`;
  }).join("");
  const labels = [0, Math.floor(counts.length / 2), counts.length].map((i) =>
    `<text x="${pad.l + i * bw}" y="${height - 8}" text-anchor="middle">${esc(money(edges[i]))}</text>`).join("");
  return `<div class="chart"><svg viewBox="0 0 ${W} ${height}" role="img" aria-label="${esc(ariaLabel)}">${grid}${bars}${labels}</svg></div>`;
}

/** گرافی هێڵی */
export function lineChart(data, { height = 200, ariaLabel = "", format = money } = {}) {
  if (!data.length) return "";
  const pad = { t: 14, r: 12, b: 26, l: 52 };
  const vals = data.map((d) => d.value);
  const max = niceMax(Math.max(...vals));
  const iw = W - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const sx = (i) => pad.l + (data.length === 1 ? iw / 2 : (i / (data.length - 1)) * iw);
  const sy = (v) => pad.t + ih - (v / max) * ih;
  const path = data.map((d, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(d.value).toFixed(1)}`).join(" ");
  const area = `${path} L${sx(data.length - 1)},${pad.t + ih} L${sx(0)},${pad.t + ih} Z`;
  const grid = ticks(max).map((v) => `<line class="grid-line" x1="${pad.l}" x2="${W - pad.r}" y1="${sy(v)}" y2="${sy(v)}"/><text x="${pad.l - 8}" y="${sy(v) + 4}" text-anchor="end">${esc(format(v))}</text>`).join("");
  const dots = data.map((d, i) => `<circle cx="${sx(i)}" cy="${sy(d.value)}" r="4" style="fill:var(--surface);stroke:var(--accent);stroke-width:2.5"><title>${esc(`${d.label}: ${format(d.value)}`)}</title></circle>`).join("");
  return `<div class="chart"><svg viewBox="0 0 ${W} ${height}" role="img" aria-label="${esc(ariaLabel)}">
    ${grid}<path d="${area}" style="fill:var(--accent);fill-opacity:.12"/>
    <path d="${path}" style="fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round"/>${dots}</svg></div>`;
}

/** بازنەی (donut) */
export function donutChart(segments, { size = 160, ariaLabel = "", center = "" } = {}) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const r = 58;
  const c = 2 * Math.PI * r;
  let offset = 0;
  const arcs = total === 0
    ? `<circle cx="80" cy="80" r="${r}" style="fill:none;stroke:var(--track);stroke-width:20"/>`
    : segments.map((s) => {
      const len = (s.value / total) * c;
      const el = `<circle cx="80" cy="80" r="${r}" transform="rotate(-90 80 80)" style="fill:none;stroke:${s.color};stroke-width:20;stroke-dasharray:${len} ${c - len};stroke-dashoffset:${-offset}"><title>${esc(`${s.label}: ${s.value}`)}</title></circle>`;
      offset += len;
      return el;
    }).join("");
  return `<div class="chart" style="width:${size}px;flex:none"><svg viewBox="0 0 160 160" role="img" aria-label="${esc(ariaLabel)}">${arcs}
    <text x="80" y="88" text-anchor="middle" style="font-size:26px;font-weight:700;fill:var(--text)">${esc(center)}</text></svg></div>`;
}

/** ستوونی ئاسۆیی بە HTML */
export function hbars(items, { color = "var(--accent)" } = {}) {
  const max = Math.max(1e-9, ...items.map((i) => i.value));
  return items.map((i) => `
    <div class="hbar">
      <div class="hbar-top"><span>${esc(i.label)}</span><span class="faint num">${esc(i.display ?? num(i.value))}</span></div>
      <div class="hbar-track"><div class="hbar-fill" style="width:${((i.value / max) * 100).toFixed(1)}%;background:${color}"></div></div>
    </div>`).join("");
}

/**
 * گرافی نرخ بە پێی کات (تەوەرەی X ڕێکەوتی ڕاستەقینەیە، نەک ژمارەی خاڵ).
 * points: [{date: "2023-09-28", value, title}]  ·  marks: [{date, label}] هێڵی ستوونی (بۆ نموونە دەرچوون)
 */
export function timeChart(points, { height = 230, ariaLabel = "", format = money, marks = [], forecast = [], model = [] } = {}) {
  // model: [{date, value, title}] نرخی مۆدێلی سەرەکیی AI (هێڵی خاڵخاڵی شین).
  // forecast: [{date, value, low, high, title}] هێڵی پچڕپچڕ + مەودا. یەکەم خاڵی دەبێت دوایین نرخی ڕاستەقینە بێت.
  if (!points.length && !forecast.length) return "";
  const pad = { t: 16, r: 16, b: 28, l: 56 };
  const ms = (d) => new Date(`${d}T00:00:00Z`).getTime();
  const xs = [...points.map((p) => ms(p.date)), ...forecast.map((p) => ms(p.date)), ...model.map((p) => ms(p.date)), ...marks.map((m) => ms(m.date))];
  let x0 = Math.min(...xs);
  let x1 = Math.max(...xs);
  if (x1 - x0 < 864e5 * 60) { x0 -= 864e5 * 45; x1 += 864e5 * 45; }
  const max = niceMax(Math.max(...points.map((p) => p.value), ...forecast.map((p) => p.high ?? p.value), ...model.map((p) => p.value)) * 1.08);
  const iw = W - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const sx = (d) => pad.l + ((ms(d) - x0) / (x1 - x0)) * iw;
  const sy = (v) => pad.t + ih - (v / max) * ih;
  const grid = ticks(max).map((v) => `<line class="grid-line" x1="${pad.l}" x2="${W - pad.r}" y1="${sy(v)}" y2="${sy(v)}"/><text x="${pad.l - 8}" y="${sy(v) + 4}" text-anchor="end">${esc(format(v))}</text>`).join("");
  const years = [];
  for (let y = new Date(x0).getUTCFullYear() + 1; y <= new Date(x1).getUTCFullYear(); y++) years.push(y);
  const yearTicks = years.map((y) => {
    const x = sx(`${y}-01-01`);
    return `<line class="grid-line" x1="${x}" x2="${x}" y1="${pad.t}" y2="${pad.t + ih}" style="stroke-dasharray:2 4"/><text x="${x}" y="${height - 8}" text-anchor="middle">${y}</text>`;
  }).join("");
  const markEls = marks.map((m) => {
    const x = sx(m.date);
    return `<line x1="${x}" x2="${x}" y1="${pad.t}" y2="${pad.t + ih}" style="stroke:var(--mint);stroke-width:1.5;stroke-dasharray:5 4"/>
      <text x="${x + 5}" y="${pad.t + 11}" style="fill:var(--mint);font-size:11px">${esc(m.label)}</text>`;
  }).join("");
  const line = (arr, key = "value") => arr.map((p, i) => `${i ? "L" : "M"}${sx(p.date).toFixed(1)},${sy(p[key] ?? p.value).toFixed(1)}`).join(" ");
  let real = "";
  if (points.length) {
    const path = line(points);
    const area = `${path} L${sx(points[points.length - 1].date).toFixed(1)},${pad.t + ih} L${sx(points[0].date).toFixed(1)},${pad.t + ih} Z`;
    real = `<path d="${area}" style="fill:var(--accent);fill-opacity:.12"/>
      <path d="${path}" style="fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round"/>`;
  }
  let fc = "";
  if (forecast.length) {
    const band = `${line(forecast, "high")} ${[...forecast].reverse().map((p) => `L${sx(p.date).toFixed(1)},${sy(p.low ?? p.value).toFixed(1)}`).join(" ")} Z`;
    fc = `<path d="${band}" style="fill:var(--mint);fill-opacity:.14"/>
      <path d="${line(forecast)}" style="fill:none;stroke:var(--mint);stroke-width:2.5;stroke-dasharray:7 5"/>`
      + forecast.slice(1).map((p) => `<circle cx="${sx(p.date)}" cy="${sy(p.value)}" r="5" style="fill:var(--surface);stroke:var(--mint);stroke-width:2.5"><title>${esc(p.title || `${p.date}: ${format(p.value)}`)}</title></circle>`).join("");
  }
  const mdl = model.length
    ? `<path d="${line(model)}" style="fill:none;stroke:var(--blue);stroke-width:2;stroke-dasharray:2 5;stroke-linecap:round"/>`
      + model.map((p) => `<circle cx="${sx(p.date)}" cy="${sy(p.value)}" r="5" style="fill:var(--blue);stroke:var(--surface);stroke-width:2"><title>${esc(p.title || `${p.date}: ${format(p.value)}`)}</title></circle>`).join("")
    : "";
  const dots = [...points, ...(forecast.length ? [forecast[0]] : [])].map((p) => `<circle cx="${sx(p.date)}" cy="${sy(p.value)}" r="4.5" style="fill:var(--surface);stroke:var(--accent);stroke-width:2.5"><title>${esc(p.title || `${p.date}: ${format(p.value)}`)}</title></circle>`).join("");
  return `<div class="chart" dir="ltr"><svg viewBox="0 0 ${W} ${height}" role="img" aria-label="${esc(ariaLabel)}">
    ${grid}${yearTicks}${markEls}${real}${fc}${mdl}${dots}</svg></div>`;
}
