# GitAway's cover page as a 3D scroll world: three prototypes

Throwaway design prototypes for the cover page (the signed-out landing) named under "Later" in `docs/briefs/free-and-polished.md`. No app code changed. **Open [`index.html`](index.html)**, or any concept straight from this folder (`file://` works, no server): [`a.html`](a.html), [`b.html`](b.html), [`c.html`](c.html). Built in Direction A (grey canvas, Apple-bright kind colours, ink accent, Geist) on omxqua's rules, light and dark, phone and laptop.

Instead of explaining GitAway, each page tells it as a story inside one real place you scroll through: **"Don't read about it. Go."** A guidebook lies open on the grey canvas; as you scroll, its pages fly off and its printed map rises into the world. Then a family's shared trip appears, you fork it, plan it together, go, and share it back.

URL switches: `?mode=light|dark`, `?still` (the calm still version), `?shot=<0..6>&local=<0..1>` (land on a chapter), `?q=low|high` (quality tier), `?measure` (no governor, raw numbers). `Shift` + `←`/`→` or the dark pill at the bottom right switches concepts.

## The place: Lake Tahoe in December
- **It's the captain's own trip.** The brief's test is planning and booking the December Tahoe trip on GitAway, so the cover's sample trip can become the first real shared trip.
- **Every beat fits in one bowl of land:** a deep blue lake (the most saturated thing on screen), snow, pines, a cabin and a pier, Heavenly's runs and gondola (tickets), a road around the lake (drive times), and Emerald Bay with Fannette Island (a landmark you'd recognise).
- **Snow is Direction A's grey canvas.** On a snowfield the kind colours, the ink trail and the solid widgets pop exactly as they do on the app's `#F2F2F5`.
- **Night has its own scene.** Dark mode is moonlight on snow, a moon glitter path on the lake, and warm cabin and town windows.
- **Considered:**
  - Yosemite: granite and waterfalls, but no road around a lake and no town to stay in.
  - Iceland: the northern lights would make a great dark mode, but it's far from the captain's trip.
  - Disneyland: the captain's other trip, but a theme park means someone else's IP on the cover.

## The story (one beat ledger, told three ways)
| # | Beat | Words on the card (A) | What the world does |
|---|---|---|---|
| 0 | Hook | **Don't read about it. Go.** Forget the guidebook. Start from a trip a real family took, make it yours, and go. | A guidebook on the grey canvas (a reading lamp at night). Its left-hand pages peel and fly away; the right-hand page is a printed map that rises into mountains, grows trees, and fills with water. |
| 1 | Arrive | **A family shared their five days here.** | The shared trip draws itself around the lake as an ink line (white and glowing at night); kind-coloured pins pop as it reaches each day. |
| 2 | Fork | **Make it yours.** | The line branches at the cabin. Theirs fades; yours draws on, and a small green car drives it. |
| 3 | Plan together | **The whole trip on one screen.** | It snows. Your route redraws with a running pulse, and the trip's widgets stamp in one by one: weather, the drive, then flight, stay, car and tickets, each with a "BOOKED" stamp and "Booked on Aviasales / Vrbo / Expedia / Klook ↗" (links out only, never a checkout). |
| 4 | Go | **Then go. Be there.** | Time moves: the sun sinks behind the west shore (at night, the moon sets and the stars come out) while the family stands at the end of the pier. |
| 5 | Share it back | **Someone's next trip starts with yours.** | Postcards lift off the pier (their photos are real renders of this world) and drift to the next family's cabin; a thank-you sparkle comes back. |
| 6 | Action | **Your trip is out there.** Start a trip · Share a trip · See trips people shared | The camera pulls up over the whole lake as other families' trips and their forks draw across it. |

All the text is real DOM text in semantic sections (headings, paragraphs, buttons), readable without the canvas. The canvas is decorative and `aria-hidden`.

