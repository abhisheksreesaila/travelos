// Screenshots one artboard (or a page) with headless Chromium on the GPU.
// node tools/shot.mjs <page?query> <out.png> <width> <height> [waitMs] [full] [js-before-shot]
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const mods = process.env.COCKPIT_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const { chromium } = createRequire(join(mods, 'x.js'))('playwright');
const here = dirname(fileURLToPath(import.meta.url));
export const exe = process.env.CHROME || join(homedir(), '.cache/ms-playwright/chromium-1248/chrome-linux64/chrome');
export const GPU = ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--allow-file-access-from-files'];
export const url = (p) => 'file://' + resolve(here, '..', p);
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [page, out, w, h, wait = 2500, full = '', js = ''] = process.argv.slice(2);
  const b = await chromium.launch({ executablePath: exe, args: GPU });
  const mobile = +w < 600;
  const ctx = await b.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
  const pg = await ctx.newPage();
  pg.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('console:', m.type(), m.text()); });
  pg.on('pageerror', (e) => console.log('pageerror:', e.message));
  await pg.goto(url(page)); await pg.waitForTimeout(+wait);
  if (js) { await pg.evaluate(js); await pg.waitForTimeout(1600); }
  await pg.screenshot({ path: out, fullPage: full === 'full' });
  await b.close();
}
