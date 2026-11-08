// Captures everything the README shows and the pages need:
//   stills  the calm still of every chapter (the poster is chapter 0), rendered from the real scene: stills/<c>-<i>-<wide|phone>-<light|dark>.webp
//   pngs    every chapter with its text, at 1440 and 390, light and dark: png/<c>-<i>-<1440|390>-<light|dark>.png
//   motion  a scroll-through per concept, rendered frame by frame (so it's smooth whatever the machine): motion/<c>.mp4
// node tools/capture.mjs [stills|pngs|motion] [a,b,c]     (no argument = all)
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, readdirSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, exe, GPU, url, open } from './shot.mjs';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const want = process.argv[2] ? process.argv[2].split(',') : ['stills', 'pngs', 'motion'];
const concepts = (process.argv[3] || 'a,b,c').split(',');
const only = process.argv[4] ? process.argv[4].split(',').map(Number) : [0, 1, 2, 3, 4, 5, 6]; // chapters
const on = (k) => want.includes(k);
const tmp = join(tmpdir(), 'cover3d-cap'); mkdirSync(tmp, { recursive: true });
// where each chapter is captured: its most telling moment
export const LOCAL = { a: [0, 0.9, 0.62, 0.92, 0.85, 0.36, 0.8], b: [0, 0.85, 0.85, 0.92, 0.85, 0.4, 0.85], c: [0, 0.6, 0.5, 0.85, 0.55, 0.45, 0.8] };
const b = await chromium.launch({ executablePath: exe, args: GPU });
const kb = (f) => (statSync(f).size / 1024).toFixed(0);

async function state(c, i, mode, w, h, dpr, extra = '') {
  const { ctx, pg } = await open(b, w, h, dpr);
  await pg.goto(url(`${c}.html?shot=${i}&local=${LOCAL[c][i]}&mode=${mode}&clean${extra}`));
  await pg.waitForFunction(() => window.__cover, null, { timeout: 30000 });
  await pg.waitForTimeout(3200);
  return { ctx, pg };
}

if (on('stills')) for (const c of concepts) for (const mode of ['light', 'dark']) for (const [lay, w, h, dpr] of [['wide', 1440, 900, 1], ['phone', 390, 844, 2]]) for (const i of only) {
  const { ctx, pg } = await state(c, i, mode, w, h, dpr);
  // display:none, not visibility: the scene sets each anchor's visibility itself, which would win
  await pg.addStyleTag({ content: '.top,.rail,main,.foot,.proto{visibility:hidden!important} .anchors{display:none!important}' });
  await pg.waitForTimeout(150);
  const f = join(tmp, `${c}-${i}-${lay}-${mode}.png`), out = join(root, 'stills', `${c}-${i}-${lay}-${mode}.webp`);
  await pg.screenshot({ path: f });
  execFileSync('magick', [f, '-quality', lay === 'wide' ? '72' : '68', '-define', 'webp:method=6', out]);
  console.log('still', c, i, lay, mode, kb(out) + ' KB');
  await ctx.close();
}

if (on('pngs')) for (const c of concepts) for (const mode of ['light', 'dark']) for (const [w, h, dpr] of [[1440, 900, 1], [390, 844, 2]].filter(([w]) => !process.env.WIDTH || +process.env.WIDTH === w)) for (const i of only) {
  const { ctx, pg } = await state(c, i, mode, w, h, dpr);
  const f = join(tmp, `p-${c}-${i}-${w}-${mode}.png`), out = join(root, 'png', `${c}-${i}-${w}-${mode}.png`);
  await pg.screenshot({ path: f });
  // 256-colour PNGs with light dithering keep the set small enough for a repo
  execFileSync('magick', [f, '-quantize', 'sRGB', '-dither', 'FloydSteinberg', '-colors', '256', '-define', 'png:compression-level=9', `PNG8:${out}`]);
  console.log('png', c, i, w, mode, kb(out) + ' KB');
  await ctx.close();
}

if (on('motion')) for (const c of concepts) {
  const dir = join(tmp, 'f-' + c); rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
  const { ctx, pg } = await open(b, 1280, 800, 1);
  await pg.goto(url(`${c}.html?capture&clean&mode=light`));
  await pg.waitForFunction(() => window.__cover && window.__cover.step, null, { timeout: 30000 });
  await pg.waitForTimeout(800);
  // a reader's pace: linger on each pinned card, move briskly between them
  const plan = await pg.evaluate(() => { const G = window.GA_COVER; G.measure(); return G.anchors().map((a) => [a.s, a.e, a.t]); });
  const keys = []; let t = 0; const FPS = 30;
  const push = (y, dur) => { keys.push([t, y]); t += dur; };
  plan.forEach(([s, e, tr], i) => { push(s, i === 0 ? 1.2 : 0); push(s, 0.4); push(e, i === 0 ? 1.0 : 3.2); if (i < plan.length - 1) push(e, 0.3), push(tr, i === 0 ? 2.6 : 1.4); else push(e, 1.6); });
  keys.push([t, keys[keys.length - 1][1]]);
  const yAt = (tt) => { for (let k = 0; k < keys.length - 1; k++) { const [t0, y0] = keys[k], [t1, y1] = keys[k + 1]; if (tt <= t1) { const f = t1 > t0 ? (tt - t0) / (t1 - t0) : 1; const e = f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2; return y0 + (y1 - y0) * e; } } return keys[keys.length - 1][1]; };
  const n = Math.ceil(t * FPS);
  for (let k = 0; k < n; k++) {
    await pg.evaluate((y) => { scrollTo(0, y); window.GA_COVER.read(); window.__cover.step(1 / 30); }, yAt(k / FPS));
    await pg.screenshot({ path: join(dir, String(k).padStart(5, '0') + '.jpg'), type: 'jpeg', quality: 88 });
  }
  await ctx.close();
  const mp4 = join(root, 'motion', `${c}.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', join(dir, '%05d.jpg'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '27', '-preset', 'slow', '-movflags', '+faststart', mp4]);
  console.log('motion', c, n + ' frames', (n / FPS).toFixed(1) + ' s', kb(mp4) + ' KB');
}
await b.close();