## The three concepts
| | **A · One continuous fly-through** | **B · One place, four seasons** | **C · The road trip** (wildcard) |
|---|---|---|---|
| Idea | One camera flies the whole story over one continuous world, chapter by chapter. | One tripod above Emerald Bay; the place changes, not the camera. Each chapter is a different family's trip in a different season. | Scroll is the accelerator. A chase camera rides behind the family's car; the fork is a literal fork in the road. |
| Meng To's topology | Continuous geography | Layered reveal | Continuous geography, chase rig |
| Arrive | The trip circles the whole lake | Lena & Sam's winter snowshoe loop from the overlook to the castle | The route glows on the road ahead as the car comes over Kingsbury Grade |
| Fork | The branch splits at the cabin and the car drives it | Spring: Priya forks the winter trip toward Eagle Falls as the snow melts and the aspens leaf | At the junction they went straight on; you take the turn (the blinker blinks) |
| Plan together | Widgets stamp into the world with dashed leaders to their places | Summer: the Okafors' kayak route to Fannette Island, same widgets | The widgets stamp onto the glass as you drive past their places |
| Go | Sunset on the pier | Fall: gold aspens, falling leaves, the family on the beach at the bay's mouth | The family sleds at golden hour, the lake far below |
| Share it back | Postcards fly to the next cabin | A year later: four postcards (the same view in all four seasons) go to a new family | The photos fly down the valley to the next car coming up |
| Ending | Every shared trip and its forks drawn across the lake | Every trip rises into a fork tree growing from Fannette Island | Every family's car on its own trip around the lake |

On a laptop each story card sits on the left and the world is shifted right with a lens offset (`setViewOffset`), so the subject is never under the words. On a phone the world is composed in the top part of the screen and the card sits in the thumb zone; the plan's widgets become one swipeable row with the next card peeking (the taste file's "parallel cards swipe in one row" rule), and fewer labels show.

<!-- GALLERY -->
## Every chapter, captured
Each chapter at its most telling moment, with its text: 1440 wide and 390 wide (phone, at 2×), day and night. The files are `png/<concept>-<chapter>-<1440|390>-<light|dark>.png`. Scroll-throughs: [`motion/a.mp4`](motion/a.mp4), [`motion/b.mp4`](motion/b.mp4), [`motion/c.mp4`](motion/c.mp4) (1280 × 800, day, rendered frame by frame).

### A · Fly-through

