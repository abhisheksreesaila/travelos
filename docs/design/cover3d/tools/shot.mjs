// One screenshot of a page state: node tools/shot.mjs '<page?query>' out.png <width> <height> [waitMs] [dpr]
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const mods = process.env.COVER3D_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
export const { chromium } = createRequire(join(mods, 'x.js'))('playwright');
const here = dirname(fileURLToPath(import.meta.url));
export const exe = process.env.CHROME || join(homedir(), '.cache/ms-playwright/chromium-1248/chrome-linux64/chrome');
export const GPU = ['--use-angle=vulkan', '--enable-features=Vulkan', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'];
export const url = (p) => 'file://' + resolve(here, '..', p);
export async function open(b, w, h, dpr) {
  const mobile = w < 760;
  const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: dpr || (mobile ? 2 : 1), isMobile: mobile, hasTouch: mobile });
  const pg = await ctx.newPage();
  pg.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('console:', m.type(), m.text().slice(0, 300)); });
  pg.on('pageerror', (e) => console.log('pageerror:', e.message));
  return { ctx, pg };
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [page, out, w = 1440, h = 900, wait = 2500, dpr = 0] = process.argv.slice(2);
  const b = await chromium.launch({ executablePath: exe, args: GPU });
  const { pg } = await open(b, +w, +h, +dpr);
  await pg.goto(url(page)); await pg.waitForTimeout(+wait);
  await pg.screenshot({ path: out });
  await b.close();
}
