# Nuitée (LiteAPI) beyond what we use: a use-case map (read 2026-11-18)

Read from the docs only, no API called. Index: https://docs.nuitee.com/llms.txt (one file, about 330 entries, read in full). Every page below is the `.md` form of the URL given. This page skips what `liteapi-shapes.md` and `liteapi-payment.md` already say (payment form, margin, vouchers, cancel, invoice URL). **Unverified** marks anything the docs do not say.

## Summary

| # | Use case | Supported? | How | Effort for us |
|---|---|---|---|---|
| 1 | Price-drop guardian (rebook a refundable stay when it gets cheaper) | **Partly.** There is no automatic price-drop product. The docs give the pieces, but who gets the saving is not documented | Detect the drop: `POST /hotels/rates` for the one hotel, or `POST /bookings/{id}/alternative-prebooks` with the same dates (it returns `priceDifferencePercent` against what was paid). Rebook: `POST /rates/rebook` (takes no payment, cancels the original by itself, "price delta settled out of band"), or a new booking with the guest paying again followed by a cancel of the old one | M for detect and alert. Fully automatic rebooking needs Nuitée to answer in writing who receives the difference |
| 1b | `booking.rebook.rfn` / `.nrfn` / `booking.amendment` | Webhooks for changes Nuitée support agents or the hard-amendment API make | Subscribe in the dashboard | S |
| 2 | Trip guardian (disruptions) | **Yes for flights**: `flight.book.schedule_changed`, `flight.book.provider_notification`, `flight.book.compensation`, and Nuitée's 24/7 desk acts on the change. **Hotels**: `booking.checkinInstruction`, `booking.book.hotelConfirmationNumber`, relocation and compensation events. No API to message a hotel | Dashboard-registered HTTPS webhook. A static `authorization` token, plus optional HMAC (scheme undocumented). The envelope's `request` and `response` are stringified JSON | M (one receiver, dedupe on `event_id`) |
| 3 | Experiences (tours, activities) | **Yes, on request** (sandbox and production each need enabling) | `/experiences/tours…` → `booking-options` → `prebooks` (Stripe PaymentIntent) → `POST /experiences/bookings` with `TRANSACTION_ID` → async `CONFIRMED` and voucher via webhook | M-L. Payment is raw Stripe.js `confirmCardPayment`, not the LiteAPIPayment wrapper |
| 4a | eSIM | **Yes.** As a hotel add-on paid in the same card charge, or as standalone eSIMply orders | `addons: [{addon:"esimply",…}]` on prebook, or `/addons/esimply/...` cart and order | S as an add-on |
| 4b | Ground transport | Uber ride vouchers only ($10 to $100, USD, as an add-on). No cars, no transfers | `addons: [{addon:"uber", value:20, currency:"USD"}]` | S |
| 4c | Insurance, saved cards, cart across hotel + flight + tour | **Not found** | None (the add-ons are the only bundling) | n/a |
| 4d | AI tools | Yes: semantic hotel search, `aiSearch` on rates, room search by image, "ask a hotel", AI highlights ($0.02), an MCP server with 127 tools, an embeddable chatbot | See section 4 | S each |
| 4e | Market data | Price index per city or hotel (beta, paid), cached **public price from Booking.com/Expedia** (beta, $0.02), weather | See section 4 | S |
| 4f | Multi-room | Yes, one booking with several `occupancies`. Group-booking product: not found | Existing rates/book | Already possible |
| 4g | White-label site, loyalty, SSO | Yes (no-code site, cashback loyalty API, SSO magic link) | Dashboard | Not for us |
| 5 | Business expense | Partly: invoice PDF per booking, `customTags` (5 key:value) filterable on the list, `GET /bookings` date filters, text search, analytics reports. **No VAT breakdown on the invoice is documented**; there is a per-hotel tax schema | `customTags` on book; `GET /bookings?customTags=K:V` | S |
| 6 | Guest emails from Nuitée | API + Payment SDK: **Nuitée sends nothing. We must send** confirmations. The white-label site and External Checkout do send email (suppressible only in headless External Checkout). Flights: the airline may email the traveller if their contact is on the PNR | n/a | We already send (F-285) |

## 1. Price-drop guardian