| | 0 · The book | 1 · Arrive | 2 · Fork | 3 · Plan together | 4 · Go | 5 · Share it back | 6 · Start |
|---|---|---|---|---|---|---|---|
| 1440 day | <a href="png/a-0-1440-light.png"><img src="png/a-0-1440-light.png" width="150" alt="A · Fly-through, chapter 0, 1440 light"></a> | <a href="png/a-1-1440-light.png"><img src="png/a-1-1440-light.png" width="150" alt="A · Fly-through, chapter 1, 1440 light"></a> | <a href="png/a-2-1440-light.png"><img src="png/a-2-1440-light.png" width="150" alt="A · Fly-through, chapter 2, 1440 light"></a> | <a href="png/a-3-1440-light.png"><img src="png/a-3-1440-light.png" width="150" alt="A · Fly-through, chapter 3, 1440 light"></a> | <a href="png/a-4-1440-light.png"><img src="png/a-4-1440-light.png" width="150" alt="A · Fly-through, chapter 4, 1440 light"></a> | <a href="png/a-5-1440-light.png"><img src="png/a-5-1440-light.png" width="150" alt="A · Fly-through, chapter 5, 1440 light"></a> | <a href="png/a-6-1440-light.png"><img src="png/a-6-1440-light.png" width="150" alt="A · Fly-through, chapter 6, 1440 light"></a> |
| 1440 night | <a href="png/a-0-1440-dark.png"><img src="png/a-0-1440-dark.png" width="150" alt="A · Fly-through, chapter 0, 1440 dark"></a> | <a href="png/a-1-1440-dark.png"><img src="png/a-1-1440-dark.png" width="150" alt="A · Fly-through, chapter 1, 1440 dark"></a> | <a href="png/a-2-1440-dark.png"><img src="png/a-2-1440-dark.png" width="150" alt="A · Fly-through, chapter 2, 1440 dark"></a> | <a href="png/a-3-1440-dark.png"><img src="png/a-3-1440-dark.png" width="150" alt="A · Fly-through, chapter 3, 1440 dark"></a> | <a href="png/a-4-1440-dark.png"><img src="png/a-4-1440-dark.png" width="150" alt="A · Fly-through, chapter 4, 1440 dark"></a> | <a href="png/a-5-1440-dark.png"><img src="png/a-5-1440-dark.png" width="150" alt="A · Fly-through, chapter 5, 1440 dark"></a> | <a href="png/a-6-1440-dark.png"><img src="png/a-6-1440-dark.png" width="150" alt="A · Fly-through, chapter 6, 1440 dark"></a> |
| 390 day | <a href="png/a-0-390-light.png"><img src="png/a-0-390-light.png" width="74" alt="A · Fly-through, chapter 0, 390 light"></a> | <a href="png/a-1-390-light.png"><img src="png/a-1-390-light.png" width="74" alt="A · Fly-through, chapter 1, 390 light"></a> | <a href="png/a-2-390-light.png"><img src="png/a-2-390-light.png" width="74" alt="A · Fly-through, chapter 2, 390 light"></a> | <a href="png/a-3-390-light.png"><img src="png/a-3-390-light.png" width="74" alt="A · Fly-through, chapter 3, 390 light"></a> | <a href="png/a-4-390-light.png"><img src="png/a-4-390-light.png" width="74" alt="A · Fly-through, chapter 4, 390 light"></a> | <a href="png/a-5-390-light.png"><img src="png/a-5-390-light.png" width="74" alt="A · Fly-through, chapter 5, 390 light"></a> | <a href="png/a-6-390-light.png"><img src="png/a-6-390-light.png" width="74" alt="A · Fly-through, chapter 6, 390 light"></a> |
| 390 night | <a href="png/a-0-390-dark.png"><img src="png/a-0-390-dark.png" width="74" alt="A · Fly-through, chapter 0, 390 dark"></a> | <a href="png/a-1-390-dark.png"><img src="png/a-1-390-dark.png" width="74" alt="A · Fly-through, chapter 1, 390 dark"></a> | <a href="png/a-2-390-dark.png"><img src="png/a-2-390-dark.png" width="74" alt="A · Fly-through, chapter 2, 390 dark"></a> | <a href="png/a-3-390-dark.png"><img src="png/a-3-390-dark.png" width="74" alt="A · Fly-through, chapter 3, 390 dark"></a> | <a href="png/a-4-390-dark.png"><img src="png/a-4-390-dark.png" width="74" alt="A · Fly-through, chapter 4, 390 dark"></a> | <a href="png/a-5-390-dark.png"><img src="png/a-5-390-dark.png" width="74" alt="A · Fly-through, chapter 5, 390 dark"></a> | <a href="png/a-6-390-dark.png"><img src="png/a-6-390-dark.png" width="74" alt="A · Fly-through, chapter 6, 390 dark"></a> |

### B · Four seasons

