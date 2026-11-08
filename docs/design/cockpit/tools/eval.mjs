// Prints the result of a JS expression evaluated in one artboard: node tools/eval.mjs <page?query> <width> <height> <js> [waitMs]
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { exe, GPU, url } from './shot.mjs';
const { chromium } = createRequire(join(process.env.COCKPIT_MODULES || join(homedir(), '.cache/story3d-build/node_modules'), 'x.js'))('playwright');
const [page, w, h, js, wait = 1500] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: exe, args: GPU });
const ctx = await b.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1, isMobile: +w < 600, hasTouch: +w < 600 });
const pg = await ctx.newPage();
pg.on('pageerror', (e) => console.log('pageerror:', e.message));
await pg.goto(url(page)); await pg.waitForTimeout(+wait);
console.log(JSON.stringify(await pg.evaluate(js), null, 1));
await b.close();
