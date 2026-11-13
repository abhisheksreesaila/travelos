# LiteAPI (Nuitée): what the sandbox actually answers

Checked 2026-11-12 with the sandbox key (`LITEAPI_KEY`, `sand_…`). Base `https://api.liteapi.travel/v3.0`, header `X-API-Key`. Docs moved to docs.nuitee.com (reference index: docs.nuitee.com/llms.txt).

## Hotels
- `GET /data/hotels?countryCode=US&cityName=San Diego&limit=N` → `{data: [hotel], hotelIds, total}`. A hotel: `id` (`lp…`), `name`, `hotelDescription` (HTML: strip before showing), `address`, `city`, `zip`, `latitude`, `longitude`, `stars`, `rating` (0–10), `reviewCount`, `main_photo`, `thumbnail` (static.cupid.travel), `facilityIds`, `chain`, `accessibilityAttributes`.
- `POST /hotels/rates` with `{cityName, countryCode, checkin, checkout, currency: "USD", guestNationality: "US", occupancies: [{adults, children: [ages]}], limit, timeout}` → `{data, hotels, guestLevel, sandbox: true}`.
  - `hotels[]`: the hotels answered, with `main_photo`, `latitude`, `longitude`, `rating`, `stars`, `review_count`.
  - `data[]`: `{hotelId, roomTypes: [{offerId, offerRetailRate {amount, currency}, suggestedSellingPrice, offerInitialPrice, paymentTypes, rates: [...]}]}`.
  - A rate: `name` ("Standard Room, 2 Queen Beds"), `maxOccupancy`, `adultCount`, `childCount`, `childrenAges`, `boardType`/`boardName` (`RO` Room Only; breakfast is a board), `retailRate {total, suggestedSellingPrice, initialPrice, taxesAndFees [{included, description, amount}]}`, `cancellationPolicies {refundableTag: "NRFN"|…, cancelPolicyInfos}`, `paymentTypes ["NUITEE_PAY"]`, `perks`, `promotions`, `priceType: "commission"`.
  - The total is for the whole stay and the whole party, taxes included (San Diego, Dec 12–16, 2 adults + kids 7 and 10: $597 to $1,181 across 5 hotels).
- `offerId` and `rateId` are long opaque strings: store verbatim, never show.

## Flights (called 2026-11-12, F-220; recorded in tests/fixtures/liteapi)
- `POST /flights/rates` with `{legs: [{origin, destination, date, direction: OUTBOUND|INBOUND}], adults, children, childrenAges, infants, infantAges, currency: "USD", country: "US"}` (no top-level origin). SFO⇄SAN Dec 12–16, 2 adults + kids 7 and 10: 200 in 16 s (2 s when asked again), 9 MB, 386 journeys, 1,647 offers.
- Answer `{data: [{journeys, sortMetadata {best, duration, …: {journeyKey, offerId, price}}, searchId, sessionId}]}`. A journey: `journeyKey`, `isCheapest`, `segments[]`, `legDurations[] {direction, duration {minutes}, dayChange, overnightFlight}`, `totalDuration`, `cheapestOffer`, `offers[]`.
  - A segment: `direction`, `originCode`, `destinationCode`, `departureTime`/`arrivalTime` (local, no zone: "2026-12-12T16:33:00"), `duration {iso8601, minutes}`, `carrier {marketingCode, marketingName, operatingCode, …}`, `flight {marketingNumber}`, `stopCount`. A connection is two segments in one direction.
  - An offer: `offerId` (opaque, verbatim), `expiration` (about 10 minutes after the search), `pricing.display {total, currency, base, taxes, fees, perPassenger {adult, child, infant}}` (the total is the party's), `baggage {hasCarryOnBag, hasCheckedBag, included[], paid[]}` (description, pieces, weightKg), `fare {family, seatsRemaining}`, `terms {refundable, changeable, summary[]}`, `segmentFares` (bookingCode, fareBasisCode: internal).
- The sandbox answers real carriers (United, American, Delta, Alaska, Frontier) besides the test airline Nuitée Air (`ND`), at test prices ($114.84 to $9,187.26 for the party).
- `Accept: text/event-stream` answered `event: rates-complete` and one `data:` line holding the whole answer (the same `data[].journeys`).
- Streamed again on 2026-11-12 (F-229, `scripts/probe_liteapi_stream.py`, recorded trimmed in tests/fixtures/liteapi/flight_rates_stream.sse with its arrival times): `event: rates-chunk` messages, each `data:` a whole answer `{data: [{journeys, sortMetadata, searchId, sessionId}]}` holding only that chunk's journeys (a journey can come again in a later chunk, a few cents apart), then `event: rates-complete` with every journey. Times: 1 journey (Nuitée Air) at 0.2 s, 141 and 172 at 5.7 s, 200, 200 and 47 by 9.9 s (the cheapest, $76.60, in the last), complete at 10.5 s; another run complete at 13.9 s; two runs hung (headers at 10 s, then nothing for 25 s). `filters.showCheapestOfferOnly: true` keeps one offer a journey.
- Then verify (`offerId` → fresh price, `changes`; 404 = expired), prebook (passengers, contact, `usePaymentSdk: true`), `/bookings`.

## Hotel details and errors
- `GET /data/hotel?hotelId=lp1f5cb` → `{data: {id, name, hotelDescription (HTML), main_photo, thumbnail, starRating, rating, reviewCount, location, address, …}}`.
- A bad request is HTTP 400 `{"error": {"code": 4000, "description": "...", "message": "bad request"}}`.
- A hotel rate's `taxesAndFees[]` can hold a fee with `"included": false` (a $160 resort fee in San Diego): paid at the hotel, not in the total.