| | 0 · The book | 1 · Winter | 2 · Spring fork | 3 · Summer plan | 4 · Fall, go | 5 · A year later | 6 · Fork tree |
|---|---|---|---|---|---|---|---|
| 1440 day | <a href="png/b-0-1440-light.png"><img src="png/b-0-1440-light.png" width="150" alt="B · Four seasons, chapter 0, 1440 light"></a> | <a href="png/b-1-1440-light.png"><img src="png/b-1-1440-light.png" width="150" alt="B · Four seasons, chapter 1, 1440 light"></a> | <a href="png/b-2-1440-light.png"><img src="png/b-2-1440-light.png" width="150" alt="B · Four seasons, chapter 2, 1440 light"></a> | <a href="png/b-3-1440-light.png"><img src="png/b-3-1440-light.png" width="150" alt="B · Four seasons, chapter 3, 1440 light"></a> | <a href="png/b-4-1440-light.png"><img src="png/b-4-1440-light.png" width="150" alt="B · Four seasons, chapter 4, 1440 light"></a> | <a href="png/b-5-1440-light.png"><img src="png/b-5-1440-light.png" width="150" alt="B · Four seasons, chapter 5, 1440 light"></a> | <a href="png/b-6-1440-light.png"><img src="png/b-6-1440-light.png" width="150" alt="B · Four seasons, chapter 6, 1440 light"></a> |
| 1440 night | <a href="png/b-0-1440-dark.png"><img src="png/b-0-1440-dark.png" width="150" alt="B · Four seasons, chapter 0, 1440 dark"></a> | <a href="png/b-1-1440-dark.png"><img src="png/b-1-1440-dark.png" width="150" alt="B · Four seasons, chapter 1, 1440 dark"></a> | <a href="png/b-2-1440-dark.png"><img src="png/b-2-1440-dark.png" width="150" alt="B · Four seasons, chapter 2, 1440 dark"></a> | <a href="png/b-3-1440-dark.png"><img src="png/b-3-1440-dark.png" width="150" alt="B · Four seasons, chapter 3, 1440 dark"></a> | <a href="png/b-4-1440-dark.png"><img src="png/b-4-1440-dark.png" width="150" alt="B · Four seasons, chapter 4, 1440 dark"></a> | <a href="png/b-5-1440-dark.png"><img src="png/b-5-1440-dark.png" width="150" alt="B · Four seasons, chapter 5, 1440 dark"></a> | <a href="png/b-6-1440-dark.png"><img src="png/b-6-1440-dark.png" width="150" alt="B · Four seasons, chapter 6, 1440 dark"></a> |
| 390 day | <a href="png/b-0-390-light.png"><img src="png/b-0-390-light.png" width="74" alt="B · Four seasons, chapter 0, 390 light"></a> | <a href="png/b-1-390-light.png"><img src="png/b-1-390-light.png" width="74" alt="B · Four seasons, chapter 1, 390 light"></a> | <a href="png/b-2-390-light.png"><img src="png/b-2-390-light.png" width="74" alt="B · Four seasons, chapter 2, 390 light"></a> | <a href="png/b-3-390-light.png"><img src="png/b-3-390-light.png" width="74" alt="B · Four seasons, chapter 3, 390 light"></a> | <a href="png/b-4-390-light.png"><img src="png/b-4-390-light.png" width="74" alt="B · Four seasons, chapter 4, 390 light"></a> | <a href="png/b-5-390-light.png"><img src="png/b-5-390-light.png" width="74" alt="B · Four seasons, chapter 5, 390 light"></a> | <a href="png/b-6-390-light.png"><img src="png/b-6-390-light.png" width="74" alt="B · Four seasons, chapter 6, 390 light"></a> |
| 390 night | <a href="png/b-0-390-dark.png"><img src="png/b-0-390-dark.png" width="74" alt="B · Four seasons, chapter 0, 390 dark"></a> | <a href="png/b-1-390-dark.png"><img src="png/b-1-390-dark.png" width="74" alt="B · Four seasons, chapter 1, 390 dark"></a> | <a href="png/b-2-390-dark.png"><img src="png/b-2-390-dark.png" width="74" alt="B · Four seasons, chapter 2, 390 dark"></a> | <a href="png/b-3-390-dark.png"><img src="png/b-3-390-dark.png" width="74" alt="B · Four seasons, chapter 3, 390 dark"></a> | <a href="png/b-4-390-dark.png"><img src="png/b-4-390-dark.png" width="74" alt="B · Four seasons, chapter 4, 390 dark"></a> | <a href="png/b-5-390-dark.png"><img src="png/b-5-390-dark.png" width="74" alt="B · Four seasons, chapter 5, 390 dark"></a> | <a href="png/b-6-390-dark.png"><img src="png/b-6-390-dark.png" width="74" alt="B · Four seasons, chapter 6, 390 dark"></a> |

### C · Road trip

