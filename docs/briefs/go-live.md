# Feature brief: go live for our LA trip (deploy, polish, phone-first, better import)

Status: approved (2026-10-01, the captain: "Now we have to get real … I'm going to use this app next week")

## Why
- The design and backend work locally. The captain will use GitAway with family next week, on their phones, with Gmail sign-in. So it has to be live, feel cohesive and look good when empty.

## Phase 1: live and polished (now)
1. **Deployed on Railway.** A new project called "gitaway", with a persistent volume for the SQLite databases and a `*.up.railway.app` address.
   - Google sign-in works on the live site and locally. The dev sign-in is never on in production.
   - The captain adds the Google keys and the session secret as Railway variables.
2. **Stay signed in about 30 days** on each device, as a sliding session, so phones rarely ask to sign in again.
3. **Every control matches the house style.** Date pickers, dropdowns and number pickers look like GitAway: rounded corners, tokens, and touch sizes. The first place this was noticed is the trip dates on "Where to?". No browser-default widgets.
4. **"Discover" becomes "Community trips".** The page is clearly about trips shared by travelers and creators, with "Share yours" and "Turn a link into a trip" up front. The name "Discover" is kept for deals and promotions later.
5. **A sign-in page that makes you want to travel.** Emotional, animated and fun, while still quick and accessible. Reduced motion stays calm.
6. **Good when empty.** A brand-new family sees a warm first-run path: start a trip, import a booked trip, or browse community trips. There are no blank or broken screens.
7. **A phone-first trip view.** It's designed first for the captain's sign-off, then built:
   - "Today" with what's next
   - a swipeable list of days
   - flight and hotel cards
   - add a plan in two taps
   - notes

   It works as an installed home-screen app.

## Phase 1.5: getting a booked trip in, easily
- **A guided trip builder.** A few friendly questions (where, when, who, flights, hotel, car) produce the same trip as the template, with no YAML.
- **Expedia confirmation import.** Paste an Expedia confirmation email and GitAway pre-fills the trip for review. This needs a real sample email from the captain, with private details removed or kept local. More booking sites later, as templates.

## Later (noted, not now)
- Face ID sign-in with passkeys, after the first Google sign-in.
- Location while the app is open ("you've landed, here's your hotel") and time-based reminders as web push. Background geofencing needs a native app.
- **Phase 2:** real inventory and booking. Research free or cheap travel APIs and the Expedia partner and payment models (who is the merchant of record, commission). Stripe comes after that model is clear.
- AI for the creator import.

## Done means (phase 1)
- The captain signs in with Gmail on the live Railway address, on desktop and an iPhone (installed to the Home Screen).
- They see a good empty state, build or import the LA trip, invite family who sign in with Gmail, and plan together.
- A redeploy keeps all data.
- The date pickers and dropdowns look like GitAway.
