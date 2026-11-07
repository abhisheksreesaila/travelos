# The cover's 3D world (F-206)

The signed-out landing at `/` is a scroll story through the real Lake Tahoe in December: concept A of `docs/design/cover3d/` (one continuous fly-through) with concept B's fork tree as its last chapter, opening on "Don't read about it. Go." and closing on "Take a trip. Leave a trail." (`docs/briefs/free-and-polished.md`, "The line"). Every word is real DOM text (`gitaway/pages/cover.py`, `assets/css/cover.css`); the world behind it is decoration (`aria-hidden`). A signed-in person keeps the old landing (`gitaway/pages/home.py`).

## What a visitor gets
- **At once:** the poster (chapter 0's still, 10 KB), chosen for day or night and phone or laptop by a `<picture>` before any script runs. A tiny inline script (`assets/js/cover_boot.js`) sets day or night and live or still before the first paint.
- **The live world** only when it is wanted: `assets/js/cover.js` fetches three.js, `assets/js/cover/world.js` and the terrain only if there is no reduced motion, WebGL works, ES modules and `DecompressionStream` exist, the device is not weak (2 GB or 2 cores or fewer), and there is no Save-Data or 2G. Until the world's first frame, the poster and (if you scroll) the stills keep the page full.
- **The calm stills** otherwise: one WebP per chapter, loaded one at a time with the next one ahead.
- **Quality tiers:** a laptop gets `high` (the 60 m ground, the planar mirror on the lake, 2048 soft shadows, up to 2x pixels on a retina screen), a strong phone `mid` (the 120 m ground, 1024 shadows, 1.5x), any other phone `low` (no shadows, fewer trees, 1.25x). The governor (`src/core.js` `Governor`) then lowers the pixel ratio while frames take longer than 23 ms, to 0.55 at worst, and gives up for the stills after three windows over 45 ms at that floor.
- **Pausing:** the render loop stops when the closing screen covers the stage and when the tab is hidden.
- **Day and night** follow the site: an explicit `data-theme`, `data-mode` or `data-color-scheme` of `dark` or `light` (or a `dark`/`light` class) on `<html>` or `<body>`, else the system setting. F-200's switch only has to set one of those (`cvMode()` in `cover_boot.js`).
- **Layouts:** a laptop puts the card beside the world; phones, portrait tablets and short screens (a phone on its side, any window under 520 px tall) put the world on top and the card below (`cover.py` `PHONE_Q`, used verbatim by `cover.css`, `cover.js` and the poster's `<picture>`). A card never runs under the header or off the screen; only on a screen shorter than any of these does it scroll inside itself. Sides keep clear of a notch (`env(safe-area-inset-*)`).
- **A screen reader** reads the plan's widgets from the card even when the world draws them (the card's copy is visually hidden then; the world's copies are `aria-hidden`).
- **Production** ignores the tools' URL switches (`?measure`, `?capture`, `?q`, `?cam`) and the world keeps `window.__cover`, `__frames` and `__work` to itself: both need `data-debug="1"` on `<main>`, which `cover.py` renders only off production.

## The place is real
`tools/bake_tahoe.py` turns what the trip cockpit fetched once (`docs/design/cockpit/tools/fetch_geo.py`, raw responses in `~/.cache/cockpit-geo-raw`) into `assets/cover/`:

| File | What | Size |
|---|---|---|
| `tahoe-hi.bin.gz` | the ground at 60 m (650 x 907) in 0.5 m steps, delta-coded; the signed distance to the shore of Lake Tahoe and Fallen Leaf Lake at 30 m | 334.5 KB |
| `tahoe-lo.bin.gz` | the same at 120 m and 60 m, for phones | 117.5 KB |
| `tahoe-geo.json.gz` | places, the story's trails, roads, towns, lake outlines, in metres | 26.1 KB |

World space is metres, x east and z south of the pier at the end of Ski Run Boulevard, y up from the lake's surface; heights are drawn 1.55 times taller (`data.js` `EXAG`) so the bowl reads from the air. Lena and Sam's five days run along the real roads (Dijkstra over OpenStreetMap's US 50, CA 89, CA 28 and SR 28), your trail is the real 18-minute OSRM drive from the cabin to Taylor Creek's sled hill, the arrival is the real drive in from Reno over Spooner Summit. Lakes, roads and places: © OpenStreetMap contributors (ODbL), credited in the cover's footer. Elevation: AWS Terrain Tiles (USGS 3DEP and others).

## How it is drawn (`src/`)
- `terrain.js`: a CDLOD quadtree of tiles sharing one grid, heights read from the elevation texture in the vertex shader and morphed toward the coarser grid with distance, so the ground is fine at every chapter for a few hundred thousand triangles; coloured by slope, height and the forest rule (snow, granite, canopy, wet shore, the lake floor); per-pixel normals, snow-crust detail near the camera, ridge shadows marched toward a low sun, three's shadow map for the trees and the cabin, haze into the sky.
- `water.js`: Tahoe's turquoise shallows over sand turning to cobalt, ripple normals from analytic derivatives with each wave faded at its pixel footprint, wind streaks, Schlick Fresnel against the shared sky (or the planar mirror on `high`), glitter, a lapping line at the shore.
- `sky.js`: one sky function for the dome, the water's reflection and the haze; real December sun positions (22 degrees in the early afternoon, setting west-southwest just left of Mt Tallac from the pier), golden hour, crepuscular rays near a low sun, cirrus, the moon, stars in the band the camera sees.
- `forest.js`: crafted firs (star-shaped drooping skirts, smooth normals) and Jeffrey pines (clumped crowns) round the cabin, the pier and the next cabin, light firs on the rest of the south shore, snow on whatever faces up, wind in the vertex shader, granite boulders, Heavenly's ski runs cleared.
- `props.js` and `wood.js`: the chalet (board-by-board cedar, stone base, rounded stones in the chimney, a snow cap and icicles, warm windows at night, smoke), the pier (every plank its own grain, pilings with a wet band), the family's SUV, the family (lathe-turned parkas, beanies, scarves, a rim of sunset light), houses along the real roads with lit windows at night, Heavenly's gondola, roads; procedural timber after Meng To's wood material.
- `fx.js` and `book.js`: trails and pins at a constant size on screen, snow round the lens, the thank-you sparkle, postcards rendered from the world, the guidebook whose map page is the real lake.
- `scene.js` and `main.js`: one renderer (WebGL2, logarithmic depth, ACES), the loop, the governor, the camera rig per chapter and layout, the DOM anchors (labels, the plan's widgets with leaders), the story.

## Build, bake, capture, measure
Everything runs from the repo root against the dev server (any port; the tools default to 6206):

```
(cd cover3d && npm ci --ignore-scripts)                 # once: exactly three@0.187.0 and esbuild@0.28.2 from the lock, no install scripts (.npmrc says so too)
node cover3d/build.mjs                                  # three.js tree-shaken + the world; writes cover3d/sizes.json (or COVER3D_MODULES=<a node_modules with the pinned two>)
pixi run python -I cover3d/tools/bake_tahoe.py          # the terrain and vectors (needs ~/.cache/cockpit-geo-raw; ~3 min); then build again, the world carries the data's hashes
pixi run python -I cover3d/tools/capture.py stills og   # the stills, the poster and the share image, from the live world on this machine's GPU
pixi run python -I cover3d/tools/capture.py report closeups video   # docs/report/f206-*
pixi run python -I cover3d/tools/measure.py             # frame rate, cover3d/fps.json
pixi run python scripts/cover_size.py                   # what the landing downloads
```
`COVER3D_DEV=1 node cover3d/build.mjs` builds an unminified world with a source map for debugging; `tests/test_cover_budget.py` refuses it, and refuses a world older than its sources (the bundle's banner carries a hash of `src/`). The build refuses any esbuild but the pinned one and looks for its tools nowhere but `cover3d/node_modules` (or `COVER3D_MODULES`). Every URL the world fetches carries its file's content hash (three.js's import specifier, the terrain files), since the service worker keeps `?v=` files for good; `cover.py` preloads the same three.js URL. The bake writes gzip with no timestamp, so the same data bakes to the same bytes (and the same hashes). Capture and measure use Playwright's own full Chromium (`channel="chromium"`) on this machine's GPU, or `COVER3D_CHROME=<path>`. The bake needs numpy, which the pixi environment has only through another package; `pixi add numpy` if that ever changes.

## Measured (2026-11-07)
**JavaScript the landing downloads, gzip -9** (Cloudflare compresses in front of gitaway.me): three.js 139.3 KB, the world 41.7 KB, `cover.js` 5.4 KB, the inline boot 0.7 KB, the site's own scripts 15.8 KB, and FastHTML's four jsDelivr scripts 42.3 KB (htmx, fasthtml-js, surreal, css-scope-inline; F-207 switches them off site-wide): **245.1 KB of the 250 KB budget**, about 203 KB once F-207 lands (`tests/test_cover_budget.py` prints the exact figure; a script from another site that nobody has measured fails it). The world downloads 361 KB of data on a laptop and 144 KB on a phone, far under the 2 MB allowed: the detail is generated on the device (a GPU-baked noise field, a GPU-baked wood field, crafted geometry in code), not downloaded.

**Frame rate** (`tools/measure.py`, one scripted 24 s scroll through the story, governor off unless noted; numbers from `fps.json`):

| Run | Mean fps | p95 frame | Frames over 33 ms | Draw calls max | Triangles max |
|---|---|---|---|---|---|
| Laptop 1440, this machine's GPU (RTX 3090, Vulkan), `high` | 58.1 | 16.8 ms | 0.6% | 59 | 1.28 M |
| Phone 390 at DPR 3, CPU throttled 4x, GPU, `mid` | 56.0 | 16.8 ms | 0.9% | 72 | 515 k |
| Same phone on SwiftShader (software GL, a weak GPU's stand-in) | 5.0 | 683 ms | 86% | 66 | 515 k |
| Same, governor on (what a visitor gets) | steps to 0.55x, then switches to the stills | | | | |

What this does and does not prove: the laptop holds 60 fps through the whole story; a phone-class CPU is not the limit; a weak GPU cannot draw this world and gets the calm stills after a few seconds (and a 2 GB or 2-core phone never downloads it). This machine's GPU is far faster than any phone's, so **the next check is the founder's own phone**.

## Rough edges
- No real phone yet (above).
- The ground is the 60 m elevation: right for the bowl and the far mountains, smooth at the cabin's feet (snow covers it, and the crust detail helps).
- The family are figures, not people: true size and crafted, but their faces are a sphere.
- The fork tree is a diagram drawn over the lake, on purpose: the story's last word, not a place.
- Phone views compose the world in the top part of the screen; on a phone on its side that part is a strip above the card, and on very wide windows a label can sit near an edge.
- A 320 px tall screen (the first iPhone SE on its side) is shorter than any layout plans for: four of its cards scroll inside themselves. Every other size measured fits whole (`tests_browser/test_cover.py` checks 844x390, 1366x768 and 320x568, live and still).

## Report
Screens of the real page, 1440 and 390, day and night: `docs/report/f206-<width>-<light|dark>-<chapter>.jpg`. Close-ups for judging the detail: `f206-closeup-cabin.jpg`, `-cabin-night`, `-trees-snow`, `-pier-sunset`, `-pier-night`, `-family-and-deck`, `-water`, `-emerald-bay`. A scroll-through: `f206-scroll-1280.mp4` (recorded before the review fixes: chapter 1's card has since gained the line that the families are made up).

Credits: [CREDITS.md](CREDITS.md).