| | 0 · The book | 1 · Arrive | 2 · Fork | 3 · Plan together | 4 · Go | 5 · Share it back | 6 · Start |
|---|---|---|---|---|---|---|---|
| 1440 day | <a href="png/c-0-1440-light.png"><img src="png/c-0-1440-light.png" width="150" alt="C · Road trip, chapter 0, 1440 light"></a> | <a href="png/c-1-1440-light.png"><img src="png/c-1-1440-light.png" width="150" alt="C · Road trip, chapter 1, 1440 light"></a> | <a href="png/c-2-1440-light.png"><img src="png/c-2-1440-light.png" width="150" alt="C · Road trip, chapter 2, 1440 light"></a> | <a href="png/c-3-1440-light.png"><img src="png/c-3-1440-light.png" width="150" alt="C · Road trip, chapter 3, 1440 light"></a> | <a href="png/c-4-1440-light.png"><img src="png/c-4-1440-light.png" width="150" alt="C · Road trip, chapter 4, 1440 light"></a> | <a href="png/c-5-1440-light.png"><img src="png/c-5-1440-light.png" width="150" alt="C · Road trip, chapter 5, 1440 light"></a> | <a href="png/c-6-1440-light.png"><img src="png/c-6-1440-light.png" width="150" alt="C · Road trip, chapter 6, 1440 light"></a> |
| 1440 night | <a href="png/c-0-1440-dark.png"><img src="png/c-0-1440-dark.png" width="150" alt="C · Road trip, chapter 0, 1440 dark"></a> | <a href="png/c-1-1440-dark.png"><img src="png/c-1-1440-dark.png" width="150" alt="C · Road trip, chapter 1, 1440 dark"></a> | <a href="png/c-2-1440-dark.png"><img src="png/c-2-1440-dark.png" width="150" alt="C · Road trip, chapter 2, 1440 dark"></a> | <a href="png/c-3-1440-dark.png"><img src="png/c-3-1440-dark.png" width="150" alt="C · Road trip, chapter 3, 1440 dark"></a> | <a href="png/c-4-1440-dark.png"><img src="png/c-4-1440-dark.png" width="150" alt="C · Road trip, chapter 4, 1440 dark"></a> | <a href="png/c-5-1440-dark.png"><img src="png/c-5-1440-dark.png" width="150" alt="C · Road trip, chapter 5, 1440 dark"></a> | <a href="png/c-6-1440-dark.png"><img src="png/c-6-1440-dark.png" width="150" alt="C · Road trip, chapter 6, 1440 dark"></a> |
| 390 day | <a href="png/c-0-390-light.png"><img src="png/c-0-390-light.png" width="74" alt="C · Road trip, chapter 0, 390 light"></a> | <a href="png/c-1-390-light.png"><img src="png/c-1-390-light.png" width="74" alt="C · Road trip, chapter 1, 390 light"></a> | <a href="png/c-2-390-light.png"><img src="png/c-2-390-light.png" width="74" alt="C · Road trip, chapter 2, 390 light"></a> | <a href="png/c-3-390-light.png"><img src="png/c-3-390-light.png" width="74" alt="C · Road trip, chapter 3, 390 light"></a> | <a href="png/c-4-390-light.png"><img src="png/c-4-390-light.png" width="74" alt="C · Road trip, chapter 4, 390 light"></a> | <a href="png/c-5-390-light.png"><img src="png/c-5-390-light.png" width="74" alt="C · Road trip, chapter 5, 390 light"></a> | <a href="png/c-6-390-light.png"><img src="png/c-6-390-light.png" width="74" alt="C · Road trip, chapter 6, 390 light"></a> |
| 390 night | <a href="png/c-0-390-dark.png"><img src="png/c-0-390-dark.png" width="74" alt="C · Road trip, chapter 0, 390 dark"></a> | <a href="png/c-1-390-dark.png"><img src="png/c-1-390-dark.png" width="74" alt="C · Road trip, chapter 1, 390 dark"></a> | <a href="png/c-2-390-dark.png"><img src="png/c-2-390-dark.png" width="74" alt="C · Road trip, chapter 2, 390 dark"></a> | <a href="png/c-3-390-dark.png"><img src="png/c-3-390-dark.png" width="74" alt="C · Road trip, chapter 3, 390 dark"></a> | <a href="png/c-4-390-dark.png"><img src="png/c-4-390-dark.png" width="74" alt="C · Road trip, chapter 4, 390 dark"></a> | <a href="png/c-5-390-dark.png"><img src="png/c-5-390-dark.png" width="74" alt="C · Road trip, chapter 5, 390 dark"></a> | <a href="png/c-6-390-dark.png"><img src="png/c-6-390-dark.png" width="74" alt="C · Road trip, chapter 6, 390 dark"></a> |

<!-- /GALLERY -->

