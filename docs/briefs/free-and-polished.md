# Feature brief: free, polished, and booking that works anywhere

Status: approved (2026-11-07, the captain: "A with a mix here and there … lets prototype and then build").

## Why
- People won't pay for plans on a new site with no network. Paid comes later, through creators (for example a premium plan with a creator's discount code). First, get families and creators in and excited. Target: 100 plans added.
- The site costs about $20 a month to run, so free costs almost nothing.
- The look has the right colors but not the polish. Some type is too small (sign-in), the booking side looks unfinished, and it can't feel like "another travel site".
- The captain wants to plan and book their own family's Lake Tahoe trip in December on GitAway. If GitAway can't do that, it doesn't work.

## What
1. **Everything is free.**
   - "Plan it for me" becomes free, with a daily cap per person and for the whole site. It uses a cheap model, and the captain's check stays optional.
   - The Stripe code stays in place, switched off.
   - An honest "Early preview" label sits on the site.
2. **Reskin, without changing what anything does.**
   - Apple-like minimalism: a neutral gray canvas, with everything placed on it colorful and high-contrast.
   - Light and dark modes. 16px minimum body text and 48px tap targets on phones. The phone app is as good as the laptop.
   - The trip and booking panels are built from iPhone-style widgets: weather, what's next, flight, stay, car, tickets.
   - Orange is no longer required. The accent is chosen from the design directions.
3. **Plan themes.** A creator or reader picks one of four: Scrapbook, Structured, Magazine, Minimal list.
4. **Booking works for any destination, not just the four sample places.**
   - **Lanes:** flights, stays, car, and tickets or activities.
   - **Partners:** today the captain has Aviasales and Klook only. Each lane uses a paying partner when one is connected. Otherwise it shows a plain link to the best site, such as Expedia, Airbnb or Vrbo, with the search already filled in. A plain link uses no data and needs no agreement, but earns nothing. It switches to an affiliate link the day a program is approved. Klook is tried first for stays and things to do. When Klook has nothing for a place, the plain link takes over.
   - **Prices:** real cached prices where a free API allows it, and honest "search on the partner" cards everywhere else.
   - **Coming back:** a booking returns into the trip through a forwarded or pasted confirmation.
   - **The test:** the captain's Tahoe trip in December, end to end.
5. **Go live with the reskin.** The captain's Disneyland trip publishes at the same time.

## The soul: sharing
- The heart of GitAway is sharing a trip the way a developer shares a repo. Someone shares their memories and plans, others look, enjoy, build on them (fork), and say thank you to the person who shared. That's the GitHub feeling and the Linux-kernel feeling, applied to travel. Nothing else does this well today.
- A shared trip tells a story, like a short animated film: the route, the days, the moments. It's interactive and 3D (three.js) but light, around 100 to 200 KB, loaded only where the story is shown. It falls back to a calm still picture with reduced motion or on weak phones. Meng To's threeui (github.com/MengTo/threeui) is the starting point if its licence allows.
- Gratitude is part of the product: a reader can thank the sharer, the way people star a repo, and forks show where a trip went next.
- Widgets and booking are a convenience, not the pitch: colorful, complete, one screen.
- Look: Direction A (gray canvas, Apple-bright colors, light and dark) is the base, with B's ticket stub where it fits. omxqua is the system. Web and phone are designed together, web first if one has to wait.
- Order: prototype the 3D story, the captain picks one, then build.
- **Picked (2026-11-07):** the trip cockpit is Direction 3, Ticket line ("I cannot take my eyes off the ticket line"). Direction 1's diorama is a candidate for the shared-trip story. Direction 2's real street map loads only when someone taps for it.

## The line (the captain's pick, 2026-11-07)
- **Tagline:** "Take a trip. Leave a trail."
- **Subhead:** "Share the whole trip, not just the photos, so the next family can follow it, make it theirs, and say thanks."
- **The buttons speak the same language:** "Leave a trail" to share or publish, "Follow this trail" to fork, "Thank them" to say thanks. The word "fork" stays in the fork tree and in places for developers. "Fork a getaway" is the line for developers.
- **The cover page story** opens with "Don't read about it. Go." and closes with "Take a trip. Leave a trail."
- **The cover page concept** is A, the fly-through over Lake Tahoe in December, with B's fork tree ("Every trip here grew from another") as its last chapter. C's chase camera becomes a "drive this trip" moment on shared trip pages later.
- **The captain confirmed the fly-through and the recommendations: "the 3D needs to have good details."**
  - **The place itself:** real Lake Tahoe topography and shoreline, realistic water, a winter sky with low sun, sunset on the pier and stars at night.
  - **The props:** crafted models (cabin, pier, car, family), pines with snow on them, soft shadows, haze over distance, falling snow.
  - **Weight:** the code stays at 250 KB or less. Detail data can reach about 2 MB, loaded after the poster and only at the quality the device can hold.

