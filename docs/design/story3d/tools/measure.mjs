// Frame-rate check: a 390x844 phone (DPR 3, touch), Chromium CPU throttled 4x, the story playing for 8 s.
// Runs twice: on this machine's GPU (Vulkan), and on SwiftShader (software GL, a stand-in for a weak phone GPU).
// The weak-device fallback is switched off with ?measure so the raw numbers show. Writes tools/fps.json.
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { exe, GPU, url } from './shot.mjs';
const mods = process.env.STORY3D_MODULES || join(homedir(), '.cache/story3d-build/node_modules');
const { chromium } = createRequire(join(mods, 'x.js'))('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const out = {};
for (const [gl, args] of [['gpu', GPU], ['swiftshader', []]]) {
  const b = await chromium.launch({ executablePath: exe, args });
  for (const proto of ['diorama', 'postcards', 'globe']) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
    const pg = await ctx.newPage();
    const cdp = await ctx.newCDPSession(pg); await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    await pg.goto(url(`${proto}.html?noauto&measure&mode=light`));
    await pg.evaluate(() => document.querySelector('#stage').scrollIntoView({ block: 'center' }));
    await pg.waitForFunction(() => window.__story, null, { timeout: 30000 });
    await pg.waitForTimeout(1500);
    const renderer = await pg.evaluate(() => { const g = document.querySelector('#stage canvas').getContext('webgl2'); const e = g.getExtension('WEBGL_debug_renderer_info'); return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : '?'; });
    await pg.evaluate(() => { window.__story.play(true); window.__frames.length = 0; window.__work.length = 0; });
    await pg.waitForTimeout(8000);
    const [f, w] = await pg.evaluate(() => [window.__frames.slice(), window.__work.slice()]); const ws = [...w].sort((a, b) => a - b);
    const s = [...f].sort((a, b) => a - b), mean = f.reduce((a, b) => a + b, 0) / f.length;
    out[`${proto}/${gl}`] = { renderer, frames: f.length, fps: +(1000 / mean).toFixed(1), median_ms: +s[Math.floor(s.length / 2)].toFixed(1), p95_ms: +s[Math.floor(s.length * 0.95)].toFixed(1), over_33ms: +((f.filter((d) => d > 33.4).length / f.length) * 100).toFixed(1), js_ms_median: +ws[Math.floor(ws.length / 2)].toFixed(2), js_ms_p95: +ws[Math.floor(ws.length * 0.95)].toFixed(2) };
    console.log(proto, gl, JSON.stringify(out[`${proto}/${gl}`]));
    await ctx.close();
  }
  await b.close();
}
writeFileSync(join(here, 'fps.json'), JSON.stringify(out, null, 2) + '\n');
