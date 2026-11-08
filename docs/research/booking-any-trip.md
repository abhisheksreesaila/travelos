# Booking for any trip: Travelpayouts lanes, in-app data, and the Lake Tahoe test

Researched 2026-11-06 for the ask "booking should work for any destination", tested against the founder's own trip: Lake Tahoe, December 2026, flying into Reno (RNO), 2 adults and kids, a cabin or hotel, an SUV, and snow days. Follows on from [booking-apis-and-payments.md](booking-apis-and-payments.md) and the Economics section of [critique-2026-11-06.md](critique-2026-11-06.md).

Markers: **[verified]** read on the owner's own page or API, or opened in a browser here. **[secondary]** from a search snippet or third party only. **[unverified]** not confirmed anywhere authoritative.

Where the numbers come from: Travelpayouts' public brand list, the JSON behind https://www.travelpayouts.com/brands-directory/ (45 public brands, read 2026-11-06), plus each brand's offer page `https://www.travelpayouts.com/en/offers/<slug>/`. The help center blocks plain fetches, so its articles were read through Zendesk's public JSON (`support.travelpayouts.com/api/v2/help_center/en-us/articles/<id>.json`). Deep links were opened in headless Chromium (Playwright) from this machine, with test dates **Sat 19 Dec to Sat 26 Dec 2026** and a test party of **2 adults plus kids aged 8 and 11**.

## TL;DR

| Lane | Partner (via Travelpayouts) | What it pays | Cookie | Deep link carries | Tahoe test |
|---|---|---|---|---|---|
| **Stay** | **Booking.com** (replaces Klook for stays) | 4% of the booking on average (the brand list says 3 to 5%) | **one session** | town, dates, adults, each child's age, rooms | **Results page, right dates and party, in both towns** [verified] |
| Stay (cabins, 2nd link) | Vrbo | 1.8% | 7 days | town, dates, adults, child ages (format not confirmed) | Bot wall (429) from here [unverified] |
| **Flight** | **Aviasales** (keep) | 40% of Aviasales' revenue, about 1.1% of the fare | 30 days | origin, destination, dates, adults/children/infants | Form filled correctly: SFO/LAX to RNO, 19 to 26 Dec, 2 adults + 2 children. Results were behind a captcha in the headless browser [verified form; results unverified] |
| **Car** | **EconomyBookings** (any airport by IATA code) | 60% of its revenue, 3 to 8% of the booking | 30 days | pickup airport only | Pickup fills as "Reno Airport"; dates don't carry [verified] |
| Car (alternative) | DiscoverCars | 54% of its revenue (23% on extras) | **365 days** | pickup, only via a per-airport page slug | RNO page opens with RNO prefilled and live prices; dates don't carry [verified] |
| **Snow and things to do** | **GetYourGuide** (replaces Klook for the US) | 8% | 31 days | place, dates | 43 Lake Tahoe results with 20 to 25 Dec kept: snowmobile from $265, snowshoe, cruises [verified] |
| Snow (2nd) | Viator | 8% | 30 days | place/category page | Has a "Ski and Snow" category page; 403 from here [secondary] |
| **Lift tickets, ski lessons** | **None.** Sold direct by Vail Resorts (Heavenly, Northstar, Kirkwood) and Alterra (Palisades Tahoe) | nothing | n/a | n/a | No affiliate route found [unverified that none exists] |
| Insurance | Skip | n/a | n/a | n/a | Travelpayouts' US policies (VisitorsCoverage, Insubuy) are for visitors to the US |

