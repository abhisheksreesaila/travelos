/* ═══════════════════════════════════════════════════════════════════════════
   TravelOS Brand Kit — Logo, marks, playful elements
   Zero-dependency ES module. All icons are inline SVG.
   ═══════════════════════════════════════════════════════════════════════════ */

/* ── Brand color palette ────────────────────────────────────────────────── */
export const BRAND = {
  sun:       '#ff6e40',
  sunLight:  '#ff8a65',
  sunDeep:   '#e64a2e',
  gold:      '#fbbf24',
  coral:     '#ff5c72',
  mint:      '#34d399',
  sky:       '#38bdf8',
  plum:      '#a78bfa',
  navy:      '#142448',
  ink:       '#182332',
  paper:     '#f8f6f0',
  white:     '#fffdf9',
};

/* ── Logo marks ──────────────────────────────────────────────────────────── */

/** Full TravelOS logo SVG string. Use size to scale. */
export function logoMark(size = 32) {
  return `<svg class="brand-logo" width="${size}" height="${size}" viewBox="0 0 40 40" aria-hidden="true" fill="none">
  <rect x="2" y="8" width="36" height="24" rx="6" fill="${BRAND.sun}" transform="rotate(-8 20 20)"/>
  <path d="M12 26h16l-3-9h-10l-3 9Z" fill="${BRAND.white}" opacity=".95"/>
  <path d="M10 28h20v4a2 2 0 0 1-2 2H12a2 2 0 0 1-2-2v-4Z" fill="${BRAND.gold}"/>
  <circle cx="14" cy="30" r="2.5" fill="${BRAND.ink}" opacity=".3"/>
  <circle cx="26" cy="30" r="2.5" fill="${BRAND.ink}" opacity=".3"/>
  <path d="M28 16h1.5a3 3 0 0 1 3 3v2a2 2 0 0 1-2 2H28" stroke="${BRAND.white}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity=".5"/>
  <path d="M20 13v2" stroke="${BRAND.gold}" stroke-width="2" stroke-linecap="round"/>
  <circle cx="17" cy="22" r="1.5" fill="${BRAND.ink}" opacity=".25"/>
  <circle cx="20" cy="22" r="1.5" fill="${BRAND.ink}" opacity=".25"/>
  <circle cx="23" cy="22" r="1.5" fill="${BRAND.ink}" opacity=".25"/>
</svg>`;
}

/** Smaller, square icon mark used for favicon / app icon. */
export function appIcon(size = 48) {
  return `<svg class="brand-icon" width="${size}" height="${size}" viewBox="0 0 48 48" aria-hidden="true" fill="none">
  <rect x="4" y="4" width="40" height="40" rx="12" fill="${BRAND.sun}"/>
  <path d="M14 30h20l-3.5-11H17.5L14 30Z" fill="${BRAND.white}" opacity=".95"/>
  <path d="M11 33h26v5a3 3 0 0 1-3 3H14a3 3 0 0 1-3-3v-5Z" fill="${BRAND.gold}"/>
  <circle cx="16" cy="35.5" r="3" fill="${BRAND.ink}" opacity=".25"/>
  <circle cx="32" cy="35.5" r="3" fill="${BRAND.ink}" opacity=".25"/>
  <path d="M35 18h2a4 4 0 0 1 4 4v3a3 3 0 0 1-3 3h-3" stroke="${BRAND.white}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" opacity=".5"/>
  <circle cx="20" cy="25" r="2" fill="${BRAND.ink}" opacity=".2"/>
  <circle cx="24" cy="25" r="2" fill="${BRAND.ink}" opacity=".2"/>
  <circle cx="28" cy="25" r="2" fill="${BRAND.ink}" opacity=".2"/>
</svg>`;
}

/* ── Playful elements ───────────────────────────────────────────────────── */

/** Dot pattern background — fun decorative element for cards/heroes. */
export function dotPattern(opacity = 0.12) {
  return `<div class="dot-pattern" aria-hidden="true" style="--dot-opacity:${opacity}">
  <svg width="100%" height="100%"><defs><pattern id="dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.5" fill="currentColor" opacity="var(--dot-opacity, 0.12)"/></pattern></defs><rect width="100%" height="100%" fill="url(#dots)"/></svg>
</div>`;
}

/** Sparkle icon — fun accent element. */
export function sparkle(size = 20) {
  return `<svg class="sparkle" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true" fill="none">
  <path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2Z" fill="${BRAND.gold}"/>
  <path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" fill="${BRAND.sun}"/>
</svg>`;
}

/** Confetti burst — used for success states or celebration moments. */
export function confettiBurst(size = 80) {
  const pieces = [
    { x: 40, y: 40, w: 4, h: 8, color: BRAND.sun, rot: 15 },
    { x: 38, y: 38, w: 3, h: 6, color: BRAND.mint, rot: -20 },
    { x: 42, y: 42, w: 4, h: 5, color: BRAND.sky, rot: 30 },
    { x: 37, y: 41, w: 3, h: 7, color: BRAND.gold, rot: -10 },
    { x: 41, y: 37, w: 3, h: 6, color: BRAND.plum, rot: 25 },
    { x: 39, y: 43, w: 4, h: 5, color: BRAND.coral, rot: -25 },
  ];
  const rects = pieces.map((p) =>
    `<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="1" fill="${p.color}" transform="rotate(${p.rot} ${p.x + p.w / 2} ${p.y + p.h / 2})" opacity="0.85"/>`
  ).join('');
  return `<svg class="confetti-burst" width="${size}" height="${size}" viewBox="0 0 80 80" aria-hidden="true">${rects}</svg>`;
}

/** Wave divider — playful section separator. */
export function waveDivider(color = BRAND.sun) {
  return `<div class="wave-divider" aria-hidden="true">
  <svg viewBox="0 0 1200 60" preserveAspectRatio="none"><path d="M0 30 C 200 0, 400 60, 600 30 S 1000 0, 1200 30 L 1200 60 L 0 60 Z" fill="${color}" opacity="0.12"/></svg>
</div>`;
}

/* ── Typography helpers ──────────────────────────────────────────────────── */

/** Gradient text effect for hero headlines. */
export const GRADIENT_TEXT_STYLE = `
  background: linear-gradient(135deg, ${BRAND.sun} 0%, ${BRAND.coral} 40%, ${BRAND.gold} 70%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;

/** Color burst style for emphasized text. */
export const COLOR_BURST_STYLE = `
  background: linear-gradient(90deg, ${BRAND.sun} 0%, ${BRAND.coral} 25%, ${BRAND.gold} 50%, ${BRAND.mint} 75%, ${BRAND.sky} 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
`;