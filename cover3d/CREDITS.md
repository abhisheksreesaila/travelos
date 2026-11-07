# Credits (the cover's 3D world, F-206)

## Code
- **three.js r187** (MIT, © 2010–2026 three.js authors), from the npm package `three@0.187.0`, tree-shaken by `build.mjs` into `assets/vendor/three-0.187.0/three.cover.min.js`; its licence is `assets/vendor/three-0.187.0/LICENSE` and stays inline at the top of the file. Built with **esbuild 0.28.2** (MIT).
- **The cover prototype** in this repo (`docs/design/cover3d/`, concept A with concept B's fork tree): the page conductor (`assets/js/cover.js` from its `page.js`), the scroll state, the camera rig, the governor, the guidebook (`book.js`), trails, pins, snow, the sparkle and postcards (`fx.js`), the story's chapter logic (`main.js`), the noise and spring helpers (`core.js`). Its own credits (`docs/design/cover3d/CREDITS.md`) carry over: Meng To's build-threejs-scroll-worlds, scroll-world-storytelling, cinematic-scroll-storytelling, threejs-landscape, 3d-sky-background, 3d-ultra-realistic-water and the story3d prototype (itself after Meng To's ThreeUI Gallery, MIT).
- **CDLOD** (continuous distance-dependent level of detail) is Filip Strugar's published method (2010); `terrain.js` is our own implementation of the idea.

## Meng To's agent skills (MIT, © Meng To; read from `~/.cache/mengto-skills-src`, nothing copied wholesale)
His MIT notice ships with the code adapted from them: `LICENSE-mengto` here, and in full at the top of `assets/js/cover/world.js` (written in by `build.mjs`) and `assets/js/cover.js`.

| Skill | What it gave the world, and where |
|---|---|
| `3d/3d-ultra-realistic-water` | the lake: per-pixel ripple normals from analytic derivatives, each wave faded at its own pixel footprint; Schlick Fresnel with F0 0.02; the reflection clamped above the horizon; glitter terms; haze into the sky's own horizon colour; a planar reflection of what stands in the water (`water.js`) |
| `3d/3d-sky-background` | one sky function shared by the dome, the water and the haze; one sun direction for the disc, the glow and the light; continuous day, dusk and night states; stars faded in after dark (`sky.js`) |
| `3d/3d-sky-rays` | the low sun's rays. Its screen-space occlusion pass is a full-screen cost a phone cannot spare, so the rays are drawn into the sky round a low sun, where the ridges and trees in front occlude them (`sky.js`); the pass itself is a possible laptop-only addition |
| `3d/3d-high-poly-models` | proportions first, then a rounded arris on every edge, curve segments where the camera looks, detail split into silhouette, form and micro detail, instancing and distance-based sets instead of one dense mesh, shadows only from what is near (`props.js`, `forest.js`) |
| `3d/3d-wood-material` | the timber: one periodic noise field baked on the GPU, read at several stretches and scales for rings with per-ring latewood, pores, fibres, rays and end-grain cells; roughness that moves with the grain; a clamped derivative bump; every layer faded by its footprint; a seed and grain axis per board (`wood.js`) |
| `3d/3d-high-resolution-textures` | detail generated on the device instead of downloaded (the baked noise and wood fields, mipmapped, in data colour space), progressive delivery (the poster, then the world, then the terrain only at the tier the device can hold) |
| `3d/3d-retina-resolution` | an explicit pixel-ratio cap per tier (2x on a laptop's retina screen, 1.5x and 1.25x on phones), one place that sizes the renderer, measured fallbacks that step down with hysteresis |
| `web-design/threejs-landscape` | ground coloured by slope, height and what grows there, never a tiled texture; instanced trees with variation and wind in the vertex shader; scattered boulders from the same height function; stars in the band the camera sees; time of day as interpolated states (`terrain.js`, `forest.js`, `sky.js`) |
| `game-development/optimize-threejs-games` | measuring one repeatable path with draw calls and triangles (`tools/measure.py`), reusing geometry and materials, culling what is far, keeping quality settings explicit and reversible |

## Data
- **Elevation:** AWS Terrain Tiles (Mapzen terrarium encoding; sources include USGS 3DEP/NED and SRTM), fetched once by the trip cockpit's `docs/design/cockpit/tools/fetch_geo.py`.
- **Lakes, roads and places:** © OpenStreetMap contributors, available under the Open Database License (ODbL), via Nominatim and the Overpass API (same fetch). The cover's footer credits them, linked to https://www.openstreetmap.org/copyright as OSM's attribution guidelines ask; `tahoe-geo.json.gz` carries the same credit (docs/decisions.md).
- **Drives:** the OSRM demo router on OpenStreetMap data (same fetch).

## Everything else
The cabin, the pier, the SUV, the family, the trees, the guidebook and the story are original. The places are real; the families, their trips, forks and bookings are made up, and the page says so.
