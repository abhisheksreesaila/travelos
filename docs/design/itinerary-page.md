# Design handoff: scrapbook itinerary page (F-011 → F-014)

**Chosen:** Option A, Scrapbook Journal, with option B's all-days board in place of the small glance strip (captain, 2026-09-29).
**Canvas:** https://claude.ai/artifact/NvLT3Tjf4XUwPbyZ4m6d2Q, artboard "A · Scrapbook Journal + board (chosen)". Option B stays on the canvas as reference only.
**Artboard source (offline copy):** `docs/design/canvas/Main.dc.html` (chosen), plus `Board.dc.html` (option B), `Brand.dc.html`, `Workspace.dc.html` and `Journey.dc.html`. Photos are the archived CC0/public-domain images `santa-monica-beach-pier.jpg` and `venice-beach-los-angeles-hero.jpg` (branch `archive/travelos-prototype`, `assets/photos/compass/`).
**Tokens and components:** `design-system/DESIGN-SYSTEM.md` (the artboard is a reference to re-implement in FastHTML and plain JS, not code to ship).

## Page, top to bottom
1. **Nav**: GitAway mark and wordmark, Discover · Plan a trip · For creators, Sign in.
2. **Hero** (7/5 grid): place pill; display title with a hand-drawn accent-2 underline; lede; three sticker tags; four stat cards (days, people, all-in cost, forks); tactile Fork, Share and Save buttons; creator source card (video thumbnail with play button, "From the vlog", title, channel, "Watch the original"). Right side: two taped polaroids, a dotted flight route with a plane badge, a bobbing weather sticker, and an "SFO → LAX" stamp.
3. **Whole trip on one board**: five tinted day columns with a big day number, date, title and tilted mini stop cards (ink for booked). A column links to its day story.
4. **Day stories**: 280px left rail (tilted day badge, date, title, weather) and a white card with a dotted timeline: time, icon bubble, title, BOOKED or tag pills, meta, optional Caveat note, optional tilted photo. Later days collapse into "Open day" cards.
5. **Make this trip yours**: tint panel with Fork and Plan my own buttons, plus a stacked "Your forks" card preview.
6. **Footer** with the price disclaimer.

## States to build
- **Themes**: Sunset and Pacific switch with no layout change.
- **Loading**: a skeleton of the hero and board, using the exact values under Motion › Skeleton to itinerary in the system file. Days cross-fade in (this is also the creator-import reveal in F-023).
- **Focus**: every control shows the system focus ring. Board day columns and "Open day" cards are links and must show it too.
- **Empty or short**: a one-day trip hides the board; a day with no stops says "Free day, nothing planned".
- **Long content**: titles wrap with `text-wrap: balance`; more than 6 stops a day collapses to "Show all N stops"; the board shows at most 4 mini cards per day, then "+N more".
- **No photo or creator**: an everyday traveler's trip has no source card and no polaroids; the collage falls back to illustrated stickers.
- **Error**: an itinerary that isn't found shows a friendly "This trip wandered off" page with a link to Discover.
- **Mobile (≤ 720px)**: the hero stacks with the collage below the buttons; the board becomes a horizontal swipe row; the day rail sits above its card; tactile buttons stay 56px.
- **Reduced motion**: no bob, no pop, instant reveal.

## Adopted into the system
GitAway now has its own system (`design-system/DESIGN-SYSTEM.md`) instead of the house Terminal Ledger style. The workspace artboard is a rough density test only and gets its own polish pass before F-015.
