# Brief: the trip canvas (plans with steps, Paste & Convert, passes)

Status: approved (captain, 2026-10-04: "I like the design… this is pretty much what I was looking for… go ahead and build it")
Designs: docs/design/canvas/Plan-Steps-v1.html (steps in lanes, touch editing, dictation, passes & documents, gate passes) and docs/design/canvas/Trip-Canvas-v2.html (Paste & Convert, one zoomable trip canvas, notes on blocks, Set aside tray, filters, speak, Ask). Both boards apply.

## Why
The family plans park days in long iMessage texts: two parks in one stream, no dates, lists sent twice, notes buried mid-line, initials instead of names. During the trip (Oct 4–10, 2026) the plan must be visual, structured and changeable on the phone, with each note on the block it's about, and the family told about changes.

## What
1. Paste & Convert: paste the messages as-is (or dictate) → park days, areas, rides/steps, notes kept on their item, skips set aside, repeats merged, named lists (e.g. "Pregnancy-safe rides") → asks who the initials are and which day each park is → nothing saved until "Add to trip". Uses the Azure OpenAI model.
2. Plans with steps: a calendar block (e.g. a park day) holds parts (areas or morning/afternoon/evening) and steps (rides, meals, meet-ups) with a time (optional), who (people; Everyone/Adults/Kids), a note, done, set aside.
3. One zoomable trip canvas: week → day → block → step, replacing the separate trip and calendar pages on the phone; notes on blocks; a Set aside tray; Mark done.
4. Semantic zoom with a subtle, fluid animation (Apple-like): pinch or tap and a summary grows into its detail and back, instead of a pane popping open.
5. Touch moves and filters: drag a step to another time, part, day or the tray, with Undo; filter by who and by lists.
6. Passes & documents: per-traveller flight, seat, group, gate, boarding time and the boarding pass file, family only; full-screen gate passes to swipe through.
7. Speak a change and Ask with search (Azure), each shown as a proposal; Apply tells the family.
8. Every AI call logged by job for the post-trip review (F-079).

## Not now
Booking, community, the airline Wallet pass itself (the airline app provides it).

## How we'll know
The captain pastes the real Universal and California Adventure messages on the phone, gets the two park days, uses them in the parks, and gives live feedback.
