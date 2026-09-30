# Design handoff: landing page (F-013)

**Chosen:** Landing A, "Two doors" (captain, 2026-09-29). Artboard source: `docs/design/canvas/Landing-A.dc.html`. Landing B is reference only.
**System:** `design-system/DESIGN-SYSTEM.md` and `assets/css/tokens.css`. Re-implement it in FastHTML and plain CSS/JS; don't paste the artboard markup.

## Page, top to bottom
1. **Shared header** (layout.page()).
2. **Headline**: centred "Fork a getaway." (display 92px, with an accent-2 hand-drawn underline under "getaway.") and a one-line lede.
3. **Two doors**: two 40px-radius panels side by side.
   - **Door one** (coral block #FF8A63, as on the artboard, ink text): "We're going. Let's book it." It holds a white search card with From / To / When / Who fields (labels plus inputs, prefilled with the catalog's SAMPLE_TRIP) and an ink button, "Open my trip workspace", that goes to `/plan`, plus a one-line promise.
   - **Door two** (sky block #6DB8FF): "No plans yet? Fork a real one." It has two tilted trip cards (the sample trip links to `/trips/sun-tacos-and-tide-pools`, and a second fictional card), a bobbing "312 families forked" sticker, and a white button "Browse trips people loved" that goes to `/discover`.
4. **Not just a booking site**: four white feature cards with tilted icon tiles (Everything side by side · One honest total · Plan it together · Fork, don't start over).
5. **After you book**: a mint-tint panel with the calendar teaser (three day columns; booked blocks in ink).
6. **For creators**: an ink panel with a yellow button "Turn a link into a trip" that goes to `/creators`, and a fake link-paste preview.
7. **Shared footer.**

## States and rules
- The search form is a real `<form method="get" action="/plan">` with labelled inputs; the fields pass through as query params, and the workspace can ignore them for now.
- **Only the sample trip is real.** The second card in door two has no page yet, so link it to `/discover`.
- **Mobile ≤720px**: the headline shrinks to about 56px, the doors stack, the search fields go one per row, the feature cards go 2×2 then 1 column, and the teaser panels stack.
- **Motion**: the doors and cards pop in (spring, staggered 80ms), and the sticker bobs. Reduced motion turns all of that off.
- **Focus**: the system ring on every control.
- The two block colours #FF8A63 and #6DB8FF are hero-block tints. Add them to tokens.css as `--block-sunset` and `--block-pacific` and record them in DESIGN-SYSTEM.md (option B's hero blocks used the same values).
