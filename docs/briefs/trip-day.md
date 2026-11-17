Status: approved (founder, 2026-11-17: "agreed. proceed with wallet pass and today … go with your recommendation")

# The trip, in your pocket: Today and the Wallet pass

## Why
Booking is the middle of the journey, not the end. On the day itself people need the next thing and nothing else: when to leave, where the hotel is, the confirmation code, a ride, the weather. Today, they dig through emails. The founder's ask: "on the mobile we can get location and prompt them with wallets, boarding pass, or notify at least". The recommendation he approved: a Wallet pass for the stay, plus a travel-day "Today" screen.

## What it does
1. **Today** (`/trip/today`, and a card at the top of My trip while the trip is near or under way).
   - **Before the trip:** a countdown and what to do now. For example: flight check-in opens 24 h before (a link to the airline's check-in), packing weather.
   - **On a travel day,** the next thing first:
     - the flight, with times and a "leave by" time from the airport drive estimate, said as an estimate;
     - then the hotel: address, check-in time, the confirmation code, directions (an Apple or Google Maps link), a ride (the Uber deep link we already make), and today's weather;
     - who to call: the hotel's number only if a source gives it; otherwise the booking's support line (Nuitée/LiteAPI) with the code.
   - **During the stay:** today's plans from the calendar, the hotel card and check-out time.
   - **Location only on a tap:** "Use my location" works out the distance and time to the hotel while the page is open. It is never stored or sent anywhere except the routing it asks for.
   - **Works offline** once opened: the service worker keeps the day's page, so codes and addresses show without signal.
2. **Wallet pass for the stay.**
   - "Add to Apple Wallet" and "Save to Google Wallet" on the booking page, the pass, the confirmation email and Today.
   - The pass carries: hotel, address, dates, guests, the confirmation code (also as a QR code of the code itself), check-in and check-out times, and a link back to the booking.
   - Apple: `relevantDate` (check-in) and `locations` (the hotel's coordinates), so iOS surfaces it on the lock screen near the hotel or near check-in. Google: the equivalent fields Google supports.
   - Real boarding passes come only from airlines. The flight shows as a card with the airline's check-in link.

## Rules
- **Never invent:** a phone number, gate or time is shown only when a source gives it; the leave-by time is labelled an estimate.
- **Personal data:** a pass holds only what the booking page already shows to its family. Pass downloads are signed per booking and per family, and never reachable by a guessable address.
- **Credentials:**
  - Apple passes need an Apple Developer Pass Type ID certificate.
  - Google passes need a Wallet issuer account and a service account key.
  - Until they are set, the buttons don't show, and the code is built and tested with test keys.
  - A setup script walks the founder through creating both.

## Out of scope now
- Push notifications (next, after this).
- Live flight status, gates and delays (needs a paid feed).
- Background geofencing (needs a native app; the Apple pass's locations do the lock-screen part).
- Boarding passes.