## Measured
<!-- MEASURED -->
### JavaScript (what a page downloads, gzip -9)
| Page | `page.js` | scene script (three.js r187 tree-shaken inside) | **Total** | Brotli total |
|---|---|---|---|---|
| A · Fly-through | 2.6 KB | 161.4 KB | **164.1 KB** | 137.1 KB |
| B · Four seasons | 2.6 KB | 164.2 KB | **166.8 KB** | 139.3 KB |
| C · Road trip | 2.6 KB | 161.3 KB | **163.9 KB** | 136.8 KB |

All three are under the 250 KB budget with room to spare. three.js is most of each scene script; the world, story and page code add about 25 KB. The scene script isn't loaded at all for reduced motion, without WebGL, or on a weak phone (2 GB of memory or 2 cores or fewer).

### Assets (images, fonts)
The live world loads **no textures or models**: the terrain, lake, sky, trees, cabin, guidebook pages and printed map are generated in code. What a visit downloads besides the scripts:

| | A | B | C |
|---|---|---|---|
| Poster (chapter 0's still, shown at once; laptop / phone, day) | 19.7 / 14.2 KB | 19.7 / 14.2 KB | 19.7 / 14.3 KB |
| Geist, inlined in `fonts.css` (gzip) | 68.9 KB | same | same |
| `cover.css` (gzip) | 4.4 KB | same | same |
| Calm still version: the 7 stills one visit can load (laptop day, the largest set) | 461.7 KB | 251.4 KB | 308.2 KB |
| Every still on disk (7 chapters × laptop and phone × day and night) | 1160.0 KB | 697.6 KB | 809.5 KB |

Everything a visit can load stays well under 1.5 MB. The stills load one chapter at a time, plus the next one ahead.

### Frame rate (`node tools/measure.mjs`, results in `tools/fps.json`)
A 390 × 844 phone (DPR 3, which the scene caps at 1.5; touch; the lighter phone tier), Chromium's CPU throttled 4×, scrolled through the whole story in about 24 s (the numbers cover the last 1,200 frames, about 20 s of it). It ran on this machine's GPU (an RTX 3090 through Vulkan) and on SwiftShader, Chromium's software renderer, standing in for a weak phone GPU. The quality governor and the weak-phone fallback were off, so the numbers are raw. Then a 1440 × 900 laptop, unthrottled.

| | Phone, CPU 4×, GPU: fps · p95 frame | Phone, CPU 4×, software GL: fps · p95 · frames over 33 ms | Main-thread JS per frame, phone CPU 4× (median / p95) | Laptop 1440, GPU: fps · p95 | Draw calls · triangles (max, phone / laptop) |
|---|---|---|---|---|---|
| A · Fly-through | **59.8** · 16.8 ms | **15.6** · 133.3 ms · 83% | 1.8 / 3.6 ms | **57.6** · 16.8 ms | 37 · 141k / 38 · 305k |
| B · Four seasons | **59.8** · 16.7 ms | **15.9** · 133.3 ms · 76.8% | 2.8 / 6.2 ms | **59.9** · 16.7 ms | 37 · 144k / 37 · 309k |
| C · Road trip | **59.8** · 16.7 ms | **15.6** · 133.4 ms · 75.3% | 2.9 / 5.7 ms | **59.9** · 16.8 ms | 49 · 129k / 49 · 293k |

**What this does and doesn't prove.** The 4× CPU throttle slows the page's JavaScript the way a mid phone does, and the per-frame JavaScript shows how much of the 16.7 ms budget is left. But this desktop GPU is far faster than a phone's, and SwiftShader renders on the CPU without being throttled, so neither run is a real mid phone. The fallback exists for exactly that case: after 2.5 s the governor checks every second (or every 45 frames) and lowers the pixel ratio step by step, to 0.55 of it at worst, while frames average over 23 ms; if they still average over 45 ms for three checks in a row at the lowest setting, it switches to the still version. **Next step: open the three pages on the captain's own phone.**

The same weak-GPU phone with the governor **on**, which is what a visitor would get: all three step down to 0.55× resolution within about 4 s, still miss 22 fps, and switch to the calm stills (A after about 7 s, B after about 6 s, C after about 5 s). On this machine's GPU the governor never has to act.

### Pausing (checked by the same script, `node tools/measure.mjs pause`)
The stage is fixed behind the page, so it only goes offscreen when the full-screen closing footer covers it; the loop also stops when the tab is hidden (the check flips `document.hidden` and fires `visibilitychange`, as switching tabs does). Renders counted by three.js's own frame counter over 1.5 s on the laptop page:

| | Footer covering the stage | Back in the story | Tab hidden | Tab shown again |
|---|---|---|---|---|
| A · Fly-through | 0 (loop stopped) | 90 | 0 (loop stopped) | 90 |
| B · Four seasons | 0 (loop stopped) | 90 | 0 (loop stopped) | 90 |
| C · Road trip | 0 (loop stopped) | 91 | 0 (loop stopped) | 90 |

<!-- /MEASURED -->

## What I took from which Meng To skill
| Skill | What it gave these pages |
|---|---|
| `build-threejs-scroll-worlds` (primary; its Kage demo and references) | The whole architecture: one persistent renderer, scene and camera for the page, and one reversible scroll state. Native scroll is the only source of truth, with an exact value for the DOM and a damped one (rate 5.2) for the camera. Chapter endpoints are composed per layout, then position and target run on Catmull–Rom curves with the field of view interpolated per segment. Also: the pixel-ratio governor with Kage's thresholds, pausing when hidden, the `dt` clamp, `?shot=` states, a poster plus chapter stills as the fallback, DOM text over a fixed canvas, particles recycled ahead of the camera, and procedural canvas textures instead of image files. |
| `scroll-world-storytelling` | Choosing the Three.js mode because the metaphor is a place, the beat ledger above, and "reduced motion uses the poster or ordered stills". |
| `cinematic-scroll-storytelling` | Pinned cards and pacing. Its GSAP and Lenis stack is left out on purpose: the primary skill keeps native scroll, and it saves about 50 KB. |
| `threejs-landscape` | The analytic height function shared by every mesh, domain-warped noise, ground coloured by slope and height with no textures, resolution that follows the lens (a foveated grid), stars in the visible band only, and time of day as interpolated full states. |
| `3d-four-seasons` | Concept B's shared season state: the snow line, settled snow on high flat ground, evergreens that keep their needles, aspen crowns thinning to bare branches, and seasonal light. |
| `3d-sky-background` | One sky function used by the dome, the lake's reflections and the haze, so water meets sky with no line, and one sun direction for disc, glow and light. |
| `3d-ultra-realistic-water` | The lake: per-pixel normals from analytic wave derivatives with a footprint fade per wave, Schlick Fresnel (F0 0.02), the reflection clamped above the horizon, glitter, and haze into the sky's horizon colour. |
| `3d-falling-leaves` | Concept B's fall: instanced leaves whose sideways slip follows their tumble, recycled ahead of the camera. |
| `3d-sky-rays` | Read and left out: a screen-space ray pass is a full-screen cost a mid phone can't spare. The golden-hour glow lives in the sky function. |
| `build-mobile-threejs-games`, `optimize-threejs-games` | A lighter phone tier by default, capped pixel ratio, thumb-zone UI, ignoring URL-bar resizes, and measuring on one repeatable path with draw calls and triangles. |

Details and file locations: [`CREDITS.md`](CREDITS.md).

## The brief's rules
- **Standalone, from disk:** three.js r187 is tree-shaken into each concept's script (no CDN). No GSAP or Lenis. The Geist font is inlined as a data URI, because a page opened from disk can't fetch a font file.
- **Under 250 KB of JavaScript, gzipped, including three.js:** yes, all three (table above).
- **Assets loaded progressively, under 1.5 MB, a poster at once:** the live world downloads no textures or models at all; the terrain, lake, sky, trees, cabin, guidebook pages and map are generated in code. The only image a live visit loads is the poster, chapter 0's still, which matches the first live frame. The calm still version loads one still per chapter, the next one ahead.
- **60 fps on a mid phone:** measured as honestly as this machine allows (above). Not yet tried on a real phone.
- **Pause when offscreen or hidden:** checked (above).
- **Reduced motion and no WebGL:** checked with `reducedMotion: 'reduce'` and with `--disable-webgl`. Both get the still version with the same text, and neither downloads three.js.
- **Real DOM text, light = day, dark = night, no glass or blur:** yes. Cards, widgets and labels are opaque.
- **16 px minimum body text, 48 px targets on phones:** body text is 17 px in phone cards and 16 px in phone widgets and labels; the eyebrows are 13 px all-caps labels, as in the reskin. Buttons and chips are 48 px tall, with 56 px primary buttons on the phone.

## Rough edges and what isn't proven
- **No real phone yet.** Every frame-rate number above comes from this desktop (its GPU, and SwiftShader standing in for a weak one). The pixel-ratio governor and the switch to stills are built and run on every page, but haven't been tried on a real weak phone.
- **A:** at noon the lake reads a little flat from straight above, and on windows narrower than 1440 the day-5 label sits close to the right edge. The family are round-headed toys on purpose, as in story3d.
- **B:** the tripod over Emerald Bay is tight, so its trails are thin lines from that distance, and the fall chapter looks down a dark canyon wall. The seasons themselves are the strongest visuals of the three.
- **C:** the chase camera keeps the car big in the frame and the sledding family small. It is also the busiest: the camera never stops moving while you scroll (reduced motion gets the stills).
- **Widgets in A and B** are laid out for the chapter's endpoint and recomputed on resize. On very wide or very short windows they can sit a little off their best spots.
- **Postcards** render their four photos once, the first time you reach the share chapter: about a 15 ms hitch here, probably more on a phone. In the app they'd be the family's real photos.
- **The guidebook's pages** are canvas textures (an illustration); the words that matter are all DOM. At night "time moves" as the moon setting behind the west shore, chosen for the picture over astronomy.
- **The font** is inlined as a 69 KB (gzip) data URI only because the pages open from disk; in the app it would be a normal preloaded woff2.
- **The PNGs** are 256-colour, quantised in sRGB, to keep 84 files to about 20 MB; soft gradients show slight dithering. The stills the pages use are WebP and don't.


## Recommendation
**Build A, the continuous fly-through.** It's the only one where every beat reads at a glance on both a laptop and a phone (the shared trip circling the lake, the fork at the cabin with your car on it, the plan's widgets stamped into the world with leaders to their places, the pier at sunset), and at 164 KB of JavaScript it costs no more than the others. Give its last chapter B's fork tree, which says "the GitHub of travel" better than a flat web of trails, and keep C's chase camera for a "drive this trip" moment on shared trip pages, not the cover, because constant camera motion tires the most people. Before building, open A on the captain's own phone: this machine flatters every frame-rate number here.


