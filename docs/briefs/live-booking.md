Status: draft (phase 2 of docs/briefs/live-liteapi.md; founder's answers 2026-11-16)

# Real booking on gitaway.me

## Why
- The founder wants to book their own Lake Tahoe trip end to end on gitaway.me today, to prove the experience before anything else: "I want to go end-to-end and finish it for myself first … then you can worry about multi-users."

## Who
- **First:** the founder, booking a real family trip.
- **Then:** any signed-in family. The founder chose "anyone signed in" over a founder-only switch.

## What it does
1. **Hotel.** An opened square's Book takes the person through LiteAPI's own secure card form (the User Payment SDK).
   - Nuitée is the merchant of record; GitAway never sees, sends or stores a card.
   - The flow: prebook with `usePaymentSdk: true`, LiteAPI's payment form with the returned `secretKey`, then book with `payment: {method: "TRANSACTION_ID", transactionId}`.
   - The `transactionId` and `prebookId` are saved as soon as prebook answers. LiteAPI cannot give them back later.
2. **Flight.** The flight is booked here too, through LiteAPI's flight prebook and booking, with the same payment form. This is decided, but it's more work and lands after the hotel.
   - Each product is its own payment, unless LiteAPI allows one transaction for both. Check that while building.
3. **The price charged matches the public price the square shows.**
   - GitAway's margin is set so the charge equals the shown price.
   - Every price is checked again at prebook, and any change is said before paying.
4. **After booking.**
   - A confirmation page with LiteAPI's booking ids.
   - The trip joins the calendar (as today's sandbox flow does).
   - Cancel in-app where the rate allows, through LiteAPI's cancel.
   - LiteAPI's or the hotel's confirmation email is the receipt.

## Out of scope today
Group or multi-room bookings beyond one room, gift cards, and our own payments.

## Look and feel
- The approved matrix v3 checkout (docs/design/matrix-v3): "Book this trip" is the boldest control.
- The checkout states the total, the refund policy word for word, and who sells it ("Sold by Nuitée through LiteAPI").
- LiteAPI's card form sits in our sheet.

## Success
- The founder books their real Tahoe stay (and flight) on gitaway.me, sees it on their calendar, and gets the confirmation email.
- A test booking with a refundable rate is cancelled in-app and the refund is shown.

## Risks (Risk: high for this work: money, personal data, sign-in)
- **Real charges.** Tested first in sandbox with the same SDK flow (the sandbox `publicKey: 'sandbox'`), then live.
- **Never `ACC_CREDIT_CARD` with a live key.** That charges the founder's own account card. A test enforces it.
- **Open to anyone signed in.** The founder accepts this. Per-person and site booking limits stay (D-510..D-513).
- **Guest data.** Name and email go to LiteAPI only, are validated and never logged (D-485).
- **Review.** The security-auditor reviews alongside the reviewer.
- **Deploy.** It needs the live key on Railway and a deploy, both on the founder's "deploy" (docs/ship/live-prices.md, extended for booking).

## Decisions and trade-offs
| Decision | Pro | Con |
|---|---|---|
| Book on gitaway.me | Proves production | A deploy today |
| Anyone signed in | No switch to manage | Strangers' money before the experience is proven |
| Charge the public price (margin) | Consistent, and we earn | The founder pays about 13% more for their own trip |
| Flights here too | One place to book | More work and more to test; hotel first |

## Open questions
- Whether LiteAPI's payment form can take one transaction for hotel plus flight.
- The exact margin value that makes the charge equal the public price. Check against a sandbox and a live prebook.
