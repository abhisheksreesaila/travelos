// Screenshots every artboard: node tools/shoot.mjs [screen ...]
// Uses the cockpit's Playwright setup (COCKPIT_MODULES, CHROME). PNGs land in png/<screen>[-theme]-<1440|390>-<light|dark>[-full].png
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const mods = process.env.COCKPIT_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const { chromium } = createRequire(join(mods, 'x.js'))('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const exe = process.env.CHROME || join(homedir(), '.cache/ms-playwright/chromium-1248/chrome-linux64/chrome');
const ALL = ['creators', 'pick', 'drafting', 'editor', 'trail', 'profile', 'stats', 'claim', 'admin', 'where', 'book', 'paste', 'detail'];
const want = process.argv.slice(2).length ? process.argv.slice(2) : ALL;
const b = await chromium.launch({ executablePath: exe, args: ['--allow-file-access-from-files'] });
const jobs = [];
for (const s of want) for (const mode of ['light', 'dark']) for (const size of ['dk', 'ph']) {
  jobs.push({ s, mode, size, extra: s === 'paste' ? '&phase=read' : '' });
  if (s === 'trail') for (const t of ['scrapbook', 'magazine', 'minimal']) jobs.push({ s, mode, size, extra: '&theme=' + t, tag: '-' + t });
}
for (const j of jobs) {
  const ph = j.size === 'ph';
  const ctx = await b.newContext({ viewport: { width: ph ? 390 : 1440, height: ph ? 844 : 900 }, deviceScaleFactor: ph ? 2 : 1, isMobile: ph, hasTouch: ph, reducedMotion: 'reduce' });
  const pg = await ctx.newPage();
  pg.on('pageerror', (e) => console.log('pageerror', j.s, e.message));
  await pg.goto('file://' + resolve(here, '..', `screen.html?s=${j.s}&size=${j.size}&mode=${j.mode}${j.extra}`));
  await pg.waitForTimeout(j.s === 'book' || j.s === 'paste' ? 2200 : 900);
  const base = join(here, '..', 'png', `${j.s}${j.tag || ''}-${ph ? 390 : 1440}-${j.mode}`);
  await pg.screenshot({ path: base + '.png' });
  const h = await pg.evaluate(() => document.documentElement.scrollHeight);
  if (!j.tag && h > (ph ? 860 : 920)) await pg.screenshot({ path: base + '-full.png', fullPage: true });
  await ctx.close();
}
await b.close();
console.log('shots:', jobs.length);
// then, to keep the repo light (8-bit, as the cover's PNGs): magick mogrify -colors 256 png/*.png
