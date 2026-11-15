# liquid: a design kit for calm, springy sites

GitAway's v2 look, extracted: a sky behind everything, near-opaque cards, one frosted-glass widget at a time, ink plus one brand hue, springs on every press and every opening.
Plain CSS and JavaScript, no build, no dependencies, no framework. Open `index.html` (from disk) to see every piece in light and dark, phone and laptop; `shots/` has pictures.

## Drop it into an fh-saas (or any) app
1. Copy this folder (`liquid.css`, `liquid.js`, `liquid.py`, `fonts/`) to your static folder and serve it at, say, `/liquid`.
2. In your page: `<body class="lq">`, `<link rel="stylesheet" href="/liquid/liquid.css">`, `<script src="/liquid/liquid.js" defer>`, and this in the head so a remembered dark mode never flashes light:
   `<script>try{var m=localStorage.getItem('lq-mode')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.setAttribute('data-mode',m)}catch(e){}</script>`
3. Put `<div class="lq-sky" data-mood="shore" aria-hidden="true"></div>` first in the body (`liquid.js` draws its sun, moon, clouds and the mood's one object).
4. With FastHTML: `from liquid import page_shell, sky, top_bar, sheet, glass_card, card`; `page_shell(top_bar(...), Main(...), title=..., mood="hills")` returns a whole page (see `liquid.py`'s docstring).

Pieces (all in `index.html`): `.lq-card`, `.lq-glass`, `.lq-btn` (+ `is-ink`, `is-soft`), `.lq-chip`, `.lq-kind.k1..k5`, `.lq-round`, `.lq-top` with `.lq-sections` and `.lq-account`/`.lq-menu`,
`.lq-sheet` (+ `is-drawer`, opened by `data-lq-sheet="id"`), `.lq-folds > .lq-fold` (one open at a time), `.lq-box` search with `.lq-list`, `Lq.toast(text, {undo})`, `.lq-skel`.
Moods: `shore`, `snow`, `hills`, `party`, `city`, plus the quiet sky (`.is-quiet`). `Lq.sky.set('snow')`, `Lq.mode.toggle()`.

## The brand: change one block
At the top of `liquid.css`, the block "1. BRAND": `--lq-brand` (buttons, current section, selected), `--lq-brand-text` (the same hue as text, a little deeper), `--lq-brand-tint` and `--lq-brand-ink`,
and the same four in the `[data-mode="dark"]` block just below (lighter text, a deep tint). The five kinds (`--lq-k1..k5`, each solid, tint, ink) are for categories only. Nothing else holds a hue.
Check a new hue: white on `--lq-brand` and `--lq-brand-text` on the sky and on a card must both be 4.5:1 or better, in light and dark.

## The rules
- Glass (`.lq-glass`) only directly over the sky, for one small widget: a pill, a menu, a list. Never over a card, never under a paragraph. Text goes on near-opaque cards.
- A quiet sky (`is-quiet`) behind anything people read. Playful moods only where you glance (a landing, a search).
- Kind colours only for kinds of thing. Never for decoration, never for a day or a row.
- Every word 4.5:1, in light and dark, over every sky: `tests_browser/test_kit_liquid.py` measures the painted pixels of the gallery. Do the same for your pages.
- Targets are 48px (`--lq-target`); text never under 16px, a label never under 13px.
- Durations and curves only from the `--lq-t-*` and `--lq-spring*` tokens, in CSS and in script. Reduced motion: nothing moves and nothing fades.
- A press is the `scale` property (never a transform), so it never fights a hover lift. A component must not press by its own transform.
- On a phone anything that opens grows out of what was tapped; from 1020px up (`--lq-calm-min`) it is a short fade, no zoom.
- The page colour is on `<html>`; keep `body` and wrappers transparent, or they paint over the fixed sky.

## Fonts
Newsreader (display) and Inter (everything you read, tabular figures for numbers), self-hosted in `fonts/` as variable woff2. Both are SIL Open Font License 1.1, which allows
self-hosting and redistribution with the licence text (`fonts/LICENSE-*.txt`, kept beside them). To use Google Fonts instead, delete the two `@font-face` rules and link
`https://fonts.googleapis.com/css2?family=Inter:wght@100..900&family=Newsreader:opsz,wght@6..72,200..800&display=swap`.

## Browser support
Needs `:has()`, `color-mix()`, the individual `scale`/`translate`/`rotate` properties, `linear()` easing and `backdrop-filter`: any browser from 2024 on.
