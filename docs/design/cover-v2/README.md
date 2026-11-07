# Cover v2 prototypes (static, not wired into the app)

Four takes on the cover after the founder's feedback: fewer words, the world up front, more colour, and one clear next step.
Open `index.html` to compare them side by side, or `a.html`, `b.html`, `c.html` and `d.html` on their own (`?beat=1..4` jumps to a beat in B and C; `?scene=1..7` freezes a scene in D).
- A, Say it, then show it: a compact card on the left with a "Where to?" box, and four coloured beat chips that change the scene.
- B, The map tells it: captions are coloured pin labels on the world, with a slim bottom bar for the tagline and buttons.
- C, Split screen: a calm left column with numbered beats, the world playing on the right, and one product card per beat.
- D, The story of a trail: seven auto-playing scenes (about 3.5 s each, tappable steps, pause on hover, arrow keys and scroll) from "Still reading the guidebook?" to a world of branching trails, drawn in inline SVG plus the a-3 and a-5 renders; B's bottom bar stays until the last scene shows the tagline big.
The world is the real renders in `assets/cover/stills/`, warmed with a sunset gradient, with a slow Ken Burns pan and crossfades. Motion stops under prefers-reduced-motion.
Colour: Start a trip is sunset orange (#D2401C light, #FF8A5B dark). The four beats use the kind colours see, stay, tickets and food.
Screenshots: `png/{a,b,c}-{wide,phone}.png` (1440x900 and 390x844, light mode).
D screenshots: `png/d-{1..7}-wide.png`, `png/d-{1,4,7}-phone.png` and `png/d-7-wide-dark.png`, made by `pixi run python docs/design/cover-v2/shoot-d.py docs/design/cover-v2/png`.
