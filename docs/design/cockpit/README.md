# Trip cockpit: three directions

Design artifacts for GitAway's trip and booking screens, under the approved brief [free-and-polished](../../briefs/free-and-polished.md). No app code changed. The template trip is the founder's family to Lake Tahoe, Sat Dec 19 to Sat Dec 26 2026: SFO to Reno, 2 adults and kids 8 and 11, a cabin in South Lake Tahoe, an SUV with snow chains, snowshoeing, a snowmobile tour and ski lessons bought direct. The cockpit's "now" is Monday Dec 21, 9:12 AM, a snow day.

**Open from disk, no server:** [`index.html`](index.html) shows the three side by side with a pick box per screen and device (your picks stay in the browser). Each direction page is live, with every screen at phone (390) and desktop (1440) and a Light/Dark switch: [`1-diorama.html`](1-diorama.html), [`2-widgets.html`](2-widgets.html), [`3-ticket.html`](3-ticket.html). Tap a day, drag a map, press "Read it" on a pasted confirmation. One artboard at real size: `3-ticket.html?bare=1&screen=cockpit&size=dk&mode=dark` (screens `cockpit book day paste`; `&day=0`…`7`; for paste `&phase=open|read|landed|play`). Direction 2 needs a connection for its map tiles. PNGs are in [`png/`](png), named `<direction>-<screen>[-phase]-<width>-<mode>[-full].png`.

## Recommendation
**Build Direction 3, Ticket line.** It shows the whole week and its times at a glance, carries B's ticket stub to its natural end so it looks like no booking site, and its map costs about 3 KB of script plus about 115 KB of data per trip, so it still works in a cabin with one bar of signal. Take Direction 1's diorama for the shared-trip 3D story, where the brief already budgets three.js, and keep Direction 2's real map (MapLibre with OpenFreeMap) as an on-demand street map that loads only when someone taps for it.

## The three directions, side by side

| | **1 · Diorama** | **2 · Widget board** | **3 · Ticket line** |
|---|---|---|---|
| Idea | The trip lives on a little 3D toy of the real Tahoe basin | The trip as a phone home screen of widgets | The week as one line of ticket stubs |
| The map | three.js toy tile built from real elevation; the day's route draws itself and the family's green SUV drives it | A real map, tilted and shaded, that flies to each day | A paper map tilted in CSS 3D; place labels stand up like a pop-up book |
| Weather | Living widget in the rail, and the same weather in the scene: snow falls on the model, night in dark mode with the towns lit | Living widget; the day view adds snow by the hour | One living widget per day stub: eight small skies across the week |
| Focal card | Up next with the next leg turn by turn (ink) | Up next with the next leg (ink, tall) | Today's stub, open and inverse ink: Up next and the next leg |
| Bookings | Four solid kind widgets under the stage | Four solid kind widgets along the bottom row | Passes in a wallet, each with a perforation |
| Book this trip | Lanes beside the model; callouts with leader lines tie each lane to its pin | The same board: wide flights widget, one widget per lane, the checklist ticket down the right, a "Bring a booking home" widget, a ride estimate | A book of tickets: one ticket per lane, the honest action on its stub |
| A pasted booking lands | The card flies into the cabin's pin, the pin pops, the lane is stamped | The card flies into the Stay widget, the stamp lands | The Stay ticket is stamped; a stub drops into the checklist |
| Best at | Delight, a sense of place, why chains matter (you can see the passes) | Reading at a glance; a real, zoomable map for any destination | The whole week and its times at once; light and works offline |
| Weak at | Heaviest; a second 3D engine; no street level | Heaviest network use; plain "dashboard" feel; needs a connection for the map | No street level (hands off to Google or Apple Maps); one relief image per trip region |

