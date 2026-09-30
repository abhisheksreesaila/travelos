/* ═══════════════════════════════════════════════════════════════════════════
   TravelOS Icon Library — Flat SVG Icons (Omarchy-inspired)
   All icons are inline SVGs. No external dependencies. No icon fonts.
   Each function returns an SVG string. Accepts size and className.
   ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Generate an SVG icon element.
 * @param {string} name - Icon identifier
 * @param {object} [opts]
 * @param {number} [opts.size=20] - Width/height in px
 * @param {string} [opts.className=''] - Additional CSS classes
 * @param {string} [opts.strokeWidth='1.8'] - Stroke width
 * @returns {string} SVG markup
 */
export function icon(name, { size = 20, className = '', strokeWidth = '1.8' } = {}) {
  const paths = ICONS[name];
  if (!paths) return '';
  const w = size;
  const cls = className ? ` class="${className}"` : '';
  return `<svg${cls} width="${w}" height="${w}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
}

/**
 * Render multiple icons as a combined string.
 * @param {Array<{name: string, opts?: object}>} icons
 * @returns {string}
 */
export function icons(list) {
  return list.map(({ name, ...opts }) => icon(name, opts)).join('');
}

/* ── Navigation & UI ─────────────────────────────────────────────────── */
const ICONS = {
  /* ── Core navigation ────────────────────────────────────────────── */
  plane: `<path d="M3 14.5 21 12 3 9.5l5-2.5 1.5-4L12 8l6.5-1.5L21 8l-5 3 5 3-2.5 1.5L12 14l-2.5 5L8 15Z"/>`,
  planeTakeoff: `<path d="M3 20h18M4.5 17.5 3 10l2-1 5 3.5L16 3l3 2-1 10-9.5 2.5-4-1Z"/>`,
  planeLanding: `<path d="M3 20h18M19.5 17.5 21 10l-2-1-5 3.5L8 3 5 5l1 10 9.5 2.5 4-1Z"/>`,
  search: `<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/><path d="M11 8v6M8 11h6"/>`,
  arrowRight: `<path d="M5 12h14M12 5l7 7-7 7"/>`,
  arrowLeft: `<path d="M19 12H5M12 19l-7-7 7-7"/>`,
  arrowUp: `<path d="M12 19V5M5 12l7-7 7 7"/>`,
  arrowDown: `<path d="M12 5v14M19 12l-7 7-7-7"/>`,
  chevronRight: `<path d="m9 18 6-6-6-6"/>`,
  chevronLeft: `<path d="m15 18-6-6 6-6"/>`,
  chevronDown: `<path d="m6 9 6 6 6-6"/>`,
  chevronUp: `<path d="m18 15-6-6-6 6"/>`,
  menu: `<path d="M4 6h16M4 12h16M4 18h16"/>`,
  close: `<path d="M18 6 6 18M6 6l12 12"/>`,
  plus: `<path d="M12 5v14M5 12h14"/>`,
  minus: `<path d="M5 12h14"/>`,
  moreHorizontal: `<circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/><circle cx="5" cy="12" r="1.5"/>`,
  moreVertical: `<circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>`,
  check: `<path d="M20 6 9 17l-5-5"/>`,
  checkCircle: `<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>`,
  xCircle: `<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>`,
  info: `<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>`,
  alert: `<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>`,
  help: `<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 1 1 5.83 1c0 2-3 3-3 3M12 17h.01"/>`,
  settings: `<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z"/><circle cx="12" cy="12" r="3"/>`,
  command: `<path d="M18 3a3 3 0 0 0-3 3v3H9V6a3 3 0 1 0-3 3h3v6H6a3 3 0 1 0 3 3v-3h6v3a3 3 0 1 0 3-3h-3V9h3a3 3 0 0 0 0-6Zm-3 6V6a3 3 0 0 0 3 3h-3ZM6 9a3 3 0 0 0 3-3v3H6Zm3 6H6a3 3 0 0 0 3 3v-3Zm6 0v3a3 3 0 0 0 3-3h-3Z"/>`,
  copy: `<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>`,
  externalLink: `<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3"/>`,

  /* ── Travel & location ──────────────────────────────────────────── */
  pin: `<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>`,
  pinOff: `<path d="M12 17v5M9 10.3a8 8 0 0 1 4.7-6.7M15 6a8 8 0 0 1 4.3 14.3M4.22 4.22 19.78 19.78"/>`,
  map: `<path d="m9 18-6 3V6l6-3 6 3 6-3v15l-6 3-6-3Z"/><path d="M9 3v15M15 6v15"/>`,
  mapPin: `<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>`,
  compass: `<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>`,
  globe: `<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10M12 2a15.3 15.3 0 0 0-4 10 15.3 15.3 0 0 0 4 10"/>`,
  route: `<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/>`,
  navigation: `<polygon points="3 11 22 2 13 21 11 13 3 11"/>`,

  /* ── Calendar & time ────────────────────────────────────────────── */
  calendar: `<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>`,
  clock: `<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>`,
  alarmClock: `<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M5 3 2 6M22 6l-3-3M6.38 18.7 4 21M17.64 18.67 20 21"/>`,
  sunrise: `<path d="M12 2v8M4.93 10.93l1.41 1.41M2 18h2M20 18h2M19.07 10.93l-1.41 1.41M22 22H2M8 6l4-4 4 4M16 18a4 4 0 0 0-8 0"/>`,
  sunset: `<path d="M12 10V2M4.93 10.93l1.41 1.41M2 18h2M20 18h2M19.07 10.93l-1.41 1.41M22 22H2M16 6l-4-4-4 4M16 18a4 4 0 0 0-8 0"/>`,
  moon: `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"/>`,

  /* ── Weather ────────────────────────────────────────────────────── */
  cloud: `<path d="M17.5 19H7a5 5 0 1 1 .8-9.9A6 6 0 0 1 19.5 11 4 4 0 0 1 17.5 19Z"/>`,
  cloudSun: `<path d="M12 2v2M12 8v2M4.93 10.93l1.41 1.41M20 12h2M2 12h2M19.07 10.93l-1.41 1.41"/><path d="M17.5 19H7a5 5 0 1 1 .8-9.9A6 6 0 0 1 19.5 11 4 4 0 0 1 17.5 19Z"/>`,
  cloudRain: `<path d="M4 14.9A7 7 0 1 1 15.7 10h1.4a4.5 4.5 0 1 1 0 9"/><path d="M16 14v6M8 14v6M12 16v6"/>`,
  umbrella: `<path d="M22 12a10.1 10.1 0 0 0-20 0Z"/><path d="M12 12v8a2 2 0 0 0 4 0"/>`,
  thermometer: `<path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>`,
  wind: `<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2M9.6 4.6A2 2 0 1 1 11 8H2M12.6 19.4A2 2 0 1 0 14 16H2"/>`,

  /* ── People & social ────────────────────────────────────────────── */
  user: `<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>`,
  users: `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><circle cx="16" cy="3" r="2.8"/>`,
  userPlus: `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>`,
  userCheck: `<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/>`,
  heart: `<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.9-8.6a5.5 5.5 0 0 0-.1-7.8Z"/>`,
  star: `<polygon points="12 2 15.1 8.3 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 8.9 8.3 12 2"/>`,
  thumbsUp: `<path d="M7 11v8a1 1 0 0 1-1 1H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3a4 4 0 0 0 4-4V4a2 2 0 0 1 4 0v5h3a2 2 0 0 1 2 2l-1 5a2 3 0 0 1-2 2h-7a3 3 0 0 1-3-3"/>`,
  messageCircle: `<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>`,

  /* ── Share & collaboration ──────────────────────────────────────── */
  share: `<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 10.6 6.8-4.2M8.6 13.4l6.8 4.2"/>`,
  share2: `<path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M16 6l-4-4-4 4M12 2v13"/>`,
  link: `<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7.5l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7.5l1.5-1.5"/>`,
  link2: `<path d="M9 17H7A5 5 0 0 1 7 7h2M15 7h2a5 5 0 1 1 0 10h-2M8 12h8"/>`,
  mail: `<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.6 5.8a2.1 2.1 0 0 1-2.8 0L2 7"/>`,
  mailPlus: `<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.6 5.8a2.1 2.1 0 0 1-2.8 0L2 7M12 14v4M10 16h4"/>`,
  send: `<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>`,
  atSign: `<circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"/>`,
  bell: `<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.9 1.9 0 0 0 3.4 0"/>`,
  bellOff: `<path d="M8.7 3A6 6 0 0 1 18 8a21.3 21.3 0 0 0 .6 5M17 17H3s3-2 3-9a4.7 4.7 0 0 1 .3-1.7M10.3 21a1.9 1.9 0 0 0 3.4 0M2 2l20 20"/>`,

  /* ── Media & files ──────────────────────────────────────────────── */
  image: `<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>`,
  camera: `<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3"/>`,
  video: `<rect x="2" y="4" width="16" height="16" rx="2"/><polygon points="22 7 18 10.5 22 14 22 7"/>`,
  play: `<polygon points="5 3 19 12 5 21 5 3"/>`,
  pause: `<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>`,
  file: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/>`,
  fileText: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>`,
  download: `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>`,
  upload: `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>`,
  printer: `<polyline points="6 9 6 2 18 2 18 9"/><path d="M6 12H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h2M18 12h2a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>`,

  /* ── Finance & booking ──────────────────────────────────────────── */
  receipt: `<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1-2-1Z"/><path d="M8 7h8M8 11h8M8 15h5"/>`,
  creditCard: `<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>`,
  wallet: `<path d="M21 12V7H5a2 2 0 1 0 0 4h14v2"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h2v-4Z"/>`,
  dollar: `<path d="M12 2v20M17 5H9.5a3.5 3.5 0 1 0 0 7h5a3.5 3.5 0 1 1 0 7H6"/>`,
  tag: `<path d="M12 2H2v10l9.2 9.2a2 2 0 0 0 2.8 0l7.2-7.2a2 2 0 0 0 0-2.8L12 2Z"/><path d="M7 7h.01"/>`,
  percent: `<path d="M19 5 5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>`,
  trendingUp: `<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>`,
  trendingDown: `<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>`,

  /* ── Trip features ──────────────────────────────────────────────── */
  spark: `<path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/>`,
  sparkles: `<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>`,
  zap: `<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>`,
  lightbulb: `<path d="M9 18h6M10 22h4M15.1 8.7a4 4 0 1 0-6.2 0c-.6.9-1.3 2-1.3 3.3a4.4 4.4 0 0 0 8.8 0c0-1.3-.7-2.4-1.3-3.3Z"/>`,
  coffee: `<path d="M17 8h1a4 4 0 1 1 0 8h-1M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"/><path d="M6 2v2M10 2v2M14 2v2"/>`,
  utencil: `<path d="M3 2v7a4 4 0 0 0 4 4 4 4 0 0 0 4-4V2M9 2v7a3 3 0 0 0 3 3"/><path d="M18 9V2h-3v10a4 4 0 1 0 8 0 4 4 0 0 0-5-3Z"/>`,
  bed: `<path d="M2 4v16M2 8h20M16 4v4M8 4v4M2 16h20M18 16v4M6 16v4"/>`,
  bike: `<circle cx="18.5" cy="17.5" r="3.5"/><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="15" cy="5" r="1"/><path d="M12 17.5V14l-3-3 1.7-5.3h4.6L17 10"/>`,
  foot: `<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1Z"/><path d="M4 15v7"/>`,
  suitcase: `<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 4V2h6v2M4 10h16"/>`,

  /* ── Kids & fun ─────────────────────────────────────────────────── */
  smile: `<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/>`,
  party: `<path d="M18.5 8c-1.9 0-3.5 1.6-3.5 3.5 0 1.9 1.6 3.5 3.5 3.5s3.5-1.6 3.5-3.5-1.6-3.5-3.5-3.5Z"/><path d="M5.5 18c-1.9 0-3.5 1.6-3.5 3.5 0 1.9 1.6 3.5 3.5 3.5s3.5-1.6 3.5-3.5-1.6-3.5-3.5-3.5Z"/><path d="M15 2c-1.7 0-3 1.3-3 3s1.3 3 3 3 3-1.3 3-3-1.3-3-3-3Z"/><path d="m6.5 20.5 12-12M10.5 5.5l2.3 3.7M17 11.5l3.7 2.3M6.5 14.5l2.3-3.7"/>`,
  gift: `<polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5"/><path d="M12 22V7M12 7H7.5a2.5 2.5 0 1 1 0-5C11 2 12 7 12 7ZM12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7Z"/>`,
  palette: `<circle cx="13.5" cy="6.5" r="1.5"/><circle cx="17.5" cy="10.5" r="1.5"/><circle cx="8.5" cy="7.5" r="1.5"/><circle cx="6.5" cy="12.5" r="1.5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.9 0 1.5-.6 1.5-1.5 0-.4-.1-.7-.3-1-.2-.2-.2-.5 0-.7l.3-.3c.5-.4.8-1 .8-1.7 0-1.4-1.1-2.5-2.5-2.5H12c-4.4 0-8-3.6-8-8s3.6-8.3 8-8.3V2Z"/>`,
  music: `<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>`,
  gamepad: `<path d="M6 12h4M8 10v4M15 13h.01M18 11h.01"/><rect x="2" y="6" width="20" height="12" rx="2"/>`,
  ticket: `<path d="M2 9a3 3 0 1 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 1 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M9 12h.01M15 12h.01"/>`,

  /* ── Platform/brands ────────────────────────────────────────────── */
  youtube: `<path d="M2.5 17.1c-.3-1.1-.3-3.3-.3-5.1s0-4 .3-5.1A3 3 0 0 1 4.7 4.7C5.8 4.4 12 4.4 12 4.4s6.2 0 7.3.3a3 3 0 0 1 2.2 2.2c.3 1.1.3 3.3.3 5.1s0 4-.3 5.1a3 3 0 0 1-2.2 2.2c-1.1.3-7.3.3-7.3.3s-6.2 0-7.3-.3a3 3 0 0 1-2.2-2.2Z"/><polygon points="9.75 8.97 9.75 15.03 16.5 12 9.75 8.97"/>`,
  instagram: `<rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5"/>`,
  facebook: `<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3.6l.4-4h-4V7a1 1 0 0 1 1-1h3Z"/>`,
  whatsapp: `<path d="m3 21 1.7-5.7a9 9 0 1 1 4.5 4l-5.7 1.7Z"/><path d="M8.5 8.5a.5.5 0 0 1 .8-.1l1.2 1.5a.5.5 0 0 1-.1.7l-.9.6a5.8 5.8 0 0 0 3.3 3.3l.6-.9a.5.5 0 0 1 .7-.1l1.5 1.2a.5.5 0 0 1-.1.8 3.5 3.5 0 0 1-4.3-.3 3.5 3.5 0 0 1-.3-4.3Z"/>`,
  twitter: `<path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-4 1.6-1.2 3.7-1 5-1Z"/><path d="M16 4h6v6"/>`,
  github: `<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5a4.6 4.6 0 0 0-1.3-3.2 4.2 4.2 0 0 0-.1-3.2s-1.1-.3-3.5 1.3a12.3 12.3 0 0 0-6.2 0C6.5 2.2 5.4 2.5 5.4 2.5a4.2 4.2 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 8.9c0 3.5 3 5.5 6 5.5-.4.5-.7 1.2-.8 2 0 0-1.4 0-2.7-1.2a3.2 3.2 0 0 0-3.3-1.3s-2 .1-.1 1.2c1.2.8 1.8 2.2 3 2.8 1 .5 2 .3 3-.2 0 1.1.2 2.7 0 4"/>`,

  /* ── Workspace / terminal ───────────────────────────────────────── */
  terminal: `<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>`,
  monitor: `<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>`,
  layout: `<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>`,
  layoutGrid: `<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>`,
  columns: `<rect x="3" y="3" width="7" height="18" rx="1"/><rect x="14" y="3" width="7" height="18" rx="1"/>`,
  sidebar: `<rect x="3" y="3" width="6" height="18" rx="1"/><rect x="13" y="3" width="8" height="18" rx="1"/>`,
  panelRight: `<rect x="3" y="3" width="7" height="18" rx="1"/><rect x="14" y="3" width="7" height="18" rx="1"/>`,
  maximize: `<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>`,
  minimize: `<path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3"/>`,
  fullscreen: `<path d="M3 7V5a2 2 0 0 1 2-2h2M15 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/>`,
  slash: `<circle cx="12" cy="12" r="10"/><path d="m4.93 4.93 14.14 14.14"/>`,
  hash: `<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>`,
  code: `<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>`,
  braces: `<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h1M16 21h1a2 2 0 0 0 2-2v-5a2 2 0 0 1 2-2 2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>`,
  database: `<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.7-4 3-9 3s-9-1.3-9-3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5"/>`,
  server: `<rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1.5"/><circle cx="6" cy="18" r="1.5"/>`,

  /* ── Misc ───────────────────────────────────────────────────────── */
  eye: `<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>`,
  eyeOff: `<path d="M9.9 4.2A9.5 9.5 0 0 1 12 4c7 0 10 7 10 7a12.3 12.3 0 0 1-3.2 5.2M6.2 6.2A14.2 14.2 0 0 0 2 12s3 7 10 7a9.6 9.6 0 0 0 5.2-1.6M2 2l20 20"/><path d="M4.7 4.7 7 7"/><path d="m10.6 10.6 2.8 2.8"/>`,
  lock: `<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 1 1 10 0v4"/>`,
  unlock: `<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 1 1 9.9-1"/>`,
  shield: `<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>`,
  shieldCheck: `<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>`,
  bookmark: `<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2Z"/>`,
  flag: `<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1Z"/><line x1="4" y1="22" x2="4" y2="15"/>`,
  target: `<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>`,
  crosshair: `<circle cx="12" cy="12" r="10"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>`,
  refresh: `<path d="M21 2v6h-6M3 22v-6h6"/><path d="M3.5 16a9 9 0 0 1 15.8-4.5L21 14M20.5 8a9 9 0 0 0-15.8 4.5L3 10"/>`,
  rotateCw: `<polyline points="23 4 23 10 17 10"/><path d="M20.5 7a9 9 0 1 0-3.1 14.9L19 23"/>`,
  trash: `<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/>`,
  edit: `<path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>`,
  pencil: `<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4Z"/>`,
  filter: `<polygon points="22 3 2 3 10 12.5 10 19 14 21 14 12.5 22 3"/>`,
  sliders: `<line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><circle cx="4" cy="12" r="2"/><circle cx="12" cy="10" r="2"/><circle cx="20" cy="14" r="2"/>`,
  list: `<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>`,
  grid: `<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>`,
  home: `<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><polyline points="9 22 9 12 15 12 15 22"/>`,
  building: `<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 6h.01M15 6h.01M9 10h.01M15 10h.01M9 14h.01M15 14h.01M9 18h6"/>`,
  store: `<path d="m2 7 4.4-4.4a2 2 0 0 1 2.8 0l8.8 8.8"/><path d="M11.3 3 8.7 5.6l8.8 8.8L21 12M2 7v13a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7"/>`,
  shopping: `<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/>`,
};

/* ── Export ──────────────────────────────────────────────────────────── */
export { ICONS };
export default icon;