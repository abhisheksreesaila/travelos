# Design handoff: booking workspace (F-015; F-016 adds the context panes)

**Chosen:** "Booking workspace (polished)" (captain, 2026-09-29). Artboard source: `docs/design/canvas/Workspace-Polish.dc.html`. Every colour is a token; `Workspace.dc.html` is the earlier rough version.
**System:** `design-system/DESIGN-SYSTEM.md` (Pane, Offer card, Tactile button, Focus). Re-implement it in FastHTML with a small plain-JS module; don't paste the artboard markup.

## Layout (desktop, full viewport height)
1. **Top bar**: GitAway mark, a trip pill (`SFO → Los Angeles · Fri Oct 16 – Tue Oct 20 · 2 adults, 2 kids · Change`), the hint "Press 1–7 to focus a pane", and an avatar placeholder. Use the full shared header only on public pages; the workspace gets this compact bar with a link home through the mark.
2. **Cost ledger** (white, radius 28): three slots, Flight + Stay + Getting around = Total. Each slot shows its icon tile, label, name and price. The total uses 44px display type, with "4 people · taxes & fees in" under it and a chip: "The cheapest combination" (mint) or "$X more than the cheapest combo" (sun tint). Then an ink pill button, "Book this trip".
3. **Panes grid**: Flights | Stays | Getting around | context column. The context column holds Weather, Map, Happening & news and Trips others loved; **F-016 fills it**. F-015 renders it as a quiet placeholder pane.
   - **Pane header**: a number key badge, a title button that focuses the pane, a count, and an expand button.
   - **Focused pane**: a 3px ink ring and a wider column (columns: flights `1.45fr 1fr 0.8fr 1fr`, stays `1fr 1.45fr 0.8fr 1fr`, cars `1fr 1fr 1.2fr 1fr`, animated 300ms).
   - **Keys 1–3** focus Flights, Stays or Getting around (4–7 are reserved for F-016). **Expand** makes a pane full width until Esc.
4. **Offer cards**: radius 20, fill #FAF7F2. Selected is fill #FFF4EF with a 3px coral ring and `aria-pressed="true"`. Hover lifts 2px.
   - **Flights**: name, badge, price, big times line, detail.
   - **Stays**: area photo (captioned as the area, never the hotel), name, detail, tags, price and rating.
   - **Getting around**: name, detail, price, plus the sun-tint tip card.

## Behaviour
- Prices, totals and the cheapest-combo difference come from `gitaway/catalog.py` (`quote`, `cheapest`). The server renders the initial ledger for the default pick (f1, h1, c1).
- Picking an offer updates the ledger instantly. Use either HTMX partial swaps of the ledger (FastHTML already ships htmx) or a small JS module with the catalog data embedded as JSON. Either way the numbers must equal `catalog.quote`.
- Keep the picked combination in the URL (`?f=f1&h=h1&c=c1`) so a reload keeps it.
- "Book this trip" leads to F-018's pay sheet. Until then, link it to `/signin?next=<current workspace url>&intent=pay`.

## States
- **Phone ≤720px**: the panes stack in order Flights, Stays, Getting around, then context, and the ledger is pinned at the bottom as a compact bar (total plus Book button) that expands on tap.
- **Loading**: skeleton offer cards using the system skeleton values.
- **Empty lane** (a filter would hide everything, for later): "No flights match. Try another time of day."
- **Reduced motion**: no column animation, no lift.
- **Focus**: the ring on every control. Focusing a pane by key moves keyboard focus to its first offer.

## Update (F-031): the ledger is a slim line in the top bar
The ledger band is gone. Beside the trip pill sits one line: flight · stay · car = total (a button) and Book. Tapping the total opens a popover with the itemized lines (stay sub-line with rooms and add-ons) and the best-value chip; Esc or a tap outside closes it. In the split view, scrolling the detail down shrinks the line to a pill (total + Book); scrolling up or tapping it restores it (instant with reduced motion). Between 826 and 1100 the line keeps only total + Book; on a phone the same total + Book pill is pinned at the top. Figures come from `/plan/quote`; the JS does no arithmetic.
