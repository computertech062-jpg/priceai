// ئایکۆنەکان (SVG ی هێڵی). هەموویان currentColor بەکاردەهێنن.
const p = (d, extra = "") =>
  `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</svg>`;

export const icons = {
  // لۆگۆی PriceAI: مۆبایل + ئەستێرەی AI + نیشانەی نرخ (هەمان frontend/favicon.svg)
  logo: `<svg aria-hidden="true" viewBox="0 0 64 64" width="100%" height="100%">
    <defs><linearGradient id="pai-logo-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#BDB2FF"/><stop offset="1" stop-color="#7F8FFF"/></linearGradient></defs>
    <rect width="64" height="64" rx="16" fill="url(#pai-logo-g)"/>
    <rect x="13" y="8" width="27" height="44" rx="8" fill="none" stroke="#0B0E19" stroke-width="4.5"/>
    <path d="M26.5 15.5c.8 4.9 2.6 6.7 7.5 7.5-4.9.8-6.7 2.6-7.5 7.5-.8-4.9-2.6-6.7-7.5-7.5 4.9-.8 6.7-2.6 7.5-7.5z" fill="#0B0E19"/>
    <g transform="translate(45 45) rotate(-45)"><path d="M-6 -8.5H9a3 3 0 0 1 3 3V5.5a3 3 0 0 1-3 3H-6L-14.5 0Z" fill="#0B0E19" stroke="url(#pai-logo-g)" stroke-width="5" stroke-linejoin="round" paint-order="stroke"/>
    <circle cx="-5.5" cy="0" r="2.5" fill="url(#pai-logo-g)"/></g></svg>`,
  phone: p('<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4"/>'),
  search: p('<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>'),
  sparkle: p('<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8z"/>'),
  home: p('<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>'),
  compare: p('<rect x="3" y="4" width="7" height="16" rx="2"/><rect x="14" y="4" width="7" height="16" rx="2"/>'),
  history: p('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  chart: p('<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>'),
  grid: p('<rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/>'),
  users: p('<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M19 8v6"/><path d="M16 11h6"/>'),
  user: p('<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'),
  moon: p('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
  sun: p('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  logout: p('<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/>'),
  check: p('<path d="M5 12l5 5 9-10"/>', 'stroke-width="2.4"'),
  x: p('<path d="M6 6l12 12M18 6L6 18"/>'),
  share: p('<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4"/><path d="M15.4 6.5l-6.8 4"/>'),
  download: p('<path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M5 21h14"/>'),
  trash: p('<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/>'),
  plus: p('<path d="M12 5v14M5 12h14"/>'),
  info: p('<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>'),
  alert: p('<path d="M12 3l10 18H2z"/><path d="M12 10v4"/><path d="M12 17h.01"/>'),
  scale: p('<path d="M12 3v18"/><path d="M5 7h14"/><path d="M5 7l-3 7a4 4 0 0 0 6 0z"/><path d="M19 7l-3 7a4 4 0 0 0 6 0z"/>'),
  sliders: p('<path d="M4 6h10"/><path d="M18 6h2"/><circle cx="16" cy="6" r="2"/><path d="M4 12h4"/><path d="M12 12h8"/><circle cx="10" cy="12" r="2"/><path d="M4 18h12"/><circle cx="18" cy="18" r="2"/>'),
  layers: p('<circle cx="9" cy="9" r="5"/><circle cx="15" cy="15" r="5"/>'),
  wand: p('<path d="M15 4V2M15 10V8M11 6h2M17 6h2"/><path d="M3 21l11-11"/><path d="M13 7l4 4"/>'),
  eye: p('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
  eyeOff: p('<path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.8 9.8 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>'),
  chevron: p('<path d="M6 9l6 6 6-6"/>', 'class="chev"'),
  arrow: p('<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>'),
  menu: p('<path d="M4 7h16M4 12h16M4 17h16"/>'),
  target: p('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>'),
  database: p('<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>'),
  shield: p('<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>'),
  copy: p('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>'),
  refresh: p('<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>'),
};