| Cockpit, desktop | 1 · Diorama | 2 · Widget board | 3 · Ticket line |
|---|---|---|---|
| Light | ![](png/1-cockpit-1440-light.png) | ![](png/2-cockpit-1440-light.png) | ![](png/3-cockpit-1440-light.png) |
| Dark | ![](png/1-cockpit-1440-dark.png) | ![](png/2-cockpit-1440-dark.png) | ![](png/3-cockpit-1440-dark.png) |
| Arrival day (the long drive from Reno) | ![](png/1-cockpit-arrive-1440-light.png) | ![](png/2-cockpit-arrive-1440-light.png) | ![](png/3-cockpit-arrive-1440-light.png) |

| Phone | 1 · cockpit | 1 · day | 2 · cockpit | 2 · day | 3 · cockpit | 3 · day |
|---|---|---|---|---|---|---|
| Light | ![](png/1-cockpit-390-light.png) | ![](png/1-day-390-light.png) | ![](png/2-cockpit-390-light.png) | ![](png/2-day-390-light.png) | ![](png/3-cockpit-390-light.png) | ![](png/3-day-390-light.png) |
| Dark | ![](png/1-cockpit-390-dark.png) | ![](png/1-day-390-dark.png) | ![](png/2-cockpit-390-dark.png) | ![](png/2-day-390-dark.png) | ![](png/3-cockpit-390-dark.png) | ![](png/3-day-390-dark.png) |

Full-length phone captures (the screens scroll) end in `-full.png`; Direction 1's phone cockpit is one fixed screen with a sheet that drags up.

| Book this trip, desktop | 1 · Diorama | 2 · Widget board | 3 · Ticket line |
|---|---|---|---|
| Light | ![](png/1-book-1440-light.png) | ![](png/2-book-1440-light.png) | ![](png/3-book-1440-light.png) |
| Dark | ![](png/1-book-1440-dark.png) | ![](png/2-book-1440-dark.png) | ![](png/3-book-1440-dark.png) |

| The paste moment | Phone: pasted | Phone: read | Phone: landed | Desktop: landed |
|---|---|---|---|---|
| 1 · Diorama | ![](png/1-paste-open-390-light.png) | ![](png/1-paste-read-390-light.png) | ![](png/1-paste-landed-390-light.png) | ![](png/1-paste-landed-1440-light.png) |
| 2 · Widget board | ![](png/2-paste-open-390-light.png) | ![](png/2-paste-read-390-light.png) | ![](png/2-paste-landed-390-light.png) | ![](png/2-paste-landed-1440-light.png) |
| 3 · Ticket line | ![](png/3-paste-open-390-light.png) | ![](png/3-paste-read-390-light.png) | ![](png/3-paste-landed-390-light.png) | ![](png/3-paste-landed-1440-light.png) |

## What all three share
- **Look:** the reskin's Direction A (neutral grey canvas `#F2F2F5` / black, Apple-bright kind colours, ink accent), B's ticket stub (dotted perforation, two punched notches) on Up next, the checklist and the passes, omxqua texture: opaque tonal surfaces, one shadow scale, no glass, blur or translucency anywhere. That includes the phone's tab bar: this brief's rule overrides the earlier nav-glass exception. Colour means a kind, never a day: day chips stay neutral with the selected one in ink, and Direction 3's stubs all wear the same weather blue.
- **Chrome:** desktop top islands (brand · Trip, Book, Family, Ask · the Beacon "Snowshoe · leave in 23 min"); phone floating tab bar (Trip · Plan · Ask · Book · Family).
- **Content:** the same trip, the same honest booking states, the same living weather engine, the same checklist and the same paste moment.

