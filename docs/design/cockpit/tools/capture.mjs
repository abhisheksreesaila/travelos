// Captures every artboard the README shows: three directions × light and dark × the four screens at 1440 and 390,
// the paste moment's phases, and one extra cockpit per direction on the arrival day (the long drive from Reno).
// node tools/capture.mjs [1|2|3]... [--force]   (no direction = all three; existing PNGs are kept unless --force)
import { createRequire } from 'node:module';
import { mkdirSync, statSync, readdirSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { exe, GPU, url } from './shot.mjs';
const { chromium } = createRequire(join(process.env.COCKPIT_MODULES || join(homedir(), '.cache/story3d-build/node_modules'), 'x.js'))('playwright');
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, 'png'); mkdirSync(out, { recursive: true });
const DIRS = { 1: '1-diorama', 2: '2-widgets', 3: '3-ticket' };
const force = process.argv.includes('--force');
const want = process.argv.slice(2).filter((a) => !a.startsWith('--')); const dirs = want.length ? want : ['1', '2', '3'];
let b = await chromium.launch({ executablePath: exe, args: GPU });
const shots = [
  ['cockpit', 'dk'], ['cockpit', 'ph'], ['cockpit', 'ph', 'full'], ['cockpit', 'dk', '', '&day=0', 'arrive'],
  ['book', 'dk'], ['book', 'ph'], ['book', 'ph', 'full'], ['day', 'ph'], ['day', 'ph', 'full'],
  ['paste', 'dk', '', '&phase=read', 'read'], ['paste', 'dk', '', '&phase=landed', 'landed'],
  ['paste', 'ph', '', '&phase=open', 'open'], ['paste', 'ph', '', '&phase=read', 'read'], ['paste', 'ph', '', '&phase=landed', 'landed'],
];
for (const d of dirs) for (const mode of ['light', 'dark']) {
  for (const [screen, size, full, extra = '', tag = ''] of shots) {
    const ph = size === 'ph';
    const name = `${d}-${screen}${tag ? '-' + tag : ''}-${ph ? 390 : 1440}-${mode}${full ? '-full' : ''}.png`;
    if (d === '1' && screen === 'cockpit' && full) continue; // Direction 1's phone cockpit is one fixed screen (the sheet drags)
    if (!force && existsSync(join(out, name))) continue;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const ctx = await b.newContext({ viewport: { width: ph ? 390 : 1440, height: ph ? 844 : 900 }, deviceScaleFactor: ph ? 2 : 1, isMobile: ph, hasTouch: ph });
        const pg = await ctx.newPage();
        pg.on('pageerror', (e) => console.log('pageerror', d, screen, e.message));
        await pg.goto(url(`${DIRS[d]}.html?bare=1&screen=${screen}&size=${size}&mode=${mode}${extra}`));
        await pg.waitForFunction(() => window.__ready, null, { timeout: 30000 }).catch(() => console.log('not ready', d, screen, size));
        await pg.waitForTimeout(d === '2' ? 2600 : 2200);
        if (screen === 'paste' && tag === 'landed') await pg.waitForTimeout(900);
        await pg.screenshot({ path: join(out, name), fullPage: !!full });
        await ctx.close();
        console.log(name, Math.round(statSync(join(out, name)).size / 1024) + ' KB');
        break;
      } catch (e) {
        console.log('retry', name, e.message.split('\n')[0]);
        try { await b.close(); } catch {}
        b = await chromium.launch({ executablePath: exe, args: GPU });
      }
    }
  }
}
await b.close();
const total = readdirSync(out).reduce((n, f) => n + statSync(join(out, f)).size, 0);
console.log('total', (total / 1048576).toFixed(1), 'MB');
