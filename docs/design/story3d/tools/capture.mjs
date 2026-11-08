// Captures everything the README shows: the calm stills (from the real scene), page PNGs at 390 and 1440 in
// light and dark, the Thank and Fork moments, and a phone screen recording plus a frame strip per prototype.
// node tools/capture.mjs [stills|pages|moments|motion]...   (no argument = all)
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, readdirSync, renameSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { exe, GPU, url } from './shot.mjs';
const mods = process.env.STORY3D_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const { chromium } = createRequire(join(mods, 'x.js'))('playwright');
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const P = ['diorama', 'postcards', 'globe'], MODES = ['light', 'dark'];
const want = process.argv.slice(2); const on = (k) => !want.length || want.includes(k);
const tmp = join(tmpdir(), 'story3d-cap'); mkdirSync(tmp, { recursive: true });
const b = await chromium.launch({ executablePath: exe, args: GPU });
const ctxFor = (w, h, dsf) => b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: dsf, isMobile: w < 600, hasTouch: w < 600 });
const ready = (pg) => pg.waitForFunction(() => window.__story, null, { timeout: 30000 });
const toStage = (pg) => pg.evaluate(() => { const s = document.querySelector('#stage'); scrollTo(0, s.getBoundingClientRect().top + scrollY - (innerWidth < 600 ? 12 : 90)); });

if (on('stills')) for (const p of P) for (const m of MODES) for (const [kind, w, h, dsf] of [['phone', 390, 844, 2], ['wide', 1440, 900, 1.5]]) {
  const ctx = await ctxFor(w, h, dsf); const pg = await ctx.newPage();
  await pg.goto(url(`${p}.html?capture&mode=${m}`)); await toStage(pg); await ready(pg); await pg.waitForTimeout(3800);
  await pg.addStyleTag({ content: '.cap,.stage-tools,.stage-hint,.sharebar{visibility:hidden!important}' });
  const f = join(tmp, `${p}-${kind}-${m}.png`); await pg.locator('#stage').screenshot({ path: f });
  execFileSync('magick', [f, '-quality', '78', join(root, 'stills', `${p}-${kind}-${m}.webp`)]);
  await ctx.close(); console.log('still', p, kind, m);
}

if (on('pages')) for (const p of P) for (const m of MODES) for (const w of [390, 1440]) {
  const ctx = await ctxFor(w, w < 600 ? 844 : 900, w < 600 ? 2 : 1); const pg = await ctx.newPage();
  await pg.goto(url(`${p}.html?day=2&mode=${m}`)); await toStage(pg); await ready(pg); await pg.waitForTimeout(4200);
  await pg.evaluate(() => scrollTo(0, 0)); await pg.waitForTimeout(300);
  await pg.screenshot({ path: join(root, 'png', `${p}-${w}-${m}.png`), fullPage: true });
  await ctx.close(); console.log('page', p, w, m);
}

if (on('moments')) for (const p of P) {
  const ctx = await ctxFor(390, 844, 2); const pg = await ctx.newPage();
  await pg.goto(url(`${p}.html?day=3&mode=light`)); await toStage(pg); await ready(pg); await pg.waitForTimeout(4200);
  await pg.click('.sharebar .js-thank'); await pg.waitForTimeout(260);
  await pg.screenshot({ path: join(root, 'png', `${p}-390-thank.png`) });
  await pg.waitForTimeout(1200); await pg.click('.sharebar .js-fork'); await pg.waitForTimeout(2200);
  await pg.screenshot({ path: join(root, 'png', `${p}-390-fork.png`) });
  await ctx.close(); console.log('moments', p);
}

if (on('motion')) for (const p of P) {
  const vdir = join(tmp, 'v-' + p); rmSync(vdir, { recursive: true, force: true });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, recordVideo: { dir: vdir, size: { width: 390, height: 844 } } });
  const pg = await ctx.newPage();
  await pg.goto(url(`${p}.html?mode=light`)); await toStage(pg); await ready(pg);
  await pg.waitForTimeout(p === 'globe' ? 19500 : 19000);
  await pg.click('.sharebar .js-thank'); await pg.waitForTimeout(1400);
  await pg.click('.sharebar .js-fork'); await pg.waitForTimeout(3000);
  await ctx.close();
  const webm = join(vdir, readdirSync(vdir)[0]), mp4 = join(root, 'motion', `${p}.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', webm, '-vf', 'fps=30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '28', '-movflags', '+faststart', mp4]);
  const dur = parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4]).toString());
  const frames = [];
  for (const [k, t] of [0.12, 0.25, 0.4, 0.55, 0.7, 0.85, 0.985].entries()) { const f = join(tmp, `${p}-f${k}.png`); execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', String(dur * t), '-i', mp4, '-frames:v', '1', '-vf', 'crop=390:600:0:0', f]); frames.push(f); }
  execFileSync('magick', [...frames, '-bordercolor', '#F2F2F5', '-border', '6', '+append', join(root, 'motion', `${p}-strip.png`)]);
  console.log('motion', p, dur.toFixed(1) + 's');
}
await b.close();
