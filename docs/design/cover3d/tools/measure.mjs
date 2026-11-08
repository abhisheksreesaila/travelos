// Frame-rate and budget check. For each concept: a 390x844 phone (DPR 3, capped by the scene to 1.5, touch),
// Chromium CPU throttled 4x, scrolled top to bottom at a reader's pace for about 24 s, on this machine's GPU and on
// SwiftShader (software GL, a stand-in for a weak phone GPU); then a 1440x900 laptop on the GPU, unthrottled.
// The quality governor and the weak-device fallback are switched off (?measure) so the numbers are raw.
// Also checks that rendering stops when the footer covers the stage and when the tab is hidden. Writes tools/fps.json.
import { writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, exe, GPU, url } from './shot.mjs';
const here = dirname(fileURLToPath(import.meta.url));
const concepts = (process.argv[2] && !['pause', 'weak'].includes(process.argv[2]) ? process.argv[2] : 'a,b,c').split(',');
const out = {};
const stats = (f, w) => {
  const s = [...f].sort((a, b) => a - b), ws = [...w].sort((a, b) => a - b), mean = f.reduce((a, b) => a + b, 0) / f.length;
  const q = (arr, p) => +arr[Math.min(arr.length - 1, Math.floor(arr.length * p))].toFixed(1);
  return { frames: f.length, fps: +(1000 / mean).toFixed(1), median_ms: q(s, 0.5), p95_ms: q(s, 0.95), over_33ms_pct: +((f.filter((d) => d > 33.4).length / f.length) * 100).toFixed(1), js_ms_median: +q(ws, 0.5), js_ms_p95: +q(ws, 0.95) };
};
async function run(b, c, { w, h, dpr, mobile, throttle }) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: dpr, isMobile: mobile, hasTouch: mobile });
  const pg = await ctx.newPage();
  pg.on('pageerror', (e) => console.log('pageerror:', e.message));
  if (throttle) { const cdp = await ctx.newCDPSession(pg); await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle }); }
  await pg.goto(url(`${c}.html?measure&mode=light&clean`));
  await pg.waitForFunction(() => window.__cover && window.__cover.S, null, { timeout: 60000 });
  await pg.waitForTimeout(2500);
  const info = await pg.evaluate(() => { const r = window.__cover.S.renderer, g = r.getContext(), e = g.getExtension('WEBGL_debug_renderer_info'); return { renderer: e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : '?', dpr: r.getPixelRatio(), quality: window.GA_COVER.quality }; });
  // scroll the whole story in the page itself, sampling draw calls and triangles as it goes
  const res = await pg.evaluate(async () => {
    const S = window.__cover.S, end = document.querySelector('.foot').offsetTop - innerHeight - 4, dur = 24000;
    window.__frames.length = 0; window.__work.length = 0;
    const calls = [], tris = []; let t0 = 0;
    await new Promise((done) => { const step = (t) => { if (!t0) t0 = t; const k = Math.min(1, (t - t0) / dur); scrollTo(0, end * k); if (k < 1) requestAnimationFrame(step); else done(); }; requestAnimationFrame(step);
      const iv = setInterval(() => { calls.push(S.renderer.info.render.calls); tris.push(S.renderer.info.render.triangles); if (performance.now() - t0 > dur) clearInterval(iv); }, 400); });
    return { f: window.__frames.slice(), w: window.__work.slice(), calls, tris };
  });
  const s = stats(res.f, res.w);
  s.draw_calls_max = Math.max(...res.calls); s.triangles_max = Math.max(...res.tris);
  return { ...info, ...s, ctx, pg };
}
async function pauseChecks(pg) {
  const frame = () => pg.evaluate(() => window.__cover.S.renderer.info.render.frame);
  const idle = async () => { const a = await frame(); await pg.waitForTimeout(1500); return (await frame()) - a; };
  await pg.evaluate(() => scrollTo(0, document.documentElement.scrollHeight)); await pg.waitForTimeout(600);
  const underFooter = { renders_in_1_5s: await idle(), running: await pg.evaluate(() => window.__cover.running) };
  await pg.evaluate(() => scrollTo(0, window.GA_COVER.anchors()[3].s + 50)); await pg.waitForTimeout(600);
  const back = await idle();
  // a hidden tab: the page sees document.hidden turn true and a visibilitychange event, as when you switch tabs
  await pg.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); });
  await pg.waitForTimeout(300);
  const hidden = { renders_in_1_5s: await idle(), running: await pg.evaluate(() => window.__cover.running) };
  await pg.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')); });
  await pg.waitForTimeout(300);
  const shown = await idle();
  return { paused_under_footer: underFooter, renders_in_1_5s_back_in_story: back, paused_when_hidden: hidden, renders_in_1_5s_when_shown_again: shown };
}
if (process.argv[2] === 'weak') {
  // a weak GPU with the governor ON (what a visitor would get): software GL, phone, CPU 4x. Where does it settle?
  const prev = JSON.parse((await import('node:fs')).readFileSync(join(here, 'fps.json'), 'utf8'));
  const b = await chromium.launch({ executablePath: exe, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  for (const c of ['a', 'b', 'c']) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }); const pg = await ctx.newPage();
    const cdp = await ctx.newCDPSession(pg); await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    await pg.goto(url(`${c}.html?mode=light&clean`)); await pg.waitForFunction(() => window.__cover && window.__cover.S, null, { timeout: 60000 });
    const t0 = Date.now(); const samples = [];
    // scroll slowly through chapter 1 for 20 s, sampling the pixel ratio the governor chose and whether it gave up
    while (Date.now() - t0 < 20000) {
      const s = await pg.evaluate((k) => { const G = window.GA_COVER; const a = G.anchors(); scrollTo(0, a[1].s + (a[1].e - a[1].s) * k); const f = window.__frames.slice(-30); return { dpr: +window.__cover.S.renderer.getPixelRatio().toFixed(2), still: G.still, ms: f.length ? +(f.reduce((x, y) => x + y, 0) / f.length).toFixed(1) : 0 }; }, (Date.now() - t0) / 20000);
      samples.push(s); await pg.waitForTimeout(1000);
    }
    const last = samples[samples.length - 1];
    prev[`${c}/phone-390-cpu4x/swiftshader-governor`] = { start_dpr: samples[0].dpr, settled_dpr: last.dpr, switched_to_stills: last.still, last_frame_ms: last.ms, timeline: samples.map((x) => `${x.dpr}${x.still ? ' still' : ''} ${x.ms}ms`) };
    console.log(c, JSON.stringify(prev[`${c}/phone-390-cpu4x/swiftshader-governor`]));
    await ctx.close();
  }
  await b.close(); writeFileSync(join(here, 'fps.json'), JSON.stringify(prev, null, 2) + '\n'); process.exit(0);
}
if (process.argv[2] === 'pause') {
  // only the pause checks, merged into an existing fps.json
  const prev = JSON.parse((await import('node:fs')).readFileSync(join(here, 'fps.json'), 'utf8'));
  const b = await chromium.launch({ executablePath: exe, args: GPU });
  for (const c of ['a', 'b', 'c']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); const pg = await ctx.newPage();
    await pg.goto(url(`${c}.html?measure&mode=light&clean`)); await pg.waitForFunction(() => window.__cover && window.__cover.S, null, { timeout: 60000 }); await pg.waitForTimeout(1500);
    const p = await pauseChecks(pg); Object.assign(prev[`${c}/laptop-1440/gpu`], p); delete prev[`${c}/laptop-1440/gpu`].paused_when_hidden_old;
    console.log(c, JSON.stringify(p)); await ctx.close();
  }
  await b.close(); writeFileSync(join(here, 'fps.json'), JSON.stringify(prev, null, 2) + '\n'); process.exit(0);
}
// GPU, plus software GL standing in for a weak phone GPU
for (const [gl, args] of [['gpu', GPU], ['swiftshader', ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']]]) {
  const b = await chromium.launch({ executablePath: exe, args });
  for (const c of concepts) {
    const r = await run(b, c, { w: 390, h: 844, dpr: 3, mobile: true, throttle: 4 });
    await r.ctx.close(); delete r.ctx; delete r.pg;
    out[`${c}/phone-390-cpu4x/${gl}`] = r; console.log(c, 'phone', gl, JSON.stringify(r));
  }
  if (gl === 'gpu') for (const c of concepts) {
    const r = await run(b, c, { w: 1440, h: 900, dpr: 1, mobile: false, throttle: 0 });
    // pause checks (renderer.info.render.frame counts every render): the footer covers the stage, then the tab is hidden
    Object.assign(r, await pauseChecks(r.pg));
    await r.ctx.close(); delete r.ctx; delete r.pg;
    out[`${c}/laptop-1440/${gl}`] = r; console.log(c, 'laptop', gl, JSON.stringify(r));
  }
  await b.close();
}
writeFileSync(join(here, 'fps.json'), JSON.stringify(out, null, 2) + '\n');
