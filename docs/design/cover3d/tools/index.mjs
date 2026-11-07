// Writes index.html, the page to open first: the three concepts with their measured numbers (from
// dist/sizes.json and tools/fps.json). Run after build.mjs and measure.mjs: node tools/index.mjs
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const sizes = JSON.parse(readFileSync(join(root, 'dist/sizes.json'), 'utf8'));
const fps = existsSync(join(root, 'tools/fps.json')) ? JSON.parse(readFileSync(join(root, 'tools/fps.json'), 'utf8')) : {};
const kb = (n) => (n / 1024).toFixed(0);
const f = (k) => (fps[k] ? `${fps[k].fps} fps · p95 ${fps[k].p95_ms} ms` : 'not measured');
const C = [
  { id: 'a', name: 'A · One continuous fly-through', still: 'a-1-wide', line: 'The guidebook’s map rises into Lake Tahoe and one camera flies the story: the shared trip draws itself around the lake, the fork branches at the cabin and a car drives it, the plan’s widgets stamp into the world while it snows, the sun sets on the pier, postcards fly to the next family.', tag: 'Recommended' },
  { id: 'b', name: 'B · One place, four seasons', still: 'b-2-wide', line: 'One tripod above Emerald Bay. Each chapter is another family’s trip in another season (winter, a spring fork of it, a summer plan, fall gold with falling leaves), the next winter shares it on, and every trip rises into a fork tree.', tag: 'Concept' },
  { id: 'c', name: 'C · The road trip (wildcard)', still: 'c-1-wide', line: 'Scroll is the accelerator. A chase camera rides behind the family’s car, the shared trip glows on the road like a route, the fork is a real fork in the road, the widgets stamp onto the glass, and the photos fly down the valley to the next car.', tag: 'Wildcard' },
];
const card = (c) => `
    <article class="pc">
      <a href="${c.id}.html" class="shot"><img src="stills/${c.still}-light.webp" alt="" loading="lazy"><img class="dk" src="stills/${c.still}-dark.webp" alt="" loading="lazy"></a>
      <div class="pc-b">
        <p class="eyebrow"><i></i>${c.tag || 'Concept'}</p>
        <h2>${c.name}</h2>
        <p>${c.line}</p>
        <dl>
          <div><dt>JavaScript</dt><dd>${kb(sizes[c.id].totalGz)} KB gzip</dd></div>
          <div><dt>Phone, CPU 4×, GPU</dt><dd>${f(`${c.id}/phone-390-cpu4x/gpu`)}</dd></div>
          <div><dt>Phone, CPU 4×, software GL</dt><dd>${f(`${c.id}/phone-390-cpu4x/swiftshader`)}</dd></div>
        </dl>
        <div class="row"><a class="btn fill" href="${c.id}.html">Open ${c.id.toUpperCase()}</a><a class="btn tonal" href="${c.id}.html?mode=dark">Night scene</a><a class="btn text" href="${c.id}.html?still">Calm still version</a></div>
        <p class="mp"><a href="motion/${c.id}.mp4">Scroll-through video</a></p>
      </div>
    </article>`;
const html = `<!doctype html>
<html lang="en" class="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitAway · Cover page · three 3D scroll worlds</title>
<link rel="stylesheet" href="fonts.css"><link rel="stylesheet" href="cover.css">
<script>if (matchMedia('(prefers-color-scheme: dark)').matches) document.documentElement.className = 'dark';</script>
<style>
  body { background: var(--bg); }
  .idx { max-width: 1240px; margin: 0 auto; padding: 40px 20px 72px; display: grid; gap: 22px; }
  .idx h1 { font: 760 clamp(44px, 6.4vw, 84px)/0.95 var(--font); letter-spacing: -.055em; margin: 8px 0 0; text-wrap: balance; }
  .idx h1 em { font-style: normal; color: var(--ink2); }
  .idx > p { font-size: 18px; color: var(--ink2); max-width: 64ch; margin: 0; }
  .cards { display: grid; gap: 18px; }
  .pc { background: var(--s1); border-radius: 28px; box-shadow: var(--sh2); overflow: hidden; display: grid; grid-template-rows: auto 1fr; min-width: 0; }
  .pc .shot { display: block; aspect-ratio: 16 / 10; background: var(--line); }
  .pc img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .pc img.dk, .dark .pc img:not(.dk) { display: none; } .dark .pc img.dk { display: block; }
  .pc-b { padding: 20px 22px 22px; display: grid; gap: 10px; align-content: start; }
  .pc h2 { font: 720 26px/1.1 var(--font); letter-spacing: -.03em; margin: 0; }
  .pc p { margin: 0; color: var(--ink2); font-size: 16px; }
  dl { margin: 4px 0 0; display: grid; gap: 4px; }
  dl div { display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid var(--line); padding-top: 6px; font-size: 15px; }
  dt { color: var(--ink2); } dd { margin: 0; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; min-width: 0; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
  .mp a { font-weight: 600; color: var(--ink); }
  .how { background: var(--s1); border-radius: 22px; box-shadow: var(--sh1); padding: 18px 22px; }
  .how h3 { margin: 0 0 8px; font: 700 18px/1.2 var(--font); }
  .how ul { margin: 0; padding-left: 20px; color: var(--ink2); font-size: 16px; display: grid; gap: 4px; }
  .how code { font: 500 14px ui-monospace, monospace; color: var(--ink); }
  @media (min-width: 1020px) { .cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
</head>
<body>
<main class="idx">
  <p class="eyebrow"><i></i>Prototype · ${new Date().toISOString().slice(0, 10)} · Direction A · design only</p>
  <h1>Forget the book. <em>Go travel.</em></h1>
  <p>Three ways to tell GitAway’s cover page as one 3D world you scroll through: Lake Tahoe in December, the captain’s own trip. A guidebook opens it, then the story: a family shared their trip, you fork it, plan it together, go, and share it back. Every page works from disk, on a phone, in light (day) and dark (night), and as a calm still version with the same words.</p>
  <section class="cards">${C.map(card).join('')}
  </section>
  <section class="how">
    <h3>How to review</h3>
    <ul>
      <li>Scroll slowly; each card stays pinned while its chapter plays in the world, then the camera moves on. Scrolling back replays it backwards.</li>
      <li>The moon or sun button switches night and day. <code>Shift</code> + <code>←</code>/<code>→</code> (or the dark pill at the bottom right) switches concepts.</li>
      <li><code>?still</code> shows the calm version (what reduced motion, no WebGL or a weak phone get). <code>?shot=3</code> jumps to a chapter.</li>
      <li>Numbers, what came from which Meng To skill, and the recommendation: <a href="README.md"><b>README.md</b></a>.</li>
    </ul>
  </section>
</main>
</body>
</html>
`;
writeFileSync(join(root, 'index.html'), html);
console.log('wrote index.html');
