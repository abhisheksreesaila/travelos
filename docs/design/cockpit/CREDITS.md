# Credits

## Code and libraries
- **three.js r187** (MIT, © 2010–2025 three.js authors). A tree-shaken copy is bundled into `core/diorama.js` by `tools/build.mjs` from the npm package `three@0.187.0`; the licence header is kept inline in the bundle. Direction 1 only.
- **MapLibre GL JS 5.24.0** (BSD-3-Clause). Loaded at run time from jsDelivr by `core/mapl.js`, not vendored. Direction 2 only.
- **Lucide** (ISC). Icons are drawn in Lucide's style (24 grid, 2 px round strokes): the reskin's set plus new weather, road and snow icons in `core/icons.js`.
- **Geist** and **Geist Mono** (SIL OFL 1.1), in `assets/` with their licence alongside.

## Map and weather data
- **OpenStreetMap** (ODbL, © OpenStreetMap contributors): the lake outlines (Nominatim polygons), the main roads (Overpass API) and the places in `data/geo.js`, fetched once by `tools/fetch_geo.py`.
- **OSRM** (the demo router at router.project-osrm.org, OpenStreetMap data): every route line and drive time in `data/geo.js`. Its usage note restricts the demo server to "reasonable, non-commercial use-cases"; see the README.
- **AWS Terrain Tiles** (Mapzen / Tilezen Joerd, terrarium encoding), on the AWS Open Data registry: the elevation grid in `data/dem.js`, the relief in `img/relief-*.webp`, and Direction 2's hillshade at run time. Attribution follows [tilezen/joerd docs/attribution.md](https://github.com/tilezen/joerd/blob/master/docs/attribution.md) (sources include USGS 3DEP/NED, NASA SRTM, GMTED2010 and ETOPO1).
- **OpenFreeMap** (free public instance; © OpenMapTiles, © OpenStreetMap contributors): Direction 2's vector tiles and its starting styles (Positron, Dark), restyled in `core/mapl.js`. MapLibre shows the attribution automatically.
- Weather in the artboards is **sample data** labelled with its proposed source (MET Norway, CC BY 4.0). Prices, confirmation numbers, carrier times and the family chat are sample data too.

## Meng To's agent skills (MIT, © 2026 Meng To)
Read from `~/.cache/mengto-skills-src/src/agent-skills/`. What was adapted, and where:
- **`web-design/threejs-weather`**: three ideas, used in the living weather widget (`core/wx.js`) and the diorama's snow (`src/diorama.js`): *density is a draw range* over one preallocated pool, so a day's weather never reallocates; *falling snow and settled snow are two variables*, so the snow bank in the widget grows while it snows and is still there on Wednesday's sunny powder day; and *wind is a slow envelope*, so Thursday's gusts build and ease instead of blowing at one rate.
- **`web-design/falling-leaves`** and **`3d/3d-falling-leaves`**: vary every parameter per particle (size, speed, sway phase) so the eye can't find a common rhythm, and recycle particles across the view instead of letting them run out.
- **`web-design/threejs-landscape`**: colour the ground by what it is doing (height and slope) instead of a texture, and scatter everything from the same height function: the diorama's valley, snow and rock faces and its tree stands.
- **`3d/3d-four-seasons`** and **`3d/3d-sky-background`**: continuous weights for light instead of hard switches, and snow that lies by elevation and exposure: the diorama's winter colouring and its dark mode as night with the towns lit.
- **ThreeUI** (MengTo/threeui, MIT), via the story3d prototypes: the render-loop lifecycle in `src/diorama.js` (pause off screen and in hidden tabs, one still frame under reduced motion, pixel ratio capped at 2).
- **`ui/design-first-ui-prompting`**: "lock one system, vary one variable": all three directions share Direction A's tokens, the same content and the same honest states, and differ only in what the trip lives on.
- Read but not adopted: **`web-design/beautiful-shadows`** and **`web-design/css-border-gradient`** (omxqua keeps its one shadow scale and no gradient edges), **`web-design/globe-gl`** (a globe adds nothing to a 60-mile trip; the story3d prototypes already cover a globe opener).

> MIT License · Copyright (c) 2026 Meng To · Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

Everything else (the layouts, the diorama scene, the paper map, the weather engine, the stamp and the paste moment) is original to these artboards.
