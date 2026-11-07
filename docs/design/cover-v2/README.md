# Cover v2 prototypes (static, not wired into the app)

Five takes on the cover after the founder's feedback: fewer words, the world up front, more colour, and one clear next step.
Open `index.html` to compare them side by side, or `a.html` to `e.html` on their own (`?beat=1..4` jumps to a beat in B and C; `?scene=1..7` freezes a scene in D).
- A, Say it, then show it: a compact card on the left with a "Where to?" box, and four coloured beat chips that change the scene.
- B, The map tells it: captions are coloured pin labels on the world, with a slim bottom bar for the tagline and buttons.
- C, Split screen: a calm left column with numbered beats, the world playing on the right, and one product card per beat.
- D, The story of a trail: seven auto-playing scenes (about 3.5 s each, tappable steps, pause on hover, arrow keys and scroll) from "Still reading the guidebook?" to a world of branching trails, drawn in inline SVG plus the a-3 and a-5 renders; B's bottom bar stays until the last scene shows the tagline big.
The world is the real renders in `assets/cover/stills/`, warmed with a sunset gradient, with a slow Ken Burns pan and crossfades. Motion stops under prefers-reduced-motion.
Colour: Start a trip is sunset orange (#D2401C light, #FF8A5B dark). The four beats use the kind colours see, stay, tickets and food.
Screenshots: `png/{a,b,c}-{wide,phone}.png` (1440x900 and 390x844, light mode).
D screenshots: `png/d-{1..7}-wide.png`, `png/d-{1,4,7}-phone.png` and `png/d-7-wide-dark.png`, made by `pixi run python docs/design/cover-v2/shoot-d.py docs/design/cover-v2/png`.
- E, The trail, a film with a voice: D as one continuous film of eight beats (about 49 s silent), with a moving camera that flies between scenes, flat illustration with friendlier faces, the real Tahoe renders (`a-1`, `a-4` for "they're there", `a-2` behind the edit, `a-3` for Rosa and Tomás) layered for a slow dolly with falling snow, and a dotted globe (canvas, orthographic, auto-rotating) that fills with trails, pins, reactions and a crowd of travellers. Captions are always on; "Play with sound" restarts the current beat with the narrator, then becomes a mute toggle. Steps, pause, arrow keys, space and swipe all work. Reduced motion holds one still frame per beat and crossfades between them, and the voice still works.
  - Freeze a frame: `e.html?beat=1..8&t=0.6` (a `t` up to 1 is a share of the beat; above 1 it is seconds).
  - Voice: `e-assets/vo-1..8.ogg` (Opus, 48 kbps mono) and `.m4a` (AAC fallback), made with Kokoro-82M (Apache-2.0), voice `af_heart`, speed 0.95. Alternatives for line 1: `e-assets/voice-sample-af_bella.ogg` and `voice-sample-am_michael.ogg`. With sound on, a beat lasts at least as long as its line plus 0.8 s; if a file will not play, the page falls back to the browser's speech.
  - Globe land: Natural Earth 110 m land (public domain), baked into a 1.5° mask inside the page.
  - Screenshots: `png/e-{1..8}-wide.png`, `png/e-{1,5,8}-phone.png`, `png/e-8-wide-dark.png` and the silent autoplay `png/e-autoplay.webm` (1280x720, first 25 s), made by `pixi run python docs/design/cover-v2/shoot-e.py video` (add `sound` or `rm` to check the voice and reduced motion).