## The model (the captain's call, 2026-11-07)
- GitAway is "the GitHub of travel": the place to plan a trip together, share it, and fork other people's trips. GitAway does not sell travel.
- **Booking is links only, with almost no liability.** Every booking happens on the partner's site, under the partner's terms and the partner's support. GitAway never takes payment and never handles a cancellation.
  - Each booking in a trip shows "Booked on <partner>". A "Change or cancel" button opens the partner's own manage-booking page.
  - LiteAPI, Duffel and acting as the merchant are off the table. They would turn GitAway into a support center.
- **What GitAway adds is one screen for the whole trip:**
  - weather
  - the plan
  - every booking, wherever it was made
  - the family's chat and calendar
  - the creator's tips
  - one tap to the partner for each lane
- **Money comes from the network:**
  - small affiliate cuts
  - creator and influencer brand deals
  - the content-creator market
  - travel ads, later, which are fine on a travel site
  - The worst case is the server bill.

## Later (ideas the captain named, 2026-11-07)
- **Cover page** as a 3D scroll world that tells the story ("Forget the book. Go travel.") in one real place. Prototypes are in docs/design/cover3d/.
- **Outreach** after the redesign: email about 50 people and ask them to contribute. The captain publishes first: their own real trips, posted anonymously.
- **Fin Explorer:** "connect your Fin Explorer account and see how much you can travel". A budget link to the captain's other product.
- **Money from the network:** ads on a travel site (no privacy cost), creator brand deals, the creator economy. Figure it out the way GitHub did, after the foundation is in.

## Not now
- Paid plans and creator discount codes.
- Checkout inside GitAway of any kind (Expedia Rapid, LiteAPI, Duffel). GitAway stays a front door, not a seller.
- Native app-store apps.

## How we'll know
- The captain plans and books the Tahoe trip through GitAway, and the bookings land in the trip.
- The captain looks at every screen on their phone, in light and dark mode, and calls it polished.
- The first creators publish, and families fork and free-plan trips. Track readers, forks and partner clicks.

## Season and weather you can feel (the captain, 2026-11-07)
- **The background shows the season** of the place on the trip's dates: winter snow, spring green, summer sun, autumn leaves. It applies to the cockpit, the shared trail, "Where to?" and the book of tickets.
  - The season is worked out from the destination and its hemisphere. Tropical places show wet or dry season instead.
- **Weather moves, gently:** a quiet animation of the real or typical weather, such as falling snow, rain, sun or wind. It's built on the cockpit's wx.js engine.
  - Reduced motion gets a still frame.
  - The animation is behind the text and keeps contrast.
- **No invented weather:** before the forecast opens, the background shows the season only. Weather animation shows only for real forecast days, or labelled typical weather.

## The cover, take two (the captain, 2026-11-07)
- **Why:** the first cover read like a wall of text over a gray world. People could not tell what GitAway is or what to do.
- **The story is flat illustration with large motion and a voice.**
  - A couple reads a guidebook, the book becomes a trip, and they go and love it.
  - They come back and leave a trail.
  - Someone else, far away, discovers it on GitAway, follows it, tweaks it a little, goes, and shares it back.
  - The world keeps filling with trails and happy travellers.
- **3D shows the beauty of the place:** the real Tahoe flyover while they are there, and a real globe lighting up with trails at the end.
- **Every screen says what GitAway is and what to do.** A bar with "Take a trip. Leave a trail." and Start a trip is always visible.
- **Voice:** a warm narrator reads short lines, in sync with the motion and with captions shown. The page starts silent (browsers block sound until a tap), and a clear "Play with sound" button turns the voice on.
- Prototypes are in docs/design/cover-v2/ (A to D, then E with motion and voice).
