# Credits

- **three.js r187** (MIT, © 2010–2025 three.js authors). A tree-shaken copy is bundled into `dist/diorama.js`, `dist/postcards.js` and `dist/globe.js` by `build.mjs` from the npm package `three@0.187.0`; the licence header is kept inline in each bundle.
- **ThreeUI Community** by Meng To (MIT, © 2026 Meng To, https://github.com/MengTo/threeui). Adapted: the render-loop lifecycle from `src/shaders/gallery/Gallery.tsx` (pause when the canvas leaves the screen or the tab is hidden, render a single frame under reduced motion, cap the pixel ratio at 2), in `src/core.js` `createStage`. Taken as an idea only: Gallery's curved, floating image panels, which led to the postcards along a path. No ThreeUI assets, shaders or fonts are copied.

  > MIT License · Copyright (c) 2026 Meng To · Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

- **Geist** and **Caveat** fonts (SIL OFL 1.1), loaded from `../reskin/assets/` with their licences alongside.
- **Photos**: two CC0 area photos (Santa Monica pier by Andrek02, Venice Beach by Blake Everett; see `assets/photos/CREDITS.md` in the app), downscaled into `dist/photos.js`. They show the area, never a hotel or room.
- **Icons**: drawn in Lucide's style (ISC), as in the reskin.
- Everything else (the scenes, props, illustrations, the continents on the globe, the page) is original to this prototype. The trip, people, forks and prices are sample data.
