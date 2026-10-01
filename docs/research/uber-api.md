# Uber ride APIs for GitAway (airport to hotel rides)

Researched 2026-10-01 against developer.uber.com and Uber's own help/marketing pages. Every claim links to the page it came from. **[unverified]** marks things the docs did not state outright.

## TL;DR

- Booking a ride *on behalf of a traveler* from a third-party app is approval-gated in both API families. There is no self-serve path to production ride requests.
- For a travel app, the realistic production API is the **Guest Rides API** (Uber for Business): server-to-server, the traveler needs no Uber account, scheduled pickups are supported, and it has a real sandbox.
- The no-approval option is a **deeplink** (`https://m.uber.com/looking?...`). It prefills pickup, dropoff and product, but the booking happens in Uber's app or site. You can't schedule through it, and nothing comes back to GitAway.
- Scheduling *from* an airport is the tricky case. The consumer "Scheduled Rides" help page says scheduled rides are not available when leaving an airport. Airport pickups are booked through **Uber Reserve** instead: up to 90 days ahead, with flight tracking.

## 1. The APIs that exist

| API | What it does | Who can use it | Auth |
|---|---|---|---|
| **Riders API: Ride Requests** (`api.uber.com/v1.2`) | Books a ride from the rider's *own* Uber account (they log in with OAuth) | Approval required. "Access to this API endpoint requires approval from Uber". Contact Uber BD ([riders intro](https://developer.uber.com/docs/riders/introduction)). The `request` scope is *privileged* and needs app approval for anyone beyond your own developer accounts ([scopes](https://developer.uber.com/docs/riders/guides/scopes), [API intro](https://developer.uber.com/docs/riders/ride-requests/tutorials/api/introduction)) | OAuth 2.0 user access token: `request` (book), `request_receipt`, `profile`, `places`, `history`, `all_trips`, `offline_access` ([scopes](https://developer.uber.com/docs/riders/guides/scopes)). The server token is deprecated ([API intro](https://developer.uber.com/docs/riders/ride-requests/tutorials/api/introduction)) |
| **Guest Rides API** (`api.uber.com/v1/guests`) | An organization books and pays for rides for guests who need no Uber account. The guest gets an SMS ride link ([build guide](https://developer.uber.com/docs/guest-rides/guest-ride-api-build-guide/requesting-a-trip)) | Uber for Business organizations. "Your application must have the `guests.trips` scope to use either of the production or sandbox resources" ([intro](https://developer.uber.com/docs/guest-rides/introduction)). **[unverified]** The docs don't describe how an org gets that scope; in practice you go through Uber for Business sales | OAuth 2.0 `client_credentials` at `https://auth.uber.com/oauth/v2/token`, scope `guests.trips`. Tokens last 30 days, and you can create at most 100 tokens per hour ([auth](https://developer.uber.com/docs/guest-rides/guides/authentication)). Each endpoint allows 200 requests/hour by default, and Uber can raise it ([intro](https://developer.uber.com/docs/guest-rides/introduction)) |
| **Deeplinks / universal links** | Opens the Uber app (or m.uber.com) with the trip prefilled | No approval mentioned. Only a `client_id` from the dashboard ([deeplinks](https://developer.uber.com/docs/riders/ride-requests/tutorials/deep-links/introduction)) | None |

Terms of use: the price estimates may not be used to "offer price comparisons with competitive third party services" ([price estimates](https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get)). That matters if GitAway ever shows Uber and Lyft side by side.

## 2. Request and response shapes

### 2a. Guest Rides API (best fit for GitAway)

| Step | Endpoint | Key fields |
|---|---|---|
| Products, prices and ETAs (one call) | `POST /v1/guests/trips/estimates` ([ref](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-estimates-post)) | **In:** `pickup.{latitude,longitude}`, `dropoff.{latitude,longitude}`, optional `scheduling.pickup_time` (ms epoch), optional `deferred_ride_options.pickup_day` (YYYY-MM-DD), `waypoints[]`. **Out:** `product_estimates[]`, each with `product{product_id, display_name, description, capacity, scheduling_enabled, advance_booking_type (SCHEDULED/RESERVE/FLEXIBLE), cancellation{...}}` and `estimate_info{fare_id, fare{value, currency_code, display, expires_at}, pickup_estimate (min), trip{distance_estimate, duration_estimate, distance_unit}}`. Example: `"fare": {"value": 11.96, "currency_code": "USD", "display": "$11.96"}`. `no_cars_available` flags products with no supply ([guide](https://developer.uber.com/docs/guest-rides/guest-ride-api-build-guide/pulling-product-estimates)) |
| Create (now or scheduled) | `POST /v1/guests/trips` ([ref](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-post)) | **Guest:** `guest.first_name`, `guest.last_name`, `guest.phone_number` (E.164), all required unless you pass `guest_id`; optional `email`, `locale`. **Trip:** `pickup.{latitude,longitude,address}`, `dropoff.{...}`, `product_id` (required), `fare_id` (locks the quoted price), `scheduling.pickup_time` (ms epoch, required for Scheduled/Reserve/Hourly), `note_for_driver` (max 600 chars), `expense_memo` (max 64), `call_enabled`, `contacts_to_notify[]`, `stops[]`, `additional_guests[]`, `return_trip_params`, `sender_display_name` (truncated at 26). **Out:** `request_id`, `product_id`, `status`, `guest`, `estimate_info`, `pickup`, `linked_request_id` (return trip) |
| Status | `GET /v1/guests/trips/{request_id}` ([ref](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-request_id-get)) | `status`, `driver`, `vehicle`, `pickup`, `destination`, `begin_trip_time`, `dropoff_time`, `client_fare`, `trip_distance_miles`, `trip_duration_seconds` |
| Cancel | `DELETE /v1/guests/trips/{request_id}` → `204` ([ref](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-request_id-delete)) | No body. The fee policy is not stated on that page; the estimate's `product.cancellation` carries the minimum fee and grace period |
| Receipt | `GET /v1/guests/trips/{request_id}/receipt` ([ref](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-request_id-receipt-get)) | Not read in detail |

**Guest trip statuses** ([ref](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-request_id-get)):

| Status | Meaning (quoted or close) | Terminal |
|---|---|---|
| `scheduled` | "scheduled to be dispatched at a later time" | |
| `processing` | matching to a driver | |
| `accepted` | driver accepted, en route to pickup | |
| `driver_redispatched` | accepted driver cancelled, new driver dispatched | |
| `arriving` | driver has arrived or will shortly | |
| `in_progress` | rider picked up, en route | |
| `completed` | dropped off | yes |
| `no_drivers_available` | unfulfilled | yes |
| `driver_canceled` | driver cancelled after waiting the grace period | yes |
| `rider_canceled` | cancelled via SMS or the DELETE endpoint (`status_detail`: `guest_rider_canceled`) | yes |
| `failed` | request failed | yes |
| `offered` / `expired` | flexible (deferred) rides only | `expired` yes |

**Webhooks** ([guide](https://developer.uber.com/docs/guest-rides/guides/webhooks)): `guests.trips.status_changed`, `guests.trips.driver_location`, `guests.trips.trip_message`, `guests.trips.receipt_ready`. Each request is signed with an `X-Uber-Signature` header (HMAC-SHA256 of the body, keyed with the webhook signing key), and an `X-Environment` header says `production` or `sandbox`. **[unverified]** The guest payload shape wasn't shown; the Riders webhook payload is `event_id`, `event_time`, `event_type`, `meta{user_id, resource_id, status}`, `resource_href` ([riders webhooks](https://developer.uber.com/docs/riders/guides/webhooks)). Treat a webhook as "go re-fetch", and answer it with a 200 and an empty body.

### 2b. Riders API v1.2 (rider's own account)

| Step | Endpoint | Key fields |
|---|---|---|
| Products | `GET /v1.2/products?latitude=&longitude=` ([ref](https://developer.uber.com/docs/riders/references/api/v1.2/products-get)) | `products[]{product_id, display_name, capacity, description, image, shared, upfront_fare_enabled, product_group (uberx, uberxl, uberblack, suv, taxi...), cash_enabled}`. "does not reflect real-time availability" |
| Price estimate | `GET /v1.2/estimates/price?start_latitude&start_longitude&end_latitude&end_longitude` ([ref](https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get)) | `prices[]{product_id, display_name, estimate ("$12-15"), low_estimate, high_estimate, currency_code, duration (s), distance (mi), surge_multiplier}`. Approval required |
| Time estimate | `GET /v1.2/estimates/time` ([API intro](https://developer.uber.com/docs/riders/ride-requests/tutorials/api/introduction)) | Not read in detail |
| Upfront fare | `POST /v1.2/requests/estimate`, which returns the `fare_id` that `POST /requests` requires ([requests-post](https://developer.uber.com/docs/riders/references/api/v1.2/requests-post)) | **[unverified]** The response shape was not read |
| Create | `POST /v1.2/requests` ([ref](https://developer.uber.com/docs/riders/references/api/v1.2/requests-post)) | `fare_id` (required), `start_latitude/longitude` or `start_place_id`, `end_...`, optional `product_id`, `start_nickname/address`, `end_nickname/address`, `payment_method_id`, `seat_count`, `expense_code/memo`. Returns `202` with `request_id`, `status`, `eta`, `driver`, `vehicle`, `location`, `surge_multiplier`; `409` if the fare or surge expired. **No scheduled-time field**: this API books immediate rides only |
| Status | `GET /v1.2/requests/{request_id}` or `/requests/current`; poll every 3 to 5 seconds or use webhooks ([best practices](https://developer.uber.com/docs/riders/ride-requests/tutorials/api/best-practices)) | Statuses: `processing`, `no_drivers_available`, `accepted`, `arriving`, `in_progress`, `driver_canceled`, `rider_canceled`, `completed` |
| Cancel | `DELETE /v1.2/requests/{request_id}` ([sandbox guide](https://developer.uber.com/docs/riders/guides/sandbox)) | |
| Webhooks | `requests.status_changed`, `requests.receipt_ready`, `all_trips.status_changed`; signed with `X-Uber-Signature` (HMAC-SHA256 keyed with the client secret); up to 7 retries over about an hour ([riders webhooks](https://developer.uber.com/docs/riders/guides/webhooks)) | **[unverified]** The summarized page carried a deprecation note dated 2020 that I couldn't confirm verbatim |

## 3. Scheduling a future pickup

- **Guest Rides API: yes.** Set `scheduling.pickup_time` (ms epoch). "Scheduled Rides are dispatched before the scheduled pickup_time such that the driver is expected to arrive at the pickup location at the pickup_time" ([create trip](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-post)). Each product's `advance_booking_type` says whether it's SCHEDULED, RESERVE or FLEXIBLE, and `scheduling_enabled` says whether it can be scheduled at all ([estimates](https://developer.uber.com/docs/guest-rides/references/api/v1/guest-trips-estimates-post)). **[unverified]** The API docs give no maximum lead time.
- **Riders API: no** scheduling field ([requests-post](https://developer.uber.com/docs/riders/references/api/v1.2/requests-post)).
- **Consumer limits** (likely the same limits behind the API, **[unverified]**): Scheduled Rides can be booked "5 minutes to 30 days in advance", and "they are not currently available when leaving an airport" ([help](https://help.uber.com/h/63165ec1-0910-409e-972f-0b8d8df1a605)). For airport pickups Uber sells **Reserve**: "up to 90 days ahead", "flight-tracking technology", wait up to 45 minutes after landing for UberX, Comfort and XL, and free cancellation "until one hour before pickup or if no driver has accepted the trip yet" ([SFO pickup page](https://www.uber.com/global/en/r/airports/sfo/pickup/)).
- Consequence for GitAway: the **hotel to airport** leg is a normal scheduled ride. The **airport to hotel** leg should be modeled as a Reserve-style booking tied to the flight. **[unverified]** Whether the Guest API accepts a flight number isn't documented on the pages read; no flight field appears in Create Guest Trip.

## 4. Sandbox

- **Guest Rides:** base `https://sandbox-api.uber.com`. `POST /v1/guests/sandbox/run` creates test riders and drivers that last 8 hours, and you pass the header `x-uber-sandbox-runuuid: {run_id}` on later calls. You advance the driver yourself with `/v1/guests/sandbox/driver-state`: `ACCEPT → ARRIVED → BEGIN_TRIP → DROPOFF`, or `CANCEL` after ACCEPT or ARRIVED. Limits: there are no receipt webhooks in the sandbox, Reserve and Hourly trips can't be moved to ACCEPT, and idle drivers go offline after 5 minutes ([sandbox](https://developer.uber.com/docs/guest-rides/guides/sandbox)).
- **Riders:** `https://sandbox-api.uber.com/v1.2`. `PUT /sandbox/requests/{id}` with statuses in the order `processing → accepted → arriving → in_progress → completed`; `driver_canceled` can happen at any point, and the rider cancels with DELETE ([sandbox](https://developer.uber.com/docs/riders/guides/sandbox)).
- **[unverified]** Whether `guests.trips` is granted for the sandbox before a production agreement exists.

## 5. Simplest no-approval option: deeplinks

Source: [deeplinks](https://developer.uber.com/docs/riders/ride-requests/tutorials/deep-links/introduction). Pickup, dropoff and product prefill all work, but **there is no scheduling parameter**. If the app isn't installed, the user is sent to the App Store or Play Store.

Universal link (preferred for web):

```
https://m.uber.com/looking?client_id=<CLIENT_ID>
  &pickup=<urlencoded JSON {"latitude":..,"longitude":..,"addressLine1":"<nickname>","addressLine2":"<full address>"}>
  &drop[0]=<urlencoded JSON, same shape>
  &product_id=<uuid>
```

Uber's own example, verbatim:

```
https://m.uber.com/looking?client_id=<CLIENT_ID>&pickup=%7B%22latitude%22%3A37.77581%2C%22longitude%22%3A-122.418028%2C%22addressLine1%22%3A%22UberHQ%22%2C%22addressLine2%22%3A%221455%20Market%20St%2C%20San%20Francisco%2C%20CA%2094103%22%7D&drop[0]=%7B%22latitude%22%3A37.802374%2C%22longitude%22%3A-122.405818%2C%22addressLine1%22%3A%22Coit%20Tower%22%2C%22addressLine2%22%3A%221%20Telegraph%20Hill%20Blvd%2C%20San%20Francisco%2C%20CA%2094133%22%7D&product_id=a1111c8c-c720-46c3-8534-2fcdd730040d
```

Native scheme (older form):

```
uber://riderequest?pickup[latitude]=..&pickup[longitude]=..&pickup[nickname]=..&pickup[formatted_address]=..&dropoff[latitude]=..&dropoff[longitude]=..&dropoff[nickname]=..&dropoff[formatted_address]=..&product_id=<uuid>
```

Notes: you can add more stops with `drop[1]`, `drop[2]` and so on. `product_id` "requires a pickup location" and doesn't work together with current-location pickup. `product_id` values are per-city UUIDs from the Products endpoint, which itself needs credentials; **[unverified]** whether a hard-coded UUID works across cities. Leaving `product_id` out is the safe default.

## 6. Lyft, briefly

- **Public developer docs:** `developer.lyft.com` did not resolve from here on 2026-10-01 (DNS failure), and `lyft.com/developers` redirects to a login. **[unverified]** whether Lyft's public API is retired or just moved.
- **Concierge API** (Lyft Business): an organization books and pays for rides for people without the app, with scheduled and Flexible rides; it's partner/business only ([Lyft blog](https://www.lyft.com/blog/posts/revolutionizing-patient-transportation-with-lyft-concierge-api), [flexible rides](https://help.lyft.com/business/hc/en-us/articles/360001832688-How-to-send-flexible-rides-in-Concierge)). Scheduled rides can be booked "up to 30 days in advance" ([help](https://help.lyft.com/business/hc/en-us/articles/360015660234-How-to-request-a-pre-scheduled-ride-in-Concierge)). This is Lyft's counterpart to Uber Guest Rides.
- **Deeplink:** `lyft://ridetype?id=lyft&pickup[latitude]=..&pickup[longitude]=..&destination[latitude]=..&destination[longitude]=..&partner=<CLIENT_ID>`, with optional `pickup[address]` and `destination[address]` ([Lyft Android SDK source](https://github.com/lyft/lyft-android-sdk/blob/master/deeplink/src/main/java/com/lyft/deeplink/DeepLink.java)). Web form: `https://lyft.com/ride?id=lyft&...` with the same parameters (from Lyft's universal-links doc via search; the page itself was unreachable, so **[unverified]**). Like Uber's, it has no scheduling.

## What to simulate

Model the **Guest Rides API**: GitAway books and the traveler gets the ride by SMS. Show a deeplink "Open in Uber" fallback.

**Fields to collect**
- Traveler: first name, last name, mobile number (E.164, with a country picker), optional email.
- Trip: pickup and dropoff (lat/lng plus address; airport terminal and hotel from the itinerary), `product_id` chosen from the estimates, `fare_id` from the chosen estimate, and `pickup_time` (ms) for scheduled legs.
- Optional: note for the driver (600 characters max), and a return trip (hotel to airport) linked through `return_trip_params` / `linked_request_id`.
- For the airport leg, keep the flight number and arrival time in GitAway's own data, as Reserve-style flight tracking. Don't send them as an API field, because none is documented.

**Screens**
1. **Ride options** (estimates): a list of products (UberX, Comfort, XL, Black) with `display_name`, capacity, price `display` (e.g. "$41.20"), pickup ETA or "Scheduled", trip duration, and a "No cars available" state. Show the quote's expiry (`fare.expires_at`).
2. **Schedule**: airport arrival leg set to the flight arrival time, with a note like "driver waits up to 45 min; free cancel until 1 h before". Return leg as a normal scheduled pickup, at least 5 minutes and at most 30 days out (Reserve allows 90).
3. **Traveler details**: name and phone, plus "Uber will text a ride link to this number".
4. **Confirmation**: request id, status `scheduled`, locked fare, a Cancel button.
5. **Live trip**: status timeline with driver name, vehicle and plate, ETA; refresh every 3 to 5 seconds or on a simulated webhook.
6. **Receipt**: final fare, distance and duration.
7. **Fallback**: "Book in the Uber app" deeplink with pickup and dropoff prefilled.

**Status sequence (happy path)**
`scheduled → processing → accepted → arriving → in_progress → completed`

**Branches to show**
- `processing → no_drivers_available` (terminal)
- `accepted → driver_redispatched → accepted`
- `accepted|arriving → driver_canceled` (terminal)
- any pre-pickup state → `rider_canceled` (Cancel button, DELETE → 204)
- `failed` (generic error)
- fare quote expired (the API answers 409, so re-quote)