- **For a family trip, the stay is where the money is.** A $2,800 cabin week at 4% pays about $112. Four SFO-RNO round trips (about $600) at about 1.1% pay about $7, a car pays about $18 to $20 a booking, and a $265 snowmobile pays about $21 (our arithmetic, using Travelpayouts' stated rates). **Put stays first and pick Booking.com.** Its one-session cookie is the weak point, but the deep link opens the exact search, which is the best case for booking within that session.
- **In-app real data:** flights only. The Aviasales Data API is free, needs a token, has no approval step, and serves cached prices up to 7 days old. **Travelpayouts has no hotel API since Hotellook closed on 2025-10-20**, and no Klook or GetYourGuide API. Expedia's Travel Redirect API has paused new applications. So: one "from $X" flight chip from the Data API (cached 24 hours), and honest search cards for everything else. Skip the widgets.
- **Bookings come back** through the "Did you book it?" prompt planned in F-180, plus pasting the confirmation email into the Ask box. The paste reader already exists; extend it beyond Expedia.
- **Klook stays in for Asia and theme parks** (Disneyland). For a US mountain trip it is thin: one South Lake Tahoe destination page with a handful of hotels, nothing for Tahoe City, and a snowshoe rental.

## 1. Programs per lane (Travelpayouts, US family trip)

Commission and cookie figures come from Travelpayouts' brand list JSON and the offer pages [verified]. "Apply" means the brand moderates each new project: Travelpayouts says Booking.com processes applications "within three business days" and Viator takes "three to ten days, on average". GetYourGuide "promptly considers all applications", and Insubuy moderation "takes up to two weeks". All of these are [verified] from the offer pages. Every program is free to join.

### Flights

| Program | Pays | Cookie | US relevance | Deep link | Apply? |
|---|---|---|---|---|---|
| **Aviasales** | "40% of the revenue that Aviasales receives" (brand list headline 50%); eCPC $0.12; average order $353 | 30 days | Weak. About 10% of aviasales.com traffic is US [secondary, Similarweb via critique]. Its results do include US agencies | `/search/<FROM><DDMM><TO><DDMM><adults><children><infants>`: confirmed here (see section 3). The marker goes on the URL | Already joined |
| Kiwi.com | 3% | 30 days | Medium | Own format; **the partner-links API refuses Kiwi links** ([links API](https://support.travelpayouts.com/hc/en-us/articles/25289759198226)) [verified] | Yes (brand approval for its API) |
| Trip.com | 1% on international flights | 7 to 30 days | Low for US domestic | Trip.com verification wall from here | Join |
| Booking.com | EUR 1.5 per flight order | one session | Medium | n/a | Yes |

No better US flight option exists on Travelpayouts. Keep Aviasales, and don't lead with flights.

### Stays

| Program | Pays | Cookie | Tahoe coverage | Deep link | Apply? |
|---|---|---|---|---|---|
| **Booking.com** | 5% headline; "On average, 4% of the booking value" ([offer](https://www.travelpayouts.com/en/offers/bookingcom-affiliate-program/)); brand list "3% – 5%" | **One session** | **Strong.** South Lake Tahoe: hundreds of properties (298 with free cancellation). Tahoe City: 50 entire homes, 47 vacation homes, 4 hotels [verified, live page] | `searchresults.html?ss=&checkin=&checkout=&group_adults=&group_children=&age=..&no_rooms=` [verified] | **Yes, about 3 business days.** Rules: no social media unless approved, no iframes of booking.com, no toolbars, no lookalike domains [verified, offer page]. A web app is fine |
| **Vrbo** | 1.8% "on online approved booking requests", confirmed 60 days after check-out | 7 days | Cabins are Vrbo's core | `vrbo.com/search?destination=&startDate=&endDate=&adults=&children=1_<age>,...` [unverified: 429 bot wall] | Join |
| Expedia (US) | Directory: 1.35 to 3.6%. The offer page now says a "30-48" revenue share: **hotels 4.20 to 6.72% of GBV**, activities 2.10 to 3.36%, cars 1.05 to 1.68%, flights 0.30 to 0.48% ([offer](https://www.travelpayouts.com/en/offers/expedia-us-affiliate-program/)). The two pages disagree | 7 days | Strong | Expedia documents `/go/` deep links (section 3) [verified docs; unverified on expedia.com: 429] | Join |
| Hotels.com | 3.6% hotels, 1.8% vacation rentals, 1.35% cars | 7 days | Strong | Same family as Expedia [unverified] | Join |
| Trip.com | 5.5% hotels, 4.5% car rental, 3.6% activities | 7 to 30 days | Unknown | Verification wall from here | Join |
| Klook (current) | 5% (2% "Special Activities") | 30 days on the offer page. Involve Asia lists 7 days for hotels and cars [secondary] | **Thin.** One South Lake Tahoe destination page with a few hotels ([klook c700078](https://www.klook.com/destination/c700078-south-lake-tahoe/)) [secondary: search snippet; 403 here] | Search only, no dates or party | Joined |
| Agoda | 1 to 6% | **1 day** | Weak in the US | n/a | Join |
| Vio.com | 40 to 64% of its commission | 30 days | Unknown (metasearch) | n/a | No landing page |
| Hotellook | **Closed 2025-10-20.** "Widgets, landing pages, and the Hotellook API stopped working"; old revenue-making links redirect to a Booking.com search ([FAQ](https://support.travelpayouts.com/hc/en-us/articles/29534131568530)) [verified] | | | | |

**Stay22** is not on Travelpayouts. It is a separate network that wraps Booking, Expedia, Vrbo and others in a map widget, keeps a share (its community guide says payouts "start at 30%"), and doesn't publish its splits [secondary]. It needs no Travelpayouts work, but it is a third-party script and a second network. Skip it for now.

### Cars

| Program | Pays | Cookie | Deep link | Apply? |
|---|---|---|---|---|
| **EconomyBookings** | "60% of the revenue that EconomyBookings receives" (3 to 8%); eCPC $0.04; average $250 | 30 days | **Documented:** `economybookings.com/en?idpickval=<IATA>` ([help](https://support.travelpayouts.com/hc/en-us/articles/360007365071)) [verified]. Pickup only; no date parameters are documented | Yes ("Your project must be approved for the program") |
| **DiscoverCars** | "54% of the revenue that DiscoverCars receives from car rentals … and 23% … from other services"; average about $18 to $20 a booking; eCPC $0.02 | **365 days** | Airport pages like `/usa-nevada/reno/rno` (country-state/city/iata) [verified for RNO]. No documented search format; Travelpayouts' DiscoverCars API article now returns nothing | Join |
| Expedia cars | 1.05 to 1.68% | 7 days | **Best link:** `/go/carsearch/Airport/<from>/<to>?PickUpLoc=RNO&Class=SUV&Equipment=W,S` (W = snow chains, S = ski rack; [Expedia car deeplinks](https://developers.expediagroup.com/white-label-travel-platform/traffic-growth/deeplinking/car-deeplinks)) [verified docs; unverified on expedia.com] | Join |
| Localrent | 7.5 to 10% | 30 days | Its own page lists Europe and resort countries; **not the US** | n/a |
| GetRentacar, QEEQ, AutoEurope (EU, UK) | 10% / 5 to 10% / 4.4 to 8% | 90 / 30 / 30 days | US coverage not checked | n/a |
| Klook (current) | 5% | 7 to 30 days | Search only; US car coverage unknown | Joined |

### Activities, snow, ski

| Program | Pays | Cookie | Tahoe | Deep link | Apply? |
|---|---|---|---|---|---|
| **GetYourGuide** | 8%; average $140 | 31 days | 43 results for "Lake Tahoe" over 20 to 25 Dec: Summit Snowmobile Tour (from $265), Scenic Snowshoe (Truckee), Emerald Bay cruises [verified] | `getyourguide.com/s/?q=<place>&date_from=&date_to=` [verified] | Yes ("promptly") |
| **Viator** | 8%; average $220 | 30 days | "Ski and Snow" category page `d816-g9-c38`: snowmobile tours from $265, self-guided snowmobile rental from Stateline [secondary: search snippets; 403 here]. Expedia and Viator both sell Black Tie's "Heavenly Premium Ski Rental Including Delivery" [secondary] | Category and product pages | **Yes, 3 to 10 days** |
| Klook | 5% / 2% | 30 days | One Tahoe snowshoe rental ([activity 131234](https://www.klook.com/en-US/activity/131234-tahoe-snowshoe-rental-and-self-guided-tour-in-lake-tahoe/)) [secondary] | Product pages | Joined |
| Tripadvisor Experiences | 8% | 14 days | Not checked | n/a | Join |
| Tiqets | 3.5 to 8% | 30 days | Museums and attractions; no Tahoe search page (404) | n/a | Join |
| Go City | 3.4 to 6% | 90 days | City passes, not Tahoe | n/a | |
| **Lift tickets and lessons** | No Travelpayouts brand. Liftopia, the old lift-ticket marketplace, went through a 2020 bankruptcy fight and was sold to Skitude [secondary]. No affiliate program was found for Vail Resorts / Epic or for Alterra / Ikon / Palisades Tahoe [unverified that none exists] | | Heavenly, Northstar, Kirkwood: Vail Resorts, sold on the resort sites and epicpass.com. Palisades Tahoe: Alterra. Sierra-at-Tahoe: its own site. All six domains answer 200 [verified] | Resort home pages | n/a |

### Insurance

VisitorsCoverage ($1 to $160 by policy price, 30 days) and Insubuy ($1.5 to $150, 30 days, moderation up to two weeks) are on Travelpayouts [verified]. Their pitch is medical cover for visitors to the US, and Insubuy's terms forbid anything that looks like soliciting insurance under Texas insurance law [verified, offer page]. That doesn't fit a domestic family trip, so **no insurance lane.**

## 2. Real data GitAway can show in its own pages, for free

| Source | Status | Auth | Limits | Terms |
|---|---|---|---|---|
| **Aviasales Data API** (`api.travelpayouts.com/aviasales/v3/prices_for_dates`, `/v3/grouped_prices`, `/v2/prices/month-matrix`, …) | **Available.** "Access is allowed without restrictions, but you must have a token", which comes with sign-up ([requirements](https://support.travelpayouts.com/hc/en-us/articles/203956083)) [verified]. Prices come from Aviasales users' searches over the last 2 to 7 days. Pass `market=us` (the default is the `ru` market) and `currency=usd` (the default is RUB) ([docs](https://support.travelpayouts.com/hc/en-us/articles/203956163)) [verified] | `X-Access-Token` header or `token=`. A call without a token answers 401 (probed) | Per minute: `prices_for_dates` and `grouped_prices` 600, `month-matrix` and `prices/calendar` 300, `prices/monthly` 60. Above that, 429 errors ([rate limits](https://support.travelpayouts.com/hc/en-us/articles/4402565416594)) [verified] | "It is recommended to cache the results onsite for 24 hours" ([FAQ](https://support.travelpayouts.com/hc/en-us/articles/204529267)) [verified]. Show them as "from $X, seen recently", never as a quote. Thin routes like SFO-RNO may return nothing; no token was available here, so **Tahoe coverage is [unverified]** |
| Aviasales Flight Search API (live fares) | **Not available.** "only available to projects with at least 50,000 monthly active users … we do not make exceptions" ([access](https://support.travelpayouts.com/hc/en-us/articles/210995808)) [verified] | | | |
| Hotel prices on Travelpayouts | **None.** Hotellook's API is gone (see above), and Aviasales' FAQ says "Aviasales doesn't provide Hotels API". Travelpayouts' list of brands that offer APIs or feeds has no hotel brand: Aviasales, Kiwi, Omio, intui, GetTransfer, Airalo, Tiqets (feed), WeGoTrip, and Viator (a discount feed) ([list](https://support.travelpayouts.com/hc/en-us/articles/20384016664594)) [verified] | | | |
| Klook / GetYourGuide APIs | **Not through Travelpayouts** (neither is on that list). GetYourGuide's Partner API token is issued by GetYourGuide [secondary] | | | |
| Viator Affiliate API (direct, not Travelpayouts) | "By creating an affiliate account, you'll immediately get Basic Access", with no fees, and you earn when traffic books on viator.com within 30 days ([Viator](https://partnerresources.viator.com/travel-commerce/affiliate/)) [verified]. Products come with titles, images, ratings, prices and availability schedules [secondary] | Viator API key | Not checked | That would mean a second Viator account beside Travelpayouts' Viator program. A later option for real snow-activity cards |
| Expedia Travel Redirect API (lodging/flight listings) | "Due to the volume of requests, we have **paused all new API applications**" ([Expedia](https://developers.expediagroup.com/travel-redirect-api)) [verified] | | | |
| **Travelpayouts widgets** | Search forms, the Aviasales calendar and price map, GetYourGuide availability, and Tiqets product widgets. Widgets are "available only for Projects with websites" ([widgets](https://support.travelpayouts.com/hc/en-us/articles/360031977872)) [verified]. The hotel map (`hotelsmap`) was a Hotellook tool | The partner ID is baked into the snippet | n/a | Each one is a third-party script with its own look and a "Powered by Travelpayouts" referral link (it can be switched off) [verified]. That breaks the colour timeline and adds a service to the privacy list. **Not recommended**; the Data API plus our own cards does the same job |
| Travelpayouts statistics API (`/statistics/v1/execute_query`) | Available, 30 requests/min [verified]. Splits bookings by SubID | Token | | Could mark a click as "probably booked" after the fact. How soon a booking shows up there is [unverified] |

## 3. The Tahoe links (19 to 26 Dec 2026, 2 adults, kids 8 and 11)

Placeholders: `{MARKER}` = 801445, `{SUB_ID}` = `log.sub_id(...)` (digits, Latin letters and `_` only: [SubID rules](https://support.travelpayouts.com/hc/en-us/articles/203955653) [verified]; the repo already does this, D-164). For every brand except Aviasales, the plain URL below is what gets sent to `POST https://api.travelpayouts.com/links/v1/create` with `{"trs": <project>, "marker": {MARKER}, "links": [{"url": <url>, "sub_id": {SUB_ID}}]}`. The project must be connected to that brand. Limits are 100 requests/min per marker and 10 links per request, and Kiwi, HolidayTaxis, Ticketmaster, Priority Pass and Indrive are excluded ([links API](https://support.travelpayouts.com/hc/en-us/articles/25289759198226)) [verified]. Whether a tracked Booking.com link keeps every query parameter is [unverified]; check it with the live probe script once the token is set.

| What | Link | What happened here |
|---|---|---|
| Flight SFO → RNO | `https://www.aviasales.com/search/SFO1912RNO261222?marker={MARKER}.{SUB_ID}` | **Form verified:** "San Francisco SFO → Reno RNO, Sat, December 19 – Sat, December 26, 4 passengers". The passenger panel reads Adults 2, Children (2 to 11) 2, Infants 0. Results showed a picture captcha to headless Chromium, so they are [unverified]. A real phone is not expected to see one [unverified] |
| Flight LAX → RNO | `https://www.aviasales.com/search/LAX1912RNO261222?marker={MARKER}.{SUB_ID}` | Same as above [verified form] |
| Flight, home airport unknown | `https://www.aviasales.com/?destination_iata=RNO&depart_date=2026-12-19&return_date=2026-12-26&adults=2&children=2&marker={MARKER}.{SUB_ID}` | Aviasales guessed the origin from the visitor's IP (SFO here), filled everything else, and waited for "Search" [verified] |
| Stay, South Lake Tahoe | `https://www.booking.com/searchresults.html?ss=South+Lake+Tahoe%2C+California&checkin=2026-12-19&checkout=2026-12-26&group_adults=2&group_children=2&age=8&age=11&no_rooms=1&lang=en-us&selected_currency=USD` | **Results page** with "Sat, Dec 19 — Sat, Dec 26 · 2 adults · 2 children · 1 room" and the breadcrumb "United States > California > South Lake Tahoe" [verified] |
| Stay, Tahoe City | same with `ss=Tahoe+City%2C+California` | **Results page**, right dates and party: 50 entire homes / 47 vacation homes / 4 hotels [verified] |
| Stay, cabin on Vrbo | `https://www.vrbo.com/search?destination=Tahoe%20City%2C%20California&startDate=2026-12-19&endDate=2026-12-26&adults=2&children=1_8%2C1_11` | "Bot or Not?" (429) [unverified] |
| Stay on Expedia (documented format) | `https://www.expedia.com/go/hotel/search/Destination/2026-12-19/2026-12-26?CityName=South%20Lake%20Tahoe&NumRoom=1&NumAdult-Room1=2&NumChild-Room1=2&Room1-Child1Age=8&Room1-Child2Age=11` ([lodging deeplinks](https://developers.expediagroup.com/white-label-travel-platform/traffic-growth/deeplinking/lodging-deeplinks)) | 429 [unverified on expedia.com; the doc is for Expedia's white-label sites, though its examples use www.expedia.com] |
| Stay on Klook | `https://www.klook.com/destination/c700078-south-lake-tahoe/` | 403 to this machine (as D-160 found). No dates or party |
| Car at RNO (any airport) | `https://www.economybookings.com/en?idpickval=RNO` | Pickup filled: "Reno Airport, Reno, USA Nevada". Dates fall back to its defaults [verified] |
| Car at RNO, DiscoverCars | `https://www.discovercars.com/usa-nevada/reno/rno` | Pickup "Reno/Tahoe International Airport (RNO)" filled, with live sample prices for default dates (e.g. Toyota RAV4 intermediate SUV $55.59/day). Dates not carried [verified] |
| Car at RNO, SUV with chains (Expedia) | `https://www.expedia.com/go/carsearch/Airport/2026-12-19/2026-12-26?PickUpLoc=RNO&Class=SUV&Equipment=W,S` | 429 [documented, unverified] |
| Snow activities | `https://www.getyourguide.com/s/?q=Lake%20Tahoe&date_from=2026-12-20&date_to=2026-12-25` | **"43 results: Lake Tahoe", "Dec 20 – 25"**, snowmobile and snowshoe listed [verified]. A third request a minute later got Cloudflare's 403, so rapid automated hits are blocked |
| Ski and snow (Viator) | `https://www.viator.com/Lake-Tahoe-tours/Ski-and-Snow/d816-g9-c38` | 403 here [secondary] |
| Lift tickets and lessons | `https://www.skiheavenly.com/`, `https://www.northstarcalifornia.com/`, `https://www.kirkwood.com/`, `https://www.palisadestahoe.com/`, `https://sierraattahoe.com/` | All answer 200. No commission; deep pages to lift tickets and ski school not checked |

GetYourGuide's "Lake Tahoe ski" search returns the same cruises and snowmobiles: **no ski lessons or lift tickets.** In this test, only flights, the Booking.com stays and GetYourGuide carry dates and party all the way through.

## 4. Recommended design for "any destination"

What a trip needs for every link: a **place name** (town), the **nearest airport IATA** (the repo has `gitaway/airport_coords.py`), **dates**, **adults** and **kid ages** (`Trip.kid_ages` already exists). Nothing per-destination has to be hand-built, so the catalog's four places stop being a limit.

**Lanes and partners (ship in a day or two):**

1. **Stay → Booking.com** search link (`ss=<town>, <state>`, dates, `group_adults`, `group_children` plus one `age=` per child). It goes through the partner-links API exactly as Klook does today: generalise `travelpayouts.klook_link` into `tracked_link(url, sub_id)`. **Apply to Booking.com on Travelpayouts now** (about 3 business days). A second "Cabins on Vrbo" link is optional (1.8%, link unverified).
2. **Flight → Aviasales** unchanged (F-195 home-airport logic). Optional: one "from $X, seen recently" chip from the Data API (`prices_for_dates`, `market=us`, `currency=usd`), cached 24 hours per route and month, hidden when the cache is empty.
3. **Car → EconomyBookings** `?idpickval=<IATA>`. It works for any airport and has the better eCPC ($0.04 vs DiscoverCars' $0.02 on Travelpayouts' own figures). Apply for project approval. DiscoverCars stays a later swap for its 365-day cookie, once there is a slug table for the top family airports.
4. **Things to do → GetYourGuide** `?q=<town>&date_from&date_to` for US and European trips. **Keep Klook** for Asia and theme parks (the Disneyland product page stays). Viator second, after its 3 to 10 day review.
5. **Lift tickets and lessons → an honest "Buy direct at <resort>" card** with no Book-and-earn styling and no commission line. Make it a small per-place list (Tahoe: Heavenly, Northstar, Kirkwood, Palisades, Sierra), shown only when the place is a ski destination.
6. Drop the made-up offers and prices whenever a real trip is in view. Each lane shows **one honest search card**: "Stays in Tahoe City · 19–26 Dec · 2 adults, 2 kids → Booking.com". Real prices appear only where they come from the Data API.

**How a booking comes back into the trip:**

- **The F-180 return prompt** ("Did you book it?" on `visibilitychange`) puts a "Booked elsewhere · Booking.com" block on the lane's dates. That needs no parsing.
- **Then "paste your confirmation".** The repo already reads a pasted or PDF Expedia itinerary (`gitaway/expedia.py`), the trip template (`gitaway/tripimport.py`), and a long paste in the Ask box (`gitaway/say.py` converts it into a plan). Point the prompt's follow-up at the Ask box, and add a few Booking.com, GetYourGuide and car-rental confirmation emails as fixtures so the AI convert handles them. Confirmation numbers stay out of titles and URLs, as now.
- **Later, not this week:** a forwarding address (trips@gitaway.me) needs an inbound-mail provider and a webhook; a statistics-API job could match SubIDs to bookings and nudge "looks like you booked a stay".

**The path to real in-app inventory:**

| Route | Gate | What it gives |
|---|---|---|
| Aviasales Flight Search API | **50,000 confirmed monthly active users**, with screenshots; no exceptions [verified] | Live fares in-app |
| Expedia Rapid (lodging) | Partner application, then a site review against the launch requirements before the key leaves "restricted development mode" ([getting started](https://developers.expediagroup.com/docs/products/rapid/setup/getting-started)) [verified]. **No traffic threshold is published** [unverified] | Search and book in-app (Expedia Collect) |
| Expedia XAP (lodging, flights, cars, activities) | Intake form, then an account manager issues keys ([XAP](https://developers.expediagroup.com/xap/products/xap/set-up/getting-started)) [verified] | Search and book |
| Expedia Travel Redirect API | **New applications paused** [verified] | Listings with a redirect |
| Booking.com Demand API | Managed affiliate partners only ([prerequisites](https://developers.booking.com/demand/docs/getting-started/prerequisites)) [verified in the earlier research] | Search; booking if enabled |
| LiteAPI (hotels) | Self-serve today (see the earlier research) | Real bookable hotel rates in-app, with LiteAPI as merchant of record. This changes GitAway from "sends you away" to "takes the booking"; product decision first |

The honest order: send traffic through tracked links, count bookings per lane in the Travelpayouts reports (by SubID), and apply to Expedia (Rapid or XAP) once there are monthly bookings to show. None of these partners publishes a number, and the only hard threshold found is Aviasales' 50,000 MAU.

## Open questions

- Aviasales results for SFO/LAX→RNO: confirm on a real phone (headless got a captcha).
- Vrbo, Expedia, Hotels.com and Trip.com deep links: bot walls here. Open one on a phone before showing them.
- Whether a Booking.com tracked link from the partner-links API keeps `checkin`, `group_adults` and `age`. Run the live probe with the token.
- Data API coverage on thin US routes (SFO-RNO, LAX-RNO): needs the token.
- The Expedia-on-Travelpayouts rate: the directory (1.35 to 3.6%) and the offer page (4.20 to 6.72% of GBV on hotels) disagree.
- Affiliate programs for Vail Resorts / Epic or Alterra / Ikon: none found. Ask them directly if ski becomes a focus.