## Honest booking states
| Lane | Before booking | What the lane says | After booking |
|---|---|---|---|
| Flights | **Real price** · 3 h ago: from $148 a person, round trip, with the cheapest fare for each nearby departure day (Aviasales Data API, cached) | "Partner link · we may earn a commission. Aviasales confirms the final price." | Booked on United (found on Aviasales) |
| Stay (a cabin) | **No commission**: Vrbo, Airbnb, Expedia, search filled in | "Klook has 6 hotels here and no cabins, so these are plain links." · "we earn nothing" | Booked on Vrbo |
| Car (SUV, snow chains) | **No commission**: Expedia with an SUV and its snow-chain option filled in | "Plain link, search filled in · we earn nothing" | Booked on Expedia (Hertz) |
| Snowshoeing | **Search on Klook** (Klook covers this one) | "No price here: Klook has the live price. We won't guess one." · partner link | Booked on Klook |
| Snowmobile tour | **No commission**: GetYourGuide | "No partner deal yet, so it's a plain link." | Booked on GetYourGuide |
| Ski lessons | **Buy direct** at Heavenly | "Ski schools sell only on their own site. No middle-man, nothing for us." | Bought direct at Heavenly |

Every booked item shows **"Booked on <partner>"** next to **"Change or cancel"**, which opens the partner's own page; GitAway is never the support centre. The checklist ticket counts "1 of 6", shows a total "booked so far, from your confirmations" (never an invented price), and turns each booked row into a torn stub. Reference numbers stay masked (`••821`). Before the trip there is no forecast yet, so the Book screen's weather widget says "Typical late December · not a forecast yet".

