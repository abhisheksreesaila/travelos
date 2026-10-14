# Design handoff: the web trip pages (option A)

Brief: docs/briefs/web-trip.md · Board: docs/design/canvas/Web-Trip-v1.html (frames A1–A4; B and C were not chosen)
Captain, 2026-10-13: "A: grid with a panel on the right … is what I like".

## Layout (viewport ≥ 1020px; 721–1019 keeps today's tablet layout with sheets; the phone is unchanged)
- **Top bar** (all signed-in pages): brand · a pill nav Trip | Family | Ask (coral mic dot, `/` key hint) · spacer · trip picker (sun tint dot, trip name, dates, chevron) · SOS pill (bubble tint) · avatar. Height 58 at 1440 (design 4.8rem at the 12px root). The signed-out landing keeps `site_header`.
- **Body**: two columns, `minmax(0,1fr)` + panel (design 404 at 1440, 372 at 1280), gap 18, side padding 28 (22 at 1280). Nothing scrolls but the grid and the panel body.
- **Day header**: the phone's ink card (radius 22) with the yellow eyebrow and day title, the five day chips inline (selected = white chip, coral-deep number), Day | Week switch, map button.
- **Filters row**: the phone's pills on the left; "Paste a plan" (white tactile) and "Say the plan" (coral tactile) on the right.
- **Grid**: a white card (radius 22, shadow md), hour rows with half-hour dashes, starts at 7 AM (or scrolled to now during the trip), a fade at the bottom. Booked = paper-2 with a dashed hairline and the "Booked" pill; plans = day-colour tints with the display title and step chips (done = struck through). Selected = 3px coral ring. Hover = shadow lg, a ⋯ button and the resize knob. Now = a coral line with a coral-deep time pill at the right.
- **Panel**: a white card with tabs Plan · Family (unread count) · Ask, a scrolling body and a fixed compose bar.
  - Idle (nothing clicked): the ink "Up next" card (eyebrow "UP NEXT · IN 20 MIN", title, time · drive · who, Directions + Open the plan), "Later today" rows, the Ask box with suggestions and the mic.
  - Plan: the plan card (icon tile, eyebrow with day and time, title, `esc` hint and close), who faces, the note slip (Caveat on sun tint), steps as tick rows (Reminders style, meta on the right, "Add a step", "Set aside (n)"), the plan's chat and compose.
  - Family: the trip's chats (whole trip first, then per plan, unread badges), the open thread below, compose.
- **Week**: the ink header (trip name, filters, Day | Week), five columns as white cards with a day-colour header (deep ink number), compact rows (time · title on at most two lines · kind icon), plans on paper-2 with a step/message summary, a dashed "Free day" card with "Say the plan", today outlined in ink, "Open the day" at the foot.

## Tokens and components
Only `design-system/DESIGN-SYSTEM.md` and `assets/css/tokens.css`: ink, ink-2, ink-3, paper, paper-2, card, coral/coral-deep, the five day tints and their deep inks, shadow sm/md/lg, radius 12/16–22/28/999, Bricolage for titles and numbers, Figtree for the rest, Caveat for the note slip only. Tactile button, sticker-free. The panel swap and the card opening use `GA.motion` and the `--motion-*` tokens (no new timings). Sizes in rem.

## States to build
- Empty: a free day (dashed card + Say the plan), a trip with no plans, an idle panel with nothing up next ("Nothing else today" + Ask).
- Loading: the panel shows the plan's outline at once (title from the tapped block) and fills in, as F-135 does on the phone.
- Error: a failed write puts things back with the existing toast.
- Long content: titles wrap (no ellipsis); a long chat scrolls inside the panel; a trip longer than five days scrolls the week sideways inside its area.
- Viewer role: no drag, no ⋯, no compose for writes they can't make (existing access rules).
- Smaller widths: 721–1019 is today's layout; ≤ 720 is the phone app, untouched.
