// Fills the generated parts of README.md (the PNG gallery and the measured numbers) from png/, stills/,
// dist/sizes.json and tools/fps.json, between <!-- GALLERY --> / <!-- MEASURED --> markers. node tools/readme.mjs
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const sizes = JSON.parse(readFileSync(join(root, 'dist/sizes.json'), 'utf8'));
const fps = JSON.parse(readFileSync(join(root, 'tools/fps.json'), 'utf8'));
const kb = (n) => (n / 1024).toFixed(1);
const NAMES = { a: 'A · Fly-through', b: 'B · Four seasons', c: 'C · Road trip' };
const CH = ['0 · The book', '1 · Arrive', '2 · Fork', '3 · Plan together', '4 · Go', '5 · Share it back', '6 · Start'];
const CHB = ['0 · The book', '1 · Winter', '2 · Spring fork', '3 · Summer plan', '4 · Fall, go', '5 · A year later', '6 · Fork tree'];

/* gallery */
let g = '## Every chapter, captured\nEach chapter at its most telling moment, with its text: 1440 wide and 390 wide (phone, at 2×), day and night. The files are `png/<concept>-<chapter>-<1440|390>-<light|dark>.png`. Scroll-throughs: [`motion/a.mp4`](motion/a.mp4), [`motion/b.mp4`](motion/b.mp4), [`motion/c.mp4`](motion/c.mp4) (1280 × 800, day, rendered frame by frame).\n';
for (const c of ['a', 'b', 'c']) {
  const names = c === 'b' ? CHB : CH;
  g += `\n### ${NAMES[c]}\n\n| | ${names.join(' | ')} |\n|---|${names.map(() => '---').join('|')}|\n`;
  for (const [w, mode, width] of [[1440, 'light', 150], [1440, 'dark', 150], [390, 'light', 74], [390, 'dark', 74]]) {
    g += `| ${w} ${mode === 'light' ? 'day' : 'night'} | ${names.map((_, i) => `<a href="png/${c}-${i}-${w}-${mode}.png"><img src="png/${c}-${i}-${w}-${mode}.png" width="${width}" alt="${NAMES[c]}, chapter ${i}, ${w} ${mode}"></a>`).join(' | ')} |\n`;
  }
}