## Interactions (working in the HTML)
| Interaction | Phone (Liquid) | Desktop (calm) |
|---|---|---|
| Tap a day | The map re-flies: diorama camera 1.25 s ease-out, MapLibre `flyTo` 1.7 s, paper map 820 ms on the spring (k170 c26). The route redraws in 1.1 s. Direction 3 opens that day's ticket. | Same calls, calmer: 0.85 s, 1.0 s and 620 ms eases with no overshoot; the route draws in 0.7 s; ticket content fades in 180 ms. |
| The weather follows the day | Numbers cross-fade in place in 140 ms (live values never bounce); the sky eases over about a second: snow thickens or stops, the bank stays (settled snow is its own value), the sun comes out, wind leans the pines. Direction 1's scene snows too. | Same. |
| Drag | Diorama: turn ±50°, tilt, pinch or wheel to zoom. Real map: pan, tilt, turn. Direction 1's phone sheet drags up from its handle and settles on a spring (520 ms). | Diorama: drag and wheel. Real map: drag, right-drag to tilt and turn. |
| Paste a confirmation | The sheet grows out of the button you tapped (520 ms spring). "Read it": a scan line runs over the email (0.9 s), five fields pop out one by one (110 ms apart, spring), the read card flies into its place (the lane, or in Direction 1 the cabin's pin, which pops), the stamp drops (from 1.9× and −16° to −7°, 640 ms, k260 c16) with a small thud on the card, and the checklist row becomes a stub while the ring, the total and the Beacon's count cross-fade. | The panel fades in (180 ms); fields fade in 60 ms apart; the panel fades out; the lane fades to booked and the stamp fades in (180 ms). Nothing flies. |
| Press | Everything tappable squashes to 0.96 (0.90 at 48 px or less) on the k380 c30 spring, 300 ms, in JS, never `:active`. | Same, plus a hover tint. |
| Reduced motion | Everything becomes a 150 ms fade; the weather draws one still frame; the diorama renders one frame per change. | Same. |

## Maps: what each costs
Measured here, gzip unless marked.

| | 1 · Diorama | 2 · Widget board | 3 · Ticket line | Today's app (for comparison) |
|---|---|---|---|---|
| Library | three.js r187, tree-shaken: **147 KB** (122 KB brotli) | MapLibre GL JS 5.24: **275 KB** (225 KB brotli) + 10 KB CSS. Version 6.16 ships as ES modules: 294 KB + a 147 KB worker | None: `paper.js` is **3 KB** | Leaflet 1.9.4: 42 KB |
| Data | Elevation 77 KB (32 KB if stored as 8-bit) + OpenStreetMap shapes 13 KB, once per trip region | First view 0.7–0.9 MB: style 60–130 KB, vector tiles ~115 KB, hillshade elevation 240–430 KB. Flying to two more days adds about 1.5–2 MB of elevation tiles | Relief image 80–100 KB (WebP) + shapes 13 KB, once per trip region | Raster tiles |
| Tiles at run time | None | OpenFreeMap vector tiles + AWS Terrain Tiles | None | OSM raster |
| Offline | Yes, once loaded | No: shows a still of the live map | Yes | No |
| Street level, any destination | No street level; a small build per trip region | Yes, instantly | No street level; a small build per trip region | Yes |
| Cost | Free | Free. OpenFreeMap's public instance has no key and no limits and runs on donations, so no guarantee; the fallback is self-hosting OpenFreeMap or a regional Protomaps file on object storage | Free | Free, within OSM's tile policy |
| Caveats | WebGL on low-end phones: fall back to a still. A second 3D engine to maintain beside the shared-trip story | MapLibre's 3D terrain is one line (`?terrain=1.3` turns it on here), but in 5.24 the DOM pins drift above the draped route with terrain on, so this build ships tilt plus hillshade; pins drawn as a symbol layer would fix it. The hillshade reads elevation only to zoom 10: first view went from 6.6 MB to under 1 MB | Safari's CSS 3D needs testing; the relief softens past about 2× zoom | — |

**The per-trip build** (Directions 1 and 3): [`tools/fetch_geo.py`](tools/fetch_geo.py) does it for Tahoe in about a minute: places from Nominatim, lakes and roads from OpenStreetMap, routes from OSRM, elevation from AWS Terrain Tiles; [`tools/gen_relief.py`](tools/gen_relief.py) draws the relief. In the app it would run once when a trip gets its places, then be cached with the trip (about 120 KB). Shapes could come from OpenFreeMap's tiles instead of Nominatim and Overpass, which ask for light use.

**Routes and drive times (all three) need a decision before launch.** They come from OSRM's demo router, which `gitaway/geo.py` already uses. Its usage note says the demo server is for "reasonable, non-commercial use-cases" and at most one request a second. GitAway earns affiliate money, so that's commercial. The options are self-hosting OSRM or Valhalla for the regions in use, or a routing service whose free tier allows commercial use. The app already caches every leg, so the volume is tiny. This is the founder's call.

## Weather: the living widget and its data
**The engine** is [`core/wx.js`](core/wx.js): one canvas behind the widget's text, 3.5 KB. Snow falls and settles into a bank, the sun turns slowly, wind drives streaks and bends the pines, clouds drift. Flakes fade to 18% behind the words so the text keeps its contrast, it pauses off screen, and reduced motion gets a still frame. The same engine runs Direction 1's rail widget (plus three.js snow in the scene), Direction 2's widget and its snow-by-the-hour day view, and Direction 3's eight small skies.

**The data**, free sources only:

| Source | Free | Commercial use | Range | Notes |
|---|---|---|---|---|
| **MET Norway** Locationforecast (recommended) | Yes | Yes, with credit to MET Norway (NLOD 2.0 and CC BY 4.0) | Global, about 9 days | Send an identifying User-Agent; more than 20 requests a second in total needs an agreement; cache by the `Expires` header |
| NWS api.weather.gov | Yes | Yes: "free to use for any purpose" | US only, 7 days | User-Agent required; a good cross-check for US trips |
| Open-Meteo | Only for non-commercial use (under 10,000 calls a day) | Paid plans | Global, 16 days | GitAway's affiliate links make it commercial, so skip it or pay |
| Before the forecast window | Climate normals (NOAA's US normals are public domain) | — | — | The widget says "Typical late December · not a forecast yet" until the forecast opens about ten days out |

## Rules check
- **Texture:** opaque surfaces and one shadow scale (Direction A's `sh1`/`sh2`/`sh3`); no glass, blur or translucent chrome. The paste sheet dims the page behind it with a scrim.
- **Type:** phone body 17 px, secondary text 16 px; only all-caps labels (13 px) and fine print (14 px) are smaller, as in the reskin. Desktop body 16 px.
- **Targets:** at least 48 px on the phone: day chips 56, buttons 48 (primary 56), Change or cancel 48, tabs 56 in a 68 px bar.
- **Fit:** every desktop artboard fits 1440×900 without scrolling. The grids are fluid, but 1280×800 wasn't checked separately.
- **Contrast** (computed, WCAG):

| Pair | Ratio |
|---|---|
| Ink on canvas, light / dark | 17.6:1 / 19.3:1 |
| Secondary ink on card, light / dark | 6.6:1 / 6.6:1 |
| White on flight / stay / car / tickets / weather / food / see | 7.9 / 6.3 / 5.0 / 5.2 / 5.9 / 5.3 / 5.5 :1 |
| Dark text on ride yellow | 12.9:1 |
| "Booked on" badge, light / dark | 5.7:1 / 9.0:1 |
| Chains badge, light / dark | 7.2:1 / 10.3:1 |
| Up next secondary text on ink / on white (dark mode) | 11.9:1 / 8.7:1 |
| Booked-lane tint ink (stay), light / dark | 9.0:1 / 11.1:1 |
| Map town labels on the relief, light / dark | 8.3:1 / 10.7:1 |

The contrast pass caught one miss: secondary text at 90% opacity on the green car fill dropped to 4.4:1. Text on kind fills is now full strength.

## Recommendation, in full
Build **Direction 3** as the cockpit and Book screen. It's the one that answers what a family checks most: what's on each day, when, and what the weather is doing, all on one screen with today open as the focal ticket. It's distinct (nobody shows a trip as a line of tickets with a living sky in each), it's the lightest (3 KB of map script), and it works offline in the mountains, which matters for this exact trip. Its Book screen (a book of tickets, each with an honest stub) is also the clearest of the three about what earns money and what doesn't.

Then borrow:
1. **From Direction 1:** the diorama becomes the shared-trip 3D story (the brief budgets three.js at 100 to 200 KB there, and it's at 147 KB), with the cockpit's "Whole trip" view as an optional extra.
2. **From Direction 2:** the real map, loaded only when someone taps the paper map for street level, and the Book screen's "Bring a booking home" and ride-estimate widgets.

What needs the founder: the OSRM decision above, and a pick in [`index.html`](index.html).

## Files
- Pages: `index.html` (compare and pick), `1-diorama.html`, `2-widgets.html`, `3-ticket.html`.
- `core/`: `base.css` (tokens, chrome, buttons, stamp), `parts.css` (weather, Up next, lanes, checklist, rail, paste), `d1.css` `d2.css` `d3.css`, `icons.js`, `data.js` (the trip), `ui.js` (shared parts and motion), `wx.js` (weather engine), `diorama.js` (built three.js bundle), `mapl.js` (MapLibre wrapper), `paper.js` (paper map), `d1.js` `d2.js` `d3.js` (the screens), `viewer.js` and `viewer.css` (the overview pages).
- `src/diorama.js`: the diorama's source. `data/`: `geo.js` (places, lakes, roads, routes) and `dem.js` (elevation). `img/`: relief images and the map's offline still. `assets/`: Geist fonts and licence.
- `tools/`: `fetch_geo.py` and `gen_relief.py` (the map data), `build.mjs` (bundles the diorama), `shot.mjs`, `eval.mjs` and `capture.mjs` (screenshots).
- [`CREDITS.md`](CREDITS.md): libraries, data sources, and what was adapted from Meng To's skills.

**Real versus sample:** places, routes, drive times, elevation, lake and road shapes and Spooner Summit's 7,146 ft are real. Weather, prices, totals, reference numbers, the United flight times, the chain control and the family chat are sample data.