## Files
- `index.html`: the overview to open first. `a.html`, `b.html`, `c.html`: the concepts (written by `tools/pages.mjs` from one template).
- `cover.css`: Direction A tokens and the page. `fonts.css`: Geist, inlined.
- `src/`: `page.js` (the page side: light or dark, phone or wide, live or still, and the scroll conductor), `scene.js` (renderer, loop, governor, camera rig, DOM anchors), `geo.js` (Tahoe's height function, roads and places), `world.js` (terrain, lake, sky, trees, props, light states), `book.js` (the guidebook), `fx.js` (trails, pins, snow, leaves, sparkle, postcards), `story.js` (labels, widgets, postcard flight for B and C), and `concept-a.js`, `concept-b.js`, `concept-c.js`.
- `dist/`: the built classic scripts and `sizes.json`.
- `stills/`: the calm stills, `<concept>-<chapter>-<wide|phone>-<light|dark>.webp`; chapter 0 is the poster.
- `png/`: every chapter with its text, `<concept>-<chapter>-<1440|390>-<light|dark>.png` (256-colour PNGs to keep the repo light).
- `motion/`: one scroll-through per concept, `a.mp4`, `b.mp4`, `c.mp4`.
- `tools/`: `build.mjs` (bundle and measure sizes), `pages.mjs`, `index.mjs`, `readme.mjs` (fills this README's gallery and numbers), `shot.mjs`, `capture.mjs` (stills, PNGs, videos), `measure.mjs` (frame rate, the weak-GPU governor run and the pause checks, results in `fps.json`).
- Rebuild: `node tools/build.mjs && node tools/pages.mjs && node tools/capture.mjs && node tools/measure.mjs && node tools/measure.mjs weak && node tools/measure.mjs pause && node tools/readme.mjs && node tools/index.mjs`, with esbuild, three@0.187.0 and Playwright from `~/.cache/story3d-build` (outside the repo, shared with story3d).