**There is no automatic price-drop rebooking by Nuitée** in the docs. No page names a product, toggle or fee for it. A web search found Nuitée's "rebooking" wording only for airline disruptions; the price-drop rebooking products found belong to other vendors (Gimmonix RateFox, Hotelmize, Vervotech). Treat "Nuitée does not offer it" as likely but **unverified**, and ask support.

**What `booking.rebook.rfn` / `booking.rebook.nrfn` are.** They are booking-management webhooks for when a booking is replaced, not price-drop alerts. https://docs.nuitee.com/docs/using-liteapi-webhooks:
> "If you have agents on your account who handle support, these webhooks allow you to track amendments and related actions on existing bookings.
> `booking.rebook.rfn` — A refundable room is rebooked
> `booking.rebook.nrfn` — A non-refundable room is rebooked
> `booking.amendment` — Changes to the booking information, like guest name or special requests
> `booking.amendment.relocation` — Due to unforeseen circumstances, the guest is relocated
> `booking.refund` — A refund is issued for the booking
> `booking.compensation` — Compensation is given to the client"

> "there are **no** separate `_error` events for amendments, rebooks, refunds, compensation"

The payload shape of these events is not documented (**unverified**).

**The API that re-shops an existing booking is the "hard amendment".**

`POST https://book.liteapi.travel/v3.0/bookings/{bookingId}/alternative-prebooks` (https://docs.nuitee.com/reference/post_bookings-bookingid-alternative-prebooks):
- The body needs only `occupancies`. Optional fields: `checkin`, `checkout`, `refundableRatesOnly` (it defaults to true when the original was refundable), `boardType`, `maxPrebooks` (default 3, max 10). So we can send the **same** dates and occupancy and ask "what does this hotel cost now?"
- > "The system searches for live availability at the same hotel with the new parameters. Up to `maxPrebooks` alternative rates are selected (sorted by price ascending)… A prebook session is created for each rate."
- > "`priceDifferencePercent` shows how each alternative compares to the **original booking's selling price** (negative = cheaper than what the guest paid…)". It also returns the flags `cancellationChanged` and `boardChanged`.
- > "**Payment type is honoured** … every other booking (including pay-later, succeeded, credit_line) only sees `NUITEE_PAY` alternatives." The booking must be `CONFIRMED`; it uses the original booking's nationality and currency.
- It is "same hotel", not "same room": we have to match the room name or mapped room and the board ourselves. Each call **creates real prebooks** (up to 10), so it is heavier than a rates search for frequent polling.

`POST https://book.liteapi.travel/v3.0/rates/rebook` (https://docs.nuitee.com/reference/post_rates-rebook):
- Body: `prebookId` (from alternative-prebooks), `existingBookingId`, `holder` (empty fields are copied from the original), `guests`, `payment: {"method":"NONE"}`, and optional `clientReference` (idempotency, 4005) and `customTags`.
- > "On success, the new booking is created **and the original booking is automatically cancelled**"
- > "No payment is collected on this endpoint. … the server forces the method to `NONE` internally. **Any price delta between the original and new rate is settled out of band.**"
- > "**Refundable original** — Returns `200 OK` with the new booking… **Non-refundable original** — Returns `202 Accepted`… queued for the Nuitee operations team to handle manually"
- > "Pay-at-property bookings are not supported." Errors: "rebooking is not allowed for this offer" (4000), already completed (409/4009). If cancelling the original fails, "the error is logged but the new booking is still returned — contact support to reconcile."
- The new booking carries `rebookFrom` (also on `GET /bookings/{id}`).
- **Unverified, and blocking for automation:** for a guest who paid through the Payment SDK (Nuitée is merchant of record), the docs do not say whether the guest's card is partly refunded, whether the saving goes to our account, or whether our commission is recomputed. They also do not say whether Nuitée emails the guest about a rebook, whether it charges a fee (the pricing page lists none for hotels), or whether the sandbox supports these two endpoints.

**The fully documented alternative** uses the flows we already have. Re-shop with `POST /hotels/rates`, sending `hotelIds:[id]`, the same dates and occupancy, `boardType`, `refundableRatesOnly:true` and `roomMapping:true` (`mappedRoomId` matches the room). On a drop, ask the guest to approve. They pay the new price through the Payment SDK (a new prebook and book), and then we cancel the old booking before `lastFreeCancellationDate`, which refunds their card. This costs the guest a second card entry, and it costs us nothing extra (the core flow is free within a 5000:1 search-to-book ratio, https://docs.nuitee.com/reference/api-pricing-usage-costs). Commission is earned only after checkout (https://docs.nuitee.com/docs/revenue-management-and-commission: "Once this happens, your commission will be locked in"), so the cancelled booking earns nothing and the new one earns its own margin.
- Note: `/hotels/min-rates` "is not covered by price consistency. Its price can differ from `/hotels/rates`" (https://docs.nuitee.com/reference/post_hotels-min-rates). Use it for a cheap first look, and confirm with `/hotels/rates`.
- The fields on the booking that drive the guardian (`GET /bookings/{id}`): `lastFreeCancellationDate`, `cancellationPolicies.cancelPolicyInfos[]` (`cancelTime` in GMT), `refundableTag`/`tag` (RFN/NRFN), `bookedRooms[].roomType`, `boardType`, `price`, `sellingPrice`, `commission`, `amountRefunded`, `refundType`.

**Amendments.** `PUT /bookings/{bookingId}/amend` changes only the holder's first name, last name and email, plus `remarks`. It answers with an amendment record of `type` UPDATE, `subType` UPDATE_NAME_CHANGE and `status` PENDING (https://docs.nuitee.com/reference/put_bookings-bookingid-amend). Dates or occupancy change only through the hard amendment above.

## 2. Trip guardian for disruptions

**Registering.** Only in the dashboard: "Developer tools → Webhooks → Register Endpoint". The fields are URL, description, "Authentication Token", max retries, initial wait, event subscriptions and static custom headers. A **Test** button sends a `sandbox: true` sample. An API to register webhooks: **not documented**. (https://docs.nuitee.com/docs/using-liteapi-webhooks)

**Authorization.** The token is "sent with each webhook request as the value for `authorization` in the header". HMAC also exists: "optional **HMAC** verification when enabled on the endpoint"; "HMAC signatures themselves are only applied on real deliveries". The header name, algorithm and signed content are **not documented** on that page (**unverified**). External Checkout documents HMAC-SHA256, which suggests the same here, but it is a different feature.

**Envelope.**
```json
{"event_id":"…","event_name":"booking.book","request":"<JSON string>","response":"<JSON string>","sandbox":false}
```
> "`request` and `response` are stringified JSON, not JSON objects." "Webhook delivery should be treated as at-least-once … Deduplicate by `event_id`." The retries back off exponentially.

**Hotel events:** `booking.prebook` ("far too noisy"), `booking.book`, `booking.cancel`, `booking.book.hotelConfirmationNumber`, `booking.checkinInstruction`, `booking.prebook_error`, `booking.book_error` (carries `prebookId`; use it when a book call times out), `booking.cancel_error`, plus the amendment set listed in section 1.
- > "`booking.checkinInstruction` Triggered when check-in instructions for the guest become available or are updated (for example hotel-supplied arrival details, access codes, or front-desk notes)."
- On the booking, `checkinInstructions` holds `idRequired`, `propertyContact.{email,phone}`, `hasCommunication`, `instructions`, `arrivalTimeRequested` and `updatedAt` (https://docs.nuitee.com/reference/get_bookings-bookingid).
- `hotelConfirmationCode`: "Not available at booking time. Nuitee performs a manual process to contact the hotel and get the confirmation number."
- Sandbox: "some webhooks, like the cancel webhook, only work in production". Prebook, book and the error events do fire in sandbox. Whether check-in instructions and confirmation numbers fire in sandbox: **unverified** (likely not, since they are manual).
- `bookout` on a booking: "Present only when the booking was made at a different hotel than the one prebooked (a relocation offered to accounts that opted in)".

**Flight events** (the same page): `flight.prebook`, `flight.attachServices`, `flight.book.created` / `.pending.confirmation`, `flight.book.confirmed`, `flight.book.cancelled` (resent if the refund figures change), and:
- > "`flight.book.schedule_changed` — The airline changed the itinerary … and the booking has already been updated." The `response` is the full booking plus `scheduleChange` (`detectedAt`, `changeCount`, `source`, `segments[]` with the previous and new carrier, flight number and times).
- > "`flight.book.provider_notification` … It tells you what kind of change happened, not the new values; call `GET /flights/bookings/{bookingId}`." Its `notificationType` is an open set: `schedule_change`, `flight_cancellation` (critical), `price_change`, `ticket_time_limit`, `void`, `name_change`, `booking_modified`, `unknown`.
- `flight.book.compensation`: `compensationId`, `amount`, `stripeRefundAmount`, `bankTransferAmount`, `status` (`completed` / `pending_bank_transfer`).
- "Flight events can arrive out of order … use `GET /flights/bookings/{bookingId}` as the source of truth." `flight.book.failed` and `.expired` are listed but never sent.

**Nuitée's flight desk acts on changes itself** (https://docs.nuitee.com/docs/flights-support-billing-model):
> "**We execute, not just notify.** Nuitée modifies the booking directly."

There are two support models. In **First Line**, Nuitée talks to the traveller and charges their card as merchant of record. In **B2B-Relayed**, we relay the case and the cost goes to a credit line. The traveller gets the airline's email only "if the traveller's own contact details are on the booking. Which contact goes into the booking is configurable at onboarding." "We make at least three contact attempts before departure. If there is still no decision, we accept the airline's protected itinerary." The fee is 25 EUR per voluntary change and none for involuntary ones. Contacts: flights@, priorityflights@ and flights.emergency@nuitee.com. Since we have no credit line, First Line looks like the fit (**unverified**: confirm at onboarding).

**Messaging a hotel.** There is no endpoint for it. The only channels are `guests[].remarks` at book ("Special requests or remarks for the guest's stay (not guaranteed)"), `remarks` on `PUT /amend`, and showing the guest `checkinInstructions.propertyContact` so they can contact the hotel directly.

## 3. Experiences

Status: the overview page still says "Experiences coming soon" (https://docs.nuitee.com/docs/docs), but a full API and guides exist. The FAQ says "Experiences access is enabled on request".

- Access (https://docs.nuitee.com/docs/getting-access-to-experiences): request it with dashboard → **Request Assistance**, separately for sandbox, production and white-label. For production, "You may be asked to provide: Your use case, Expected usage or traffic, Proof of a working sandbox integration." Sandbox "does **not** mirror the production Experiences catalogue."
- Base `https://api.liteapi.travel/v3.0`, header `X-API-Key` (https://docs.nuitee.com/docs/experiences-reference). Endpoints: `GET /experiences/tours` (`textSearch` or lat/long/`radiusKm`; filters for date, price, category, rating, duration), `/tours/{id}`, `/tours/{id}/reviews`, `/tours/{id}/availability`, `POST /tours/{id}/booking-options` (slots, price, `bookingQuestionSchema`), `POST /tours/{id}/prebooks`, `POST /experiences/bookings`, `GET /experiences/bookings/{id}`, `GET …/cancel-preview`, `POST …/cancel`.
- Payment (https://docs.nuitee.com/docs/build-an-experiences-booking-flow): prebook with `usePaymentSdk: true` returns `prebookId`, `transactionId`, `secretKey` and a Stripe publishable key. "On the client, call `stripe.confirmCardPayment(secretKey, …)`", then book with `payment.method: TRANSACTION_ID`. **This differs from hotels**: it uses Stripe.js directly, not `liteAPIPayment.js`, so our CSP and `PAYMENT_SDK` rule would need js.stripe.com. Merchant of record: not stated for experiences; probably Nuitée, since the PaymentIntent is created on their side and a voucher's discount "is deducted from the Stripe PaymentIntent and charged separately to the agency's stored card" (**unverified**). `voucherCode` works. The hold lasts "typically ~10 minutes". Error 2015 means the price changed.
- Async (https://docs.nuitee.com/docs/experiences-async-confirmation-webhooks): book usually answers `PENDING_CONFIRMATION`. Webhooks: `experience.book.pending.confirmation`, `.confirmed`, `.voucher.available`, `.updated.datetime`, `.updated.price`, `.cancelled`, `.failed`.
- Cancel (https://docs.nuitee.com/docs/experiences-cancel-refunds): the preview gives `refundAmount`, `cancellationFee`, `refundType` and `estimateConfidence`. Cancel answers `CANCELLATION_REQUESTED` (with `refundPending`) or `CANCELLED`.
- Coverage and the supplier behind it: **not stated**. Pricing for experiences: none listed beyond the general "free" rule.

## 4. Anything else bookable or useful

- **Add-ons in one card charge (the closest thing to a cart)** (https://docs.nuitee.com/docs/attaching-add-ons-to-user-payment): `addons` on the hotel prebook, "The final booking amount is the sum of the offer's total price and the cost of any addons". Uber vouchers come in $10 steps up to $100. eSIM uses `addon:"esimply"` with `package_id`, `destination_code`, `start_date` and `end_date`; the packages come from `/v3.0/addons/esimply/packages/{CC}`. "Be aware that both add-ons are non-refundable." "Only USD values are currently supported." The book response returns `addonVoucherCode` (for an eSIM, the LPA install string). The page's examples use `usePaymentSdk:false`; the title says user payment, so **verify in sandbox** that add-ons work with the SDK.
- **Standalone eSIMply** (https://docs.nuitee.com/reference/createesimplycart, submitesimplyorder): destinations, regions, packages, `cart` → `order` (ICCID, QR/LPA; idempotent by `cartKey`), top-ups, and usage by ICCID. It "Requires `esimply_access` enabled". How a standalone order is paid is **not documented**; it is probably billed to our account, which would make us the seller.
- Cars, transfers, insurance: **not offered** (apart from the Uber voucher). Saved guest cards: no. `CREDIT_CARD_SCHEDULED` ("charged 24 hours before check-in", "Contact the team to enable") needs raw card numbers sent to `pci-book.liteapi.travel`, so it does not fit our rule of never being the seller.
- Multi-room: `occupancies[]` with `guests[].occupancyNumber` 1:1. Group-booking product: not found.
- **AI and search:** `aiSearch` on `/hotels/rates` (natural language, hard filters by city or radius); `GET /data/hotels/semantic-search` (beta, returns tags, persona, style and story); room search by image and text (beta: "twin room with a city view"); `GET /data/hotel/ask` (beta, `allowWebSearch`); `POST /data/hotel/highlights` ($0.02, 10/min); an MCP server at `https://mcp.liteapi.travel/api/mcp` with "127 tools" (hotels, booking, flights, experiences, eSIM, loyalty) (https://docs.nuitee.com/reference/mcp-for-ai-agents); a coding skill for Claude Code; an embeddable Gemini booking chatbot (https://docs.nuitee.com/reference/liteapi-ai-chatbot).
- **Market data:** price index per city (up to 1,000 hotels) and per hotel (≤50 IDs), daily average per night for future dates, beta, 10/min. The price conflicts between pages: $0.02 on the endpoint pages, $0.05 on the pricing page (https://docs.nuitee.com/reference/getpriceindexhotels). **Cached public price** `GET /prices/public`: "pricing information sourced from public booking platforms (e.g., Booking.com, Expedia)", with `offers[]` per provider, USD only, $0.02, 10/min, beta (https://docs.nuitee.com/reference/getpublicprice). Weather: `GET /data/weather`.
- Places: `/data/places` (Google Places, $0.01 per request).
- White label (no-code OTA, weekly payouts, custom domain), loyalty (`PUT /loyalties` cashback rate, guests, points, redeem to a voucher), SSO magic link, External Checkout, widgets, GraphQL: these exist and are not for us.

## 5. Expense reporting (business travel)

- **Invoice PDF per booking:** `GET https://api.wlbl.cloud/v1/invoices/{bookingId}?attachment&key=…` (https://docs.nuitee.com/docs/user-payment). The key travels in the query string, so it must never be logged and the call must stay server-side. Whether the PDF itemises VAT is **unverified** (fetch one in sandbox and look).
- Tax data: `GET /data/hotel/{hotelId}/tax-schema` (`included` vs `payAtProperty`, percentage or fixed, VAT as a category, `securityDeposit`) (https://docs.nuitee.com/reference/gethoteltaxschema). The booking has `mandatoryFees`, `optionalFees` and `price`; it has no VAT line.
- `customTags` on book and rebook: "up to 5 user-defined key/value labels … Keys must match `^[A-Z0-9_-]+$` … values … up to 255 characters … can be used to filter the list endpoints via the `customTags=KEY:VALUE,KEY2:VALUE2` query parameter" (https://docs.nuitee.com/reference/post_rates-book). Good for `COST_CENTER`, `PROJECT` and `TRIP`.
- Lists: `GET /bookings` (stay or creation date ranges, status), `GET /bookings?clientReference=|guestId=|customTags=` (https://docs.nuitee.com/reference/listbookings), and text search `POST` (https://docs.nuitee.com/reference/searchbookings). Analytics (weekly, report, markets, hotels, commissions) are account-level, not per traveller. A CSV export endpoint: not found (the dashboard may have one, **unverified**).
- `metadata` on book (IP, device, UTM) is for fraud screening, not labels.

## 6. Notifications

- API + Payment SDK (our setup): > "Nuitée Connect is the **merchant of record (MoR)** for the guest's card charge… **your application is responsible** for sending the traveler a booking confirmation, receipt, or invoice" and "That is not automatic for API + Payment SDK flows" (https://docs.nuitee.com/docs/user-payment). There is nothing to turn off or brand. The card statement descriptor can be branded: prebook `payment.descriptorSuffix` is a "Suffix appended to the Stripe payment descriptor (visible on customer's bank statement)" (https://docs.nuitee.com/reference/post_rates-prebook).
- On the white-label site Nuitée sends the emails. External Checkout: "Nuitée sends the confirmation email to the guest automatically"; "Suppress confirmation email (Headless mode only)" (https://docs.nuitee.com/docs/external-checkout-dashboard-setup-guide).
- Whether Nuitée emails the guest on a cancel, refund, rebook or relocation in API mode: **unverified**.

## Surprises worth a feature

1. **The public price from Booking.com and Expedia, per hotel and stay** ($0.02, beta). It supports an honest "same as or cheaper than Booking.com" line on the opened square. `suggestedSellingPrice` can also carry `source: "booking.com"` on accounts with "public price enrichment".
2. **The hotel tax schema** (`included` vs `payAtProperty`, resort fees, security deposit). This feeds directly into "The fine print, up front" (F-282).
3. **Hotel registration (the DSA trader)** (`GET /data/hotel/{hotelId}/registration`): the legal entity, register and contact behind a hotel. It is an EU legal disclosure we could show under the fine print.
4. **The check-in instructions webhook and fields** (access codes, `arrivalTimeRequested`, the property's email and phone). This is a "Today" card for arrival day, with no scraping.
5. **The flexible-date flight matrix** (`POST /flights/rates/matrix`, ±1 to 3 days, SSE). It fits our trip matrix's "give or take" days, but needs enablement by support.
6. **Airline website links for a flight** (`POST /flights/booking-links`, unverified method): an honest fallback link when we do not sell a fare.
7. **eSIM and Uber add-ons in the same card charge** as the hotel: one tap adds data for the trip.
8. **`descriptorSuffix`**: put GITAWAY on the guest's bank statement.
9. **Prebook at search and price consistency** (`sessionId`, account features). They hold the listed price through to the hotel page and could stop the price jumps between the matrix and the opened square.
10. **Flight post-booking extras** (seats and bags after ticketing, via precharge then charge) and the flight cancel quote.
11. **Relocation (`bookout`) and compensation events**: we can tell the family plainly when the hotel moved them.
12. Rate limits: sandbox 5 requests per second, production 250 per second per key (https://docs.nuitee.com/reference/rate-limiting).

## Ask Nuitée support (before building use case 1)

1. On `POST /rates/rebook` for a Payment SDK booking that gets cheaper, is the guest's card partly refunded, and is it automatic? Who keeps the difference? How is our commission recalculated? Is the guest emailed? Are there fees?
2. Do `alternative-prebooks` and `rebook` work in the sandbox, and is calling `alternative-prebooks` daily per booking acceptable use (it creates real prebooks)?
3. Which header and algorithm does the webhook HMAC use? Is there an API to register webhooks?