/* measured */
const sum = (re) => readdirSync(join(root, 'stills')).filter((f) => re.test(f)).reduce((a, f) => a + statSync(join(root, 'stills', f)).size, 0);
const fontGz = gzipSync(readFileSync(join(root, 'fonts.css')), { level: 9 }).length, cssGz = gzipSync(readFileSync(join(root, 'cover.css')), { level: 9 }).length;
let m = '### JavaScript (what a page downloads, gzip -9)\n| Page | `page.js` | scene script (three.js r187 tree-shaken inside) | **Total** | Brotli total |\n|---|---|---|---|---|\n';
for (const c of ['a', 'b', 'c']) m += `| ${NAMES[c]} | ${kb(sizes.page.gz)} KB | ${kb(sizes[c].gz)} KB | **${kb(sizes[c].totalGz)} KB** | ${kb(sizes[c].totalBr)} KB |\n`;
m += `\nAll three are under the 250 KB budget with room to spare. three.js is most of each scene script; the world, story and page code add about 25 KB. The scene script isn't loaded at all for reduced motion, without WebGL, or on a weak phone (2 GB of memory or 2 cores or fewer).\n`;
m += `\n### Assets (images, fonts)\nThe live world loads **no textures or models**: the terrain, lake, sky, trees, cabin, guidebook pages and printed map are generated in code. What a visit downloads besides the scripts:\n\n| | A | B | C |\n|---|---|---|---|\n`;
const poster = (c) => ['wide-light', 'wide-dark', 'phone-light', 'phone-dark'].map((v) => statSync(join(root, 'stills', `${c}-0-${v}.webp`)).size);
m += `| Poster (chapter 0's still, shown at once; laptop / phone, day) | ${['a', 'b', 'c'].map((c) => `${kb(poster(c)[0])} / ${kb(poster(c)[2])} KB`).join(' | ')} |\n`;
m += `| Geist, inlined in \`fonts.css\` (gzip) | ${kb(fontGz)} KB | same | same |\n| \`cover.css\` (gzip) | ${kb(cssGz)} KB | same | same |\n`;
m += `| Calm still version: the 7 stills one visit can load (laptop day, the largest set) | ${['a', 'b', 'c'].map((c) => `${kb(sum(new RegExp(`^${c}-\\d-wide-light`)))} KB`).join(' | ')} |\n`;
m += `| Every still on disk (7 chapters × laptop and phone × day and night) | ${['a', 'b', 'c'].map((c) => `${kb(sum(new RegExp(`^${c}-`)))} KB`).join(' | ')} |\n`;
m += `\nEverything a visit can load stays well under 1.5 MB. The stills load one chapter at a time, plus the next one ahead.\n`;
const r = (k) => fps[k] || {};
m += `\n### Frame rate (\`node tools/measure.mjs\`, results in \`tools/fps.json\`)\nA 390 × 844 phone (DPR 3, which the scene caps at 1.5; touch; the lighter phone tier), Chromium's CPU throttled 4×, scrolled through the whole story in about 24 s (the numbers cover the last 1,200 frames, about 20 s of it). It ran on this machine's GPU (${/RTX 3090/.test(r('a/phone-390-cpu4x/gpu').renderer || '') ? 'an RTX 3090 through Vulkan' : r('a/phone-390-cpu4x/gpu').renderer}) and on SwiftShader, Chromium's software renderer, standing in for a weak phone GPU. The quality governor and the weak-phone fallback were off, so the numbers are raw. Then a 1440 × 900 laptop, unthrottled.\n\n| | Phone, CPU 4×, GPU: fps · p95 frame | Phone, CPU 4×, software GL: fps · p95 · frames over 33 ms | Main-thread JS per frame, phone CPU 4× (median / p95) | Laptop 1440, GPU: fps · p95 | Draw calls · triangles (max, phone / laptop) |\n|---|---|---|---|---|---|\n`;
for (const c of ['a', 'b', 'c']) {
  const p = r(`${c}/phone-390-cpu4x/gpu`), s = r(`${c}/phone-390-cpu4x/swiftshader`), l = r(`${c}/laptop-1440/gpu`);
  m += `| ${NAMES[c]} | **${p.fps}** · ${p.p95_ms} ms | **${s.fps}** · ${s.p95_ms} ms · ${s.over_33ms_pct}% | ${p.js_ms_median} / ${p.js_ms_p95} ms | **${l.fps}** · ${l.p95_ms} ms | ${p.draw_calls_max} · ${(p.triangles_max / 1000).toFixed(0)}k / ${l.draw_calls_max} · ${(l.triangles_max / 1000).toFixed(0)}k |\n`;
}
m += `\n**What this does and doesn't prove.** The 4× CPU throttle slows the page's JavaScript the way a mid phone does, and the per-frame JavaScript shows how much of the 16.7 ms budget is left. But this desktop GPU is far faster than a phone's, and SwiftShader renders on the CPU without being throttled, so neither run is a real mid phone. The fallback exists for exactly that case: after 2.5 s the governor checks every second (or every 45 frames) and lowers the pixel ratio step by step, to 0.55 of it at worst, while frames average over 23 ms; if they still average over 45 ms for three checks in a row at the lowest setting, it switches to the still version. **Next step: open the three pages on the captain's own phone.**\n`;
const gv = ['a', 'b', 'c'].map((c) => { const w = r(`${c}/phone-390-cpu4x/swiftshader-governor`); const i = (w.timeline || []).findIndex((x) => /still/.test(x)); return `${NAMES[c].split(' ·')[0]} after about ${i < 0 ? 'more than 20' : i + 1} s`; });
m += `\nThe same weak-GPU phone with the governor **on**, which is what a visitor would get: all three step down to 0.55× resolution within about 4 s, still miss 22 fps, and switch to the calm stills (${gv.join(', ')}). On this machine's GPU the governor never has to act.\n`;
const pz = (c) => { const l = r(`${c}/laptop-1440/gpu`); const f = l.paused_under_footer || {}, h = l.paused_when_hidden || {}; return `| ${NAMES[c]} | ${f.renders_in_1_5s} (loop ${f.running ? 'running' : 'stopped'}) | ${l.renders_in_1_5s_back_in_story} | ${h.renders_in_1_5s} (loop ${h.running ? 'running' : 'stopped'}) | ${l.renders_in_1_5s_when_shown_again} |`; };
m += `\n### Pausing (checked by the same script, \`node tools/measure.mjs pause\`)\nThe stage is fixed behind the page, so it only goes offscreen when the full-screen closing footer covers it; the loop also stops when the tab is hidden (the check flips \`document.hidden\` and fires \`visibilitychange\`, as switching tabs does). Renders counted by three.js's own frame counter over 1.5 s on the laptop page:\n\n| | Footer covering the stage | Back in the story | Tab hidden | Tab shown again |\n|---|---|---|---|---|\n${['a', 'b', 'c'].map(pz).join('\n')}\n`;

let md = readFileSync(join(root, 'README.md'), 'utf8');
const put = (tag, body) => { const re = new RegExp(`<!-- ${tag} -->[\\s\\S]*?<!-- /${tag} -->|<!-- ${tag} -->`); md = md.replace(re, `<!-- ${tag} -->\n${body}\n<!-- /${tag} -->`); };
put('GALLERY', g); put('MEASURED', m);
writeFileSync(join(root, 'README.md'), md);
console.log('README filled');
