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

## Not now
- Paid plans and creator discount codes.
- Checkout inside GitAway of any kind (Expedia Rapid, LiteAPI, Duffel). GitAway stays a front door, not a seller.
- Native app-store apps.

## How we'll know
- The captain plans and books the Tahoe trip through GitAway, and the bookings land in the trip.
- The captain looks at every screen on their phone, in light and dark mode, and calls it polished.
- The first creators publish, and families fork and free-plan trips. Track readers, forks and partner clicks.
