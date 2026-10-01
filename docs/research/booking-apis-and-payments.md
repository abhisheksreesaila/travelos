# Booking APIs and payments for GitAway phase 2

Researched 2026-10-01. Primary sources (official developer docs, partner pages, pricing pages) are linked inline.
Markers: **[verified]** read on the owner's page; **[secondary]** only found in a third-party write-up or search snippet of the owner's page, not confirmed on the owner's page; **[unverified]** not found published anywhere authoritative.

## TL;DR

- **"Free APIs with real inventory" mostly means affiliate links or a sandbox.** Real bookable inventory needs either a self-serve aggregator (Duffel for flights, LiteAPI for hotels) or partner approval (Expedia, Booking.com, Hotelbeds production).
- **Amadeus Self-Service is gone.** Its keys were switched off on 2026-07-17, and new sign-ups were paused before that. Only Amadeus Enterprise (a sales contract) remains.
- **Expedia Rapid is approval-only.** You can test against `test.ean.com` only after Expedia accepts you as a partner. Expedia publishes no margin figures.
- **Fastest real demo:** Duffel test mode for flights, a LiteAPI sandbox for hotels, and an affiliate deep link for cars. All three are self-serve today.

## 1. Inventory APIs

### Flights

| Provider | Access | Cost | Sandbox | Search / book | Rate limits | Terms that matter |
|---|---|---|---|---|---|---|
| **Amadeus Self-Service** | **Closed.** Keys disabled and portal inaccessible from 2026-07-17. Enterprise customers are unaffected. [secondary: [PhocusWire](https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers), [Ignav migration note](https://ignav.com/docs/amadeus-self-service-shutdown)]. Amadeus's own portal is JavaScript-rendered and could not be read. | Enterprise contract only | n/a | n/a | n/a | Don't build on it. |
| **Duffel** | Self-serve sign-up. Live bookings need identity verification plus a card or balance top-up ([help: go live](https://help.duffel.com/hc/en-gb/articles/360019685579-How-do-I-go-live-once-I-ve-built-my-integration)) [secondary: search snippet] | $3/order, plus 1% of order value for "managed content", $2 per paid ancillary, 2% FX. Excess searches cost $0.005 each above a 1500:1 search-to-book ratio. No upfront fee ([pricing](https://duffel.com/pricing)) [verified] | Yes. `duffel_test_` tokens and a fake airline, "Duffel Airways" (ZZ), with full search, order, cancel and change ([test mode](https://duffel.com/docs/api/overview/test-mode)) [verified] | Search **and book** (tickets real airlines) | Not found on a readable page [unverified] | Paying with the customer's card: the airline is merchant of record and **no markup is allowed**, but you carry chargeback and fraud liability. Paying from your Duffel Balance lets you set your own price and markup ([payments guide](https://duffel.com/docs/guides/collecting-and-making-payments)) [verified] |
| **Kiwi.com Tequila** | Self-serve sign-up reportedly closed since about May 2024. Now B2B partners only, by application or invitation [secondary: [phptravels](https://phptravels.com/blog/comprehensive-guide-to-flights-api-integration); [tequila.kiwi.com](https://tequila.kiwi.com/) is JavaScript-rendered and could not be read] | Revenue share [unverified] | Unknown | Search and book (for approved partners) | Unknown | Treat it as unavailable to a new startup. |
| **Skyscanner Travel API** | Apply. For "established business[es] with a large audience". About 2-week review, then an account manager ([partners page](https://www.partners.skyscanner.net/product/travel-api)) [verified] | Not published. You earn commission on traffic sent | Not stated | **Search only.** Booking happens on the partner site you redirect to | Not stated | A metasearch redirect model. GitAway is too small to qualify today. |
| **Travelpayouts (Aviasales)** | Self-serve. The Data API works right after sign-up; the real-time flight search API needs you to join the Aviasales program ([data API](https://support.travelpayouts.com/hc/en-us/articles/203956163), [requirements](https://support.travelpayouts.com/hc/en-us/articles/203956083-Requirements-for-Aviasales-data-API-access)) [secondary: support pages blocked fetch; content from search snippets] | Free. You earn affiliate commission [rate unverified] | The Data API returns **cached** prices (up to about 7 days old), not live fares | Search or price data only. **Booking happens on Aviasales or the airline** | 30 to 600 requests/min per endpoint; real-time search is 200 requests/hour per IP ([rate limits](https://support.travelpayouts.com/hc/en-us/articles/4402565416594)) [secondary] | Cached prices are fine for "from $X" inspiration but are not bookable quotes. |
| **LiteAPI (Nuitée)** (also does flights now) | Self-serve (see hotels below) | Flights: 1% ticketing fee (EUR 2 to 10), EUR 25 per change, EUR 0.005 per search above 1500:1 ([pricing](https://docs.liteapi.travel/reference/api-pricing-usage-costs)) [verified] | Sandbox key | Search and book | Not stated | Newer offering. Coverage not assessed. |

### Hotels

| Provider | Access | Cost | Sandbox | Search / book | Rate limits | Terms that matter |
|---|---|---|---|---|---|---|
| **LiteAPI (Nuitée)** | **Self-serve.** Free sandbox key with no card. Production needs a payment method and a payout method ([keys](https://docs.liteapi.travel/docs/getting-a-sandbox-key)) [verified] | Rates → prebook → book is free at a "reasonable" look-to-book ratio (5000:1 per a docs snippet [secondary]). Price-index calls cost $0.05, places calls $0.01 ([pricing](https://docs.liteapi.travel/reference/api-pricing-usage-costs)) [verified] | Yes | Search **and book** | Not published [unverified] | You earn a `margin` % on top of the net rate (`margin=15` adds 15%). LiteAPI can be merchant of record through its payment SDK, or you are merchant and sell at net plus your own fee. Commission locks at guest checkout and is paid weekly ([commission](https://docs.liteapi.travel/docs/revenue-management-and-commission)) [verified] |
| **Expedia Rapid** | **Partner approval first.** The key stays in "restricted development mode" until a site review approves launch ([getting started](https://developers.expediagroup.com/docs/products/rapid/setup/getting-started)) [verified] | No API fee published. You earn margin or commission on bookings [figures unverified] | `https://test.ean.com/`: "will not result in actual property reservations or credit card charges" [verified] | Search and book (lodging; Rapid also has a car API) | Not published. "The system monitors anomalous API traffic" [verified] | Launch requires site review against Expedia's launch requirements (display, terms links) ([index](https://developers.expediagroup.com/rapid/setup/launch-requirements)). Detailed caching and display rules were not readable [unverified]. |
| **Hotelbeds (HBX Group) APItude** | Free registration gives an evaluation key. Production needs a profile, a commercial assessment and certification ([portal](https://developer.hotelbeds.com/)) [verified] | No API fee published. Wholesale net rates [commercial terms unverified] | Evaluation at `api.test.hotelbeds.com`, **50 requests/day**, then 403 errors ([docs](https://developer.hotelbeds.com/documentation/)) [verified] | Search and book (booking after certification) | 50/day in evaluation; higher after certification | B2B wholesaler: you are expected to be the seller to the traveler. |
| **Booking.com Demand API** | **Managed Affiliate Partner only.** The account manager issues Partner Centre access ([prerequisites](https://developers.booking.com/demand/docs/getting-started/prerequisites)) [verified] | No fee; affiliate commission | Sandbox at a fixed 50 requests/min ([rate limiting](https://developers.booking.com/demand/docs/development-guide/rate-limiting)) [verified] | Search; booking or orders depends on what is enabled for you | Production limits are set per partner; cars/search allows 3000 requests/min [verified] | Don't cache prices or availability; static data may be cached [secondary]. |
| **Booking.com affiliate (links)** | Self-serve through the CJ network ([program](https://www.booking.com/affiliate-program/v2/index.html)) [verified] | Free. Commission rate not on the page [rate unverified; third parties cite 25 to 40% of Booking's commission] | n/a | Links or widgets only. Booking happens on Booking.com | n/a | Booking.com is the merchant. |
| **Amadeus hotels** | Gone with Self-Service (see flights) | n/a | n/a | n/a | n/a | n/a |
| **Duffel Stays** | "Request access" (contact sales). Test tokens available ([guide](https://duffel.com/docs/guides/getting-started-with-stays)) [verified] | Profit share on completed stays; rate negotiated ([pricing](https://duffel.com/pricing)) [verified] | Yes | Search and book | Not stated | Pairs naturally with Duffel flights. |

### Cars

| Provider | Access | Cost | Sandbox | Search / book | Terms that matter |
|---|---|---|---|---|---|
| **Booking.com Demand API: cars** | Managed affiliate (as for hotels) | Affiliate commission | Sandbox, 50 requests/min | **Search, then redirect** to cars.booking.com. API booking is in beta, by special permission ([cars overview](https://developers.booking.com/demand/docs/cars/overview)) [verified] | Rentalcars.com is Booking Holdings' car brand. |
| **Rentalcars.com affiliate** | Self-serve through Awin [secondary: [Awin spotlight](https://awin.com/us/news-and-events/interviews/advertiser-spotlight-rentalcars.com)] | About 6% on pay-now bookings, 1% on pay-later [secondary, unverified] | n/a | Links only | Rentalcars is the merchant. |
| **Expedia (Rapid car API, XAP)** | Partner approval. XAP covers lodging, flights, cars, packages and activities; keys come from an account manager after the intake form ([XAP getting started](https://developers.expediagroup.com/xap/products/xap/set-up/getting-started)) [verified] | Not published | XAP: "test with the production API keys directly" [verified] | Search and book | Rapid has its own car launch requirements ([index](https://developers.expediagroup.com/rapid/setup/launch-requirements)). |
| **Skyscanner car hire** | Same gate as Skyscanner flights | n/a | n/a | Search and redirect | n/a |

No self-serve, bookable car API was found that a small startup can use today. Cars realistically start as affiliate links.

## 2. Expedia's partner options

| Option | What it is | Merchant of record | Payment flow | Earnings (published?) | Approval |
|---|---|---|---|---|---|
| **Travel Creator / Affiliate Program** | Links and widgets to Expedia, Hotels.com and Vrbo | Expedia | Traveler pays Expedia on Expedia's site | "**Up to 4%** on every eligible booking". Per-product rates show only after login ([program page](https://partner.expediagroup.com/en-us/solutions/explore-our-affiliate-program)) [verified]. A per-product split (hotels 4%, cars 1.5%, flights excluded, etc.) appears only in third-party write-ups [secondary] | Application. Light for content sites |
| **Rapid API (Expedia Partner Solutions, EPS)**: Expedia Collect | Your own booking user interface on Expedia lodging inventory | **Expedia** ([Expedia business models](https://developers.expediagroup.com/supply/lodging/docs/booking_apis/reservations/learn/bus_models/)) [secondary: snippet] | You pass the traveler's card in the booking call; Expedia charges it ("pay now") | Margin or commission not published [unverified] | Partner application, then a site review before launch ([getting started](https://developers.expediagroup.com/docs/products/rapid/setup/getting-started)) [verified] |
| **Rapid**: Property Collect | "Pay later" properties | The **property**. Rapid becomes merchant of record only where SCA (European strong customer authentication) applies ([property collect](https://developers.expediagroup.com/rapid/lodging/booking/property-collect)) [verified] | Traveler pays at the hotel | Not published | As above |
| **Rapid**: Partner as merchant of record | You charge the traveler and Expedia bills you at net (invoice or virtual card) | **You** ([EPS Rapid data-processing terms](https://eglegal.elevate.law/privacy/privacy-contract-terms/partner-data-processing-agreements/expedia-partner-solutions(eps)/eps-rapid) list both "Partner is Merchant of Record" and "Expedia is Merchant of Record") [secondary: snippet] | You collect, then pay Expedia | Your markup over net [figures unverified] | Larger partners. Brings seller-of-travel and payments obligations (section 3) |
| **TAAP (Travel Agent Affiliate Program)** | Booking site for travel agents | Expedia | Agent books on the agent site; Expedia charges | Commission on hotels, cars, activities and packages; **none on standalone air** [secondary: [AltexSoft](https://www.altexsoft.com/blog/travel/expedia-taap-rapid-api-partner-solutions/)] | Agent sign-up. A manual tool, not an API, so irrelevant to an app |

Expedia's eligibility criteria are not public. One third party lists revenue potential, traffic, booking volume and IATA compliance as factors [secondary].

## 3. Payments for an online travel startup

| | **Agency** (supplier charges) | **Merchant** (you charge) |
|---|---|---|
| Who charges the card | Supplier or aggregator (airline through Duffel card payment, Expedia Collect, LiteAPI's payment SDK, Booking.com) | You (for example Stripe), then you pay the supplier at net |
| How you earn | Commission or affiliate share; or LiteAPI margin built into the price | Markup over net, plus service fees |
| Risk you carry | Low; it varies (Duffel still makes you liable for chargebacks on card payments [verified]) | Chargebacks, refunds, supplier failure, holding traveler funds |
| Regulatory load | Lower | Seller-of-travel registration plus trust account or bond; full PCI scope if you touch cards |

**Stripe** ([restricted businesses](https://stripe.com/legal/restricted-businesses)) [verified]:
- **Prohibited:** commercial airlines and cruises, cross-border charter or private airlines, timeshares.
- **Restricted** (needs extra documents and Stripe's approval, which it can revoke): **"Travel reservation services and clubs"**. A GitAway that charges travelers itself needs Stripe's pre-approval. Charging only your own subscription or planning fee, while suppliers take the booking payment, is the low-friction route [our inference].

**Seller-of-travel laws (US):**
- **California:** you must register with the Attorney General, pay **$100 per business location** a year, show the registration number in advertising, and keep a **trust account or a surety bond**. The law covers out-of-state and internet sellers dealing with California residents ([CA AG](https://oag.ca.gov/travel), [registrant FAQ](https://www.oag.ca.gov/travel/reg-faqs)) [verified]. Exemptions include forwarding 100% of traveler funds to a registered seller of travel or the ARC (Airlines Reporting Corporation), and agents of registered sellers who meet set criteria [verified]. California-based sellers must also take part in the Travel Consumer Restitution Fund [verified].
- **Florida:** annual registration with FDACS (the state Department of Agriculture and Consumer Services), **$300**, plus a **surety bond of up to $25,000**. It applies to anyone selling to Florida residents. Fines run up to $5,000 per violation ([FDACS](https://www.fdacs.gov/Business-Services/Sellers-of-Travel)) [verified].
- **Washington and Hawaii** also register sellers of travel. Iowa reportedly repealed its law [secondary: [travellaw.com](https://travellaw.com/page/seller-travel-registration); not checked against state sites].
- Whether a pure affiliate or link-out model counts as "selling" under these laws has not been confirmed. Get counsel before taking traveler money [unverified].

## 4. Recommended path for a small startup

**Demo or MVP (weeks, no approvals):**
1. **Flights:** Duffel test mode now (Duffel Airways). Real fares once live, with no approval gate beyond verification. Start with card payments, so the airline is merchant of record and you need no markup and no Stripe travel approval.
2. **Hotels:** a LiteAPI sandbox now, and real bookable inventory with only a card and payout setup. Let LiteAPI be merchant of record through its payment SDK and earn through `margin`.
3. **Cars:** affiliate deep links (Booking.com/Rentalcars through CJ or Awin, or the Expedia Creator program). No bookable car API is self-serve.
4. **Inspiration prices** ("LA flights from $X"): the Travelpayouts Data API. Cached and free, and must never be shown as a bookable quote.

**Revenue path:**
- **Phase A (agency):** LiteAPI margin on hotels, Duffel Stays profit share once access is granted, and affiliate commission on cars and Expedia links. No traveler money touches GitAway, so the seller-of-travel and Stripe-restricted exposure is minimal [inference; confirm with counsel].
- **Phase B (scale):** apply to Expedia Rapid (EPS) and Booking.com Managed Affiliate once traffic numbers exist; both gate on business review. Consider merchant of record (Duffel Balance markups, Rapid partner-as-merchant) only after registering as a seller of travel in California and Florida and getting Stripe's travel approval.

## Open uncertainties

- Amadeus shutdown: trade press and migration guides only; Amadeus's own page could not be rendered.
- Kiwi Tequila access status, Travelpayouts commission rates, the Booking.com commission tiers, Rentalcars rates and Expedia's per-product affiliate split: all secondary.
- Expedia Rapid margins and partner-as-merchant terms: not published; ask Expedia (EPS) sales.
- Rate limits for Duffel, LiteAPI and Rapid production: not published or not readable.
- Whether a link-out affiliate counts as a "seller of travel": needs legal advice.
