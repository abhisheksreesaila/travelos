# F-254 Subtract the old app: inventory

Marks: **(a)** the v2 journey, stays. **(b)** still needed by v2 (or a product of its own that v2 does not replace), stays. **(c)** old and replaced by v2: retired, its address redirects (`gitaway/pages/retired.py`).

## (a) The v2 journey

| Module | Routes |
|---|---|
| home, cover | `/` (the cover; signed in goes to the way in) |
| signin | `/signin`, `/login`, `/auth/callback`, `/signout`, `/logout` |
| tripask | `/plan/ask`, `/plan/ask/suggest` |
| tripmatrix, matrixbook | `/plan/matrix` (+ tile, peek, rail, warm, square, save, book, book/confirm), `/start` (redirects into the matrix with its words) |
| planv2 | `/trip/plan` (+ cal, together, write, suggest, thread) |
| booking (new) | `/trip/booking` (what a locked calendar block opens) |
| chatwrites (new) | `POST /trip/family/message`, `POST /trip/talk/message` (the Together drawer's writes) |
| guides, guidepage, guidesheet, forcreators | `/guides`, `/guides/make`, `/guides/make/trip`, `/guides/add`, `/guides/sheet`, guide pages `/trips/<slug>`, `/trips/<slug>/book`, `/creators/import/<token>/book|guide` |
| creatorimport, creatoredit, studio | `/creators/import…` (make a guide, the editor) |

## (b) Still needed

| Module | Why |
|---|---|
| admin, creatorclaim, creatorsettings, creatorstats, creatordrafts, creators | the captain's page (avatar menu), claim links, creator settings and stats, batch drafts |
| family, morning, passkeys | Family members (avatar menu), invites and roles, `/invite`, the morning reminder, Face ID |
| legal, report, crawlers, blogbutton, pwa, sharetarget | privacy and terms, reporting, robots and sitemap, the blog badge, manifest, service worker, offline, the share target |
| tripshare | the share card and `/s/<token>`; `/trip/share` is the Plan page's Share button |
| trips | `/trips/<slug>` (guides, and a family's own published trip), `/save`, `/unsave` (the guide's heart), `/pub/<slug>/<file>` (published photos) |
| tripimport, tripbuild | importing a trip already booked (`/trips/import`, the way in where the matrix does not exist), `/trip/details`, `/trip/delete` |
| partners | `/book/<lane>` (the matrix's flight link), `/go/<offer>`, `/sandbox/…` |
| passes, tab_help, booked, bookedwhere | a booking's boarding passes, the gate view, phone fix and "Change or cancel"; the pieces of `/trip/booking` (`/trip/passes/…`, `/trip/help/flight|pass|phone`) |
| planforme, planview | Plan it for me is its own product (orders, Stripe webhook `/stripe/webhook`); nothing in v2 replaces it. Founder decision whether it stays |
| devart | the designer's `/dev/placeart` (showcase only) |
| `healthz`, `/assets/*` | in main.py |

## (c) Retired (73 addresses, 303 unless noted)

| To `/trip/plan` | To `/plan/ask` | To `/guides` |
|---|---|---|
| `/trip`, `/trip/cockpit` (+ map, pack), `/trip/today`, `/trip/canvas` (+ card, step, move, undo, plan, add, note, actnote), `/trip/map`, `/trip/map/around`, `/trip/block`, `/trip/block/step`, `/trip/add`, `/trip/ask` (+ 6 more), `/trip/family` (GET, thread, quiet, panel, seen, list), `/trip/help`, `/trip/photos…`, `/trip/talk` (GET, items, photo, voice), `/trip/plans`, `/trip/notes`, `/trip/publish…`, `/calendar`, `/trips` (301), `/trips/switch`, `/booked`, `/partners`, `/rides…` | `/plan` (301), `/plan/grid` (301), `/plan/grid/trip`, `/plan/quote`, `/plan/explore`, `/plan/pay`, `/pay`, `/trip/book`, `/trip/new` | `/forks` (301), `/forks/apply`, `/forks/undo`, `/fork`, `/share`, `/share/unpublish`, `/share/done` |

(`/community`, `/discover`, `/for-creators` were redirected to `/guides` by F-262.)

Deleted page modules (29): cockpit, tripcanvas, daycard, daydock, familydock, weekdesk, dayshared, trip, tripadd, tripnew, tab_ask, tab_family, tab_map, phone_tabs, photos, around_ui, plantalk (its page; the message write moved to chatwrites), plan, plan_widgets, stay_detail, flight_detail, pay, rides, tripgrid, forks (the heart moved to trips), publish (the photo route moved to trips), share, tripbook, calendar. Models that only they used went too: cockpit, geopack, say, speak, partners.prices and three smoke scripts. Models and data kept: tripcal, familydb (every table, including the geo pack and rides tables), planedit, members, liteapi, matrixbook, weather, canvas, plantalk, familythread, photos, passes.

## Direction A tokens

`tokens.css` and `base.css` stay: `layout.styles()` loads them on every page including the v2 ones (v2 tokens are added after them), and the family page, admin, legal, sign-in, import and Plan it for me are still built on them. `desk_skin.css` also stays (it holds dead `cz-*` selectors, a follow-up). `topbar.css`/`topbar.js` were trimmed to Book, Plan, Guides and the avatar menu.
