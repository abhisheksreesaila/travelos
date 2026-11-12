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

## Flights (from the docs; not yet called)
- Search takes a `legs` array (origin, destination, date per leg; no top-level origin), plus `currency` and `country`; `Accept: text/event-stream` streams offers as they arrive, which suits a matrix that fills in.
- An offer: `offerId` (verbatim), `expiration`, `baggage.included`, `isCheapest`, `fareFamily`, cabin; `fareBasisCode`/`bookingCode` are internal.
- Then verify (`offerId` → fresh price, `changes`; 404 = expired), prebook (passengers, contact, `usePaymentSdk: true`), `/bookings`.
- The sandbox has only the test airline ("Nuitee Air"); real carriers need production flight access.
