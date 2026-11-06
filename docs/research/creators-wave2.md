# Creator list, wave 2 (2026-11-06)

The list is `creators-wave2.csv` in this folder: **162 new creators**, none of them in `creators.csv`. **90 have a verified day-by-day itinerary post at a bookable place.** The other 72 are verified family creators whose post at a bookable place is a guide, a list or a one-day plan, marked `post_is_day_by_day = no`. Nobody has been contacted.

The goal was 150 day-by-day rows. I got 90. The last rounds of searching mostly returned creators already on the list, so the open web probably holds not many more than this. The 72 guide rows are there to give outreach the volume the critique asked for (`critique-2026-11-06.md`: about 8.5% reply, so 150 creators needs 600+ contacts). Each one is labeled so it can't pass for an itinerary.

## Columns

Same as `creators.csv`, plus:

- `contact_email`: only addresses printed on the creator's own homepage, contact, about or work-with-me page (as a `mailto:` link or as text). None were guessed or built from a name. Where a site prints two addresses, both are listed, separated by `;`.
- `robots_ai_blocked`: `yes` if the site's robots.txt disallows the example post's path for `anthropic-ai`, `ClaudeBot`, `Claude-Web`, `GPTBot`, or for all agents (`*`). Rules were matched Google-style (most specific user-agent group, then the longest matching rule).
- `post_is_day_by_day`: `yes` only if the fetched post has Day 1 / Day 2 / … sections (two or more in headings, or three or more in the body text, every body-text case checked by eye).
- `place`: `la` (Los Angeles and Disneyland/Anaheim), `sd`, `hi` (Oahu/Honolulu), `nyc`.
- `est_audience` says `not checked` on every row. Where the site runs Mediavine, Raptive, Journey, Ezoic or Stay22 code, that is noted, since it is a rough sign of size. No traffic was measured.
- `why_fit` gives the day count, the post title, the post's date (`dateModified`, else `datePublished`, from the page's own schema) and how often the post says kid/family words.
- `priority` for day-by-day rows: **A** means 3+ days, 30+ kid/family mentions, dated 2024 or later, not AI-blocked, with an email or contact page. **C** means dated before 2021 or fewer than 12 kid/family mentions (family-light posts). **B** is everything else. Every guide row is **C**.

## Method

1. **Find candidates three ways.**
   - Sitemap crawl: 596 blog domains from Feedspot lists (family travel, Disney mom, San Diego, LA, NYC, Brooklyn and Hawaii mom blogs, theme park, road trip). For each, the robots.txt and sitemaps were read, and post URLs matching a bookable place plus an itinerary word ("itinerary", "3-days", "weekend", …) were picked, with up to 3 posts per place per domain fetched.
   - About 60 web searches by place, trip length, age (baby, toddler, teens), season (Christmas, Halloween, Thanksgiving, spring break) and style (budget, multigenerational, recap).
   - A smaller scripted Brave/Yahoo run. Both engines throttled after a few queries.
2. **Fetch and verify every post** (1,016 fetches: 723 from sitemaps, 293 from search). A row needed HTTP 200, a title or URL naming a bookable place, nothing pointing to Walt Disney World, Disneyland Paris/Tokyo/Hong Kong, upstate New York or day trips out of the city, and, for guide rows, at least 15 kid/family words.
3. **Read the robots.txt** of every kept site and test the post path against the four AI agents and `*`.
4. **Find contacts** on the homepage and up to 6 linked contact, about, work-with-me, media-kit or advertise pages on the same domain.
5. **Drop by hand** (109 domains). Removed: travel agencies and advisor sites (Roam Wisely, Magic Journeys, The One With The Vacation / Paradise Travel Co), apps and programmatic planners (Endless Travel Plans, Family Travel Path, Family Tripwise, FamilyTriplan, Wanderjoy, Hey Robin, Itinara, want.travel), hotels, tourism boards, magazines, tour and rental companies, solo or couple blogs whose post has no family content, and posts at the wrong place. Also dropped: 3 posts that wouldn't load (Maddy's Avenue, The DIY Playbook, Popovers and Passports) and one where the "days" were sidebar links to other trips (Adventures of the 4 JLs).
6. **One row per creator**, keeping each domain's strongest post. A sitemap post beat a search hit when it had more day headings and more kid content. For example, Adventures With Tiff's 7-day Oahu post replaced its 3-day one.

## Counts

| | Oahu (hi) | LA + Disneyland (la) | San Diego (sd) | NYC | Total |
|---|---|---|---|---|---|
| Day-by-day (`yes`) | 18 | 19 | 16 | 37 | **90** |
| Guide / list / one-day (`no`) | 14 | 31 | 10 | 17 | **72** |
| All rows | 32 | 50 | 26 | 54 | **162** |

- **With a public email: 74** (40 of the day-by-day rows, 34 of the guide rows). 145 rows have an email or a contact page.
- **AI-blocked: 18** (11 day-by-day, 7 guide). By agent: anthropic-ai 18, GPTBot 18, Claude-Web 17, ClaudeBot 7, all agents 1. 10 sites block exactly `anthropic-ai`, `Claude-Web` and `GPTBot` but not `ClaudeBot`. All 10 run Raptive ads, which suggests a block list supplied by the network (not confirmed). Only 7 sites block `ClaudeBot` itself.
- **Priority, day-by-day rows:** A 34, B 35, C 21.
- **Disneyland:** only 8 of the 19 day-by-day `la` rows are Disneyland or Anaheim plans. The rest are Los Angeles or Southern California road trips that include it. Disneyland is the biggest group among the guide rows (21 of 31), because most Disneyland bloggers write tip lists or one-day plans, not multi-day ones. 10 guide rows are one-day plans and say so in `why_fit`.
- **Freshness:** 98 posts are dated 2025 or later and 14 are undated.

## Contact first: the top 25

I chose these from the day-by-day rows that aren't AI-blocked. I favoured a public email, a recent post, a multi-day plan with real kid content, and spread across the four places (Disneyland weighted up). Audience size is unknown for all of them.

| # | Creator | Place | Post | Reach | Why first |
|---|---|---|---|---|---|
| 1 | Family Holiday Destinations | la | [Anaheim 7 days for families](https://familyholidaydestinations.com/anaheim-itinerary-7-days-families/) | familyholidaydestinations@gmail.com | A full week in Anaheim, day by day, updated 2026-08: the longest Disneyland-area plan found |
| 2 | Our Family Passport | la | [4-day Disneyland itinerary](https://www.ourfamilypassport.com/the-ultimate-4-day-disneyland-itinerary-to-avoid-crowds/) | hello@ourfamilypassport.com | A pure Disneyland multi-day plan, updated 2026-01, with an email |
| 3 | Tori Pines Travels | la | [10 days in Southern California with kids](https://toripinestravels.com/california-road-trip-itinerary-with-kids/) | tori@toripinestravels.com | 10 day sections covering Disneyland and San Diego, updated 2026-08 |
| 4 | The Baby Abroad | la | [2-day Disneyland with a toddler](https://thebabyabroad.com/the-perfect-2-day-disneyland-itinerary-with-a-toddler/) | no contact page found; try social | A clean 2-day Disneyland toddler plan, the kind families copy |
| 5 | Katie Did What | la | [Our first family trip to Disneyland](https://www.katiedidwhat.com/our-first-family-trip-to-disneyland-disneyland-planning-tips/) | [contact](https://www.katiedidwhat.com/contact/) | A real 3-day family recap from 2025, the authentic voice the product wants |
| 6 | Family Can Travel | la | [3 days in LA with kids](https://www.familycantravel.com/los-angeles-with-kids/) | [contact](https://www.familycantravel.com/contact/) | 3 day sections and 70 kid mentions, updated 2026-05 |
| 7 | Loving This Adventure | la | [LA with kids, 5 days](https://www.lovingthisadventure.com/los-angeles-with-kids-a-doable-5-day-family-itinerary/) | [contact](https://www.lovingthisadventure.com/contact-me/) | First-person 5-day trip with four boys, updated 2026-06 |
| 8 | LathropsGoneAWOL | nyc | [NYC 4 days with kids](https://www.lathropsgoneawol.com/post/new-york-city-family-trip-kid-things-to-do-in-nyc/) | contact@lathropsgoneawol.com | The most kid-dense NYC plan found (157 mentions), budget angle, 2026-05 |
| 9 | Two in a Canoe Family | nyc | [NYC family itinerary, day by day](https://twoinacanoefamily.com/nyc-family-itinerary/) | hello@twoinacanoefamily.com | 5 day sections, a family travel blog |
| 10 | Simply Awesome Trips | nyc | [NYC with kids, 5 days](https://www.simplyawesometrips.com/new-york-city-with-kids-a-5-day-itinerary/) | info@simplyawesometrips.com | 5 day sections, updated 2026-07 |
| 11 | Feathers and Stripes | nyc | [4 days in NYC with kids](https://feathersandstripes.com/4-days-in-nyc-with-kids/) | feathersandstripes@gmail.com | Tight 4-day plan, updated 2026-09 |
| 12 | Jolly Good Travel | nyc | [3 days in NYC with kids](https://www.jollygoodtravel.com/trip-recaps/3-days-in-nyc-with-kids) | samantha.russell@jollygoodtravel.com | A trip recap, updated 2026-10, with a named person's email |
| 13 | DIY Travel Blog | nyc | [5-day kid-friendly NYC](https://diytravelagent.blog/2023/08/15/looking-back-on-a-year-of-working-remotely/) | diytravelagent@gmail.com | 5 day sections, updated 2026-10 (the URL slug is old and doesn't match the title) |
| 14 | Stepwise Wonders | nyc | [NYC with kids 2026 guide](https://stepwisewonders.com/nyc-with-kids-2026-guide-50-best-family-things-to-do-in-new-york-city/) | hello@stepwisewonders.com | A long guide with a 5-day plan inside, 2026-07 |
| 15 | Part Time Tourists | hi | [Aulani with little kids](https://parttimetourists.com/aulani-with-little-kids-the-ultimate-guide-for-babies-toddlers-preschoolers/) | parttimetourists2@gmail.com | 4-day Ko Olina plan with babies and toddlers, 2026-08 |
| 16 | Family of 4 Adventures | hi | [7-day Oahu with kids](https://familyof4adventures.com/7-day-oahu-itinerary-with-kids/) | info@familyof4adventures.com | A week on Oahu, updated 2026-04 |
| 17 | Hawaii's Best Travel | hi | [7 nights in Ko Olina, family](https://hawaiisbesttravel.com/ko-olina-oahu-family-itinerary/) | bryan@hawaiisbesttravel.com | 8 day sections from their own family stay, 2026-10 |
| 18 | Bon Voyage With Kids | hi | [7-day Oahu for families](https://www.bonvoyagewithkids.com/best-7-day-oahu-itinerary-for-families/) | keri@bonvoyagewithkids.com | 7 day headings, a family travel blog |
| 19 | Island + Alpine | hi | [Oahu 7 days](https://islandandalpine.com/oahu-itinerary-7-days/) | islandandalpine@gmail.com | 7 day headings and 45 kid mentions |
| 20 | Helping of Happiness | hi | [5-day Oahu for families](https://www.helpingofhappiness.com/as-the-traveler/2026/oahu-itinerary-for-families) | hill@helpingofhappiness.com | Written in 2026 |
| 21 | Travel With A Plan | sd | [San Diego family, 5–6 days](https://travelwithaplan.com/san-diego-family-vacation-6-day-itinerary-that-the-whole-family-will-love/) | travelwithaplan.jen@gmail.com | 6 day sections covering Legoland, SeaWorld and Coronado |
| 22 | Strong Like My Coffee | sd | [San Diego, toddler-friendly](https://stronglikemycoffee.com/2024/03/15/san-diego-family-vacation-itinerary-very-toddler-friendly/) | kenzie@stronglikemycoffee.com | A nap-paced 5-day plan |
| 23 | Our Routes & Roots | sd | [San Diego with kids, 3–4 days](https://ourroutesandroots.com/2026/02/06/san-diego-with-kids/) | [about](https://ourroutesandroots.com/about/) | 107 kid mentions, 2026 |
| 24 | Kids Eat World | sd | [San Diego 4 days](https://kidseatworld.com/san-diego-itinerary-4-days/) | [about](https://kidseatworld.com/about-me/) | 4 day headings, family food angle |
| 25 | Where the Wild Kids Wander | sd | [3 days in San Diego with kids](https://wildkidswander.com/3-days-in-san-diego-with-kids-itinerary/) | [contact](https://wildkidswander.com/contact-us/) | A family travel blog with a clean 3-day plan |

**Top 10 in one line each:** Family Holiday Destinations (Anaheim week), Our Family Passport (4-day Disneyland), Tori Pines Travels (SoCal 10 days), The Baby Abroad (2-day Disneyland toddler), Katie Did What (first Disneyland trip recap), Family Can Travel (3 days LA), Loving This Adventure (5 days LA), LathropsGoneAWOL (4 days NYC), Two in a Canoe Family (NYC day by day), Simply Awesome Trips (5 days NYC).

## Better example posts for the existing A and B rows

I crawled each A and B creator's sitemap for posts at the four places, plus site searches where the sitemap gave nothing. Every replacement below was fetched and checked. The public emails found on the same pages are listed too, since `creators.csv` has none.

| Existing row | Current example | Better example | Day-by-day? | Public email found |
|---|---|---|---|---|
| Hawaii Travel with Kids (Marcie) | Maui 3-day | [4 days in Oahu, family budget](https://hawaiitravelwithkids.com/4-days-in-oahu-itinerary-family-vacation-on-a-budget/) (hi, updated 2026-10). Also her second site: [NYC in 7 days](https://www.marcieinmommyland.com/kid-friendly-new-york-in-7-days-itinerary/) (nyc) | yes, 4 and 7 day headings | marcieinmommyland@gmail.com |
| Trips With Tykes | Lake Tahoe | none found. Her Disneyland posts are lists, for example [Disneyland with preschoolers](https://tripswithtykes.com/disneyland-with-preschoolers/) | no | none |
| La Jolla Mom | SD planning guide | keep the current post. It holds 3-, 5- and 7-day San Diego plans in body text | yes (body text) | none |
| The Wandering Daughter | SD itinerary ideas | none better. Both her SD post and [2-day Disneyland](https://thewanderingdaughter.com/2-day-disneyland-itinerary/) are idea lists without Day 1/Day 2 sections | no | astrid@thewanderingdaughter.com |
| Your Brooklyn Guide | NYC with kids | keep (3 day headings, 61 kid mentions) | yes | none |
| SoCal Disney Dad | YouTube video | not checked (YouTube) | – | – |
| The Hawaii Vacation Guide | Maui with toddler | [Best 5-day Oahu itinerary](https://thehawaiivacationguide.com/5-day-oahu-itinerary/) (hi). The post is light on kid content (8 kid/family mentions) | yes, 6 day headings | aloha@thehawaiivacationguide.com |
| Life With My Littles | Disneyland toddler tips | none found (no sitemap hits, no itinerary in search) | no | none |
| Kids Are A Trip | Lake Tahoe | [A perfect NYC weekend with kids](https://kidsareatrip.com/how-to-have-a-perfect-new-york-city-weekend-with-kids/) (nyc, 2025-08) | yes, 4 day headings | kidsareatrip@gmail.com |
| No Back Home | Disneyland toddlers | [Disneyland and California Adventure in one day](https://nobackhome.com/disneyland-and-california-adventure-in-one-day/) (la): a one-day plan | no (one day) | none |
| Travels Between | educational Disneyland | none multi-day. [San Diego Zoo itinerary with kids](https://travelsbetween.com/best-of-san-diego-zoo-with-kids/) (sd) is a one-day plan | no | none |
| Mommy Mouse Clubhouse | Disneyland tips | [3 days at Disneyland + everything we ate](https://mommymouseclubhouse.com/everything-we-ate-at-disneyland/) (la, 2026-05) | yes, 5 day headings (food-led) | none |
| A Happy Passport | Oahu week | keep (8 days in body text) | yes | alison@ahappypassport.com |
| Baby Can Travel | SD 6-day | keep (6 day headings) | yes | none |
| The Family Voyage | LA podcast page | [Oahu itinerary: 7 days](https://www.thefamilyvoyage.com/oahu-itinerary-7-days/) (hi, 2026-07) | yes, 7 day headings | none |
| Six Suitcase Travel | SD big family | keep (3 day headings). **robots.txt blocks ClaudeBot and GPTBot** | yes | none |
| MomsLA | 100 things in LA | none found | no | none |
| Zest in a Tote | 2-day Disneyland | keep | yes | zestinatote@gmail.com |
| Our Sweet Adventures | 3 days Disneyland | keep. **robots.txt blocks anthropic-ai, Claude-Web, GPTBot** | yes | oursweetadventures2016@gmail.com |
| Global Munchkins | Disneyland toddlers | [3-day Los Angeles itinerary](https://globalmunchkins.com/destinations/travel-within-the-states/3-day-los-angeles-itinerary/) (la, from 2020) | yes, 3 day headings | none |
| Bridges and Balloons | Disneyland toddlers | [San Diego itinerary, 3 days](https://bridgesandballoons.com/san-diego-itinerary/) (sd, updated 2026-10) | yes, 3 day headings | none |
| Families Go Travel | Lake Tahoe | none at a bookable place (the NYC posts are weekend trips out of the city) | no | none |
| This Is My Happiness | Lake Tahoe | none found | no | none |
| 2 Travel Dads | Planning NYC | [A weekend in Honolulu](https://2traveldads.com/weekend-in-honolulu-hawaii/) (hi), but it has no day sections. Their sitemap is blocked to crawlers | no | none |
| Little Kid Big City | Thanksgiving parade guide | [NYC Valentine's Day family itinerary](https://littlekidbigcity.com/nyc-valentines-day-family-itinerary-kids/): one day, 2018 | no (one day) | none |
| Stroller in the City | NYC holiday guide | [Three days in La Jolla](https://strollerinthecity.com/three-days-in-la-jolla-itinerary/) (sd, 2025-03), but it has no day sections and is a mother-daughter trip | no | none |
| Globetrotting Mommy | 5 things NYC | none found | no | none |
| Bambini Travel | NYC with kids | [Thanksgiving weekend in NYC](https://bambinitravel.com/thanksgiving-weekend-in-new-york-city/) (nyc) | yes, 4 day headings | erin@bambinitravel.com |
| Bon Traveler | Oahu toddler guide | keep. It's a guide (3 nights Ko Olina, 3 nights Waikiki), not day by day | no | jessica@bontraveler.com |
| Hawaii Mom Blog | Maui Ocean Center | none found (sitemap closed, no Oahu itinerary in search) | no | none |

**After the swap:** 15 of the 29 checkable A/B rows have a day-by-day example at a bookable place (7 already did, 8 more with a replacement). The other 14 don't: Trips With Tykes, Wandering Daughter, Life With My Littles, No Back Home, Travels Between, MomsLA, Families Go Travel, This Is My Happiness, 2 Travel Dads, Little Kid Big City, Stroller in the City, Globetrotting Mommy, Bon Traveler and Hawaii Mom Blog. For those 14, use a guide post or ask the creator for a trip they'd like to see drafted. SoCal Disney Dad (YouTube) wasn't checked.

## Caveats

- **Short of the 150 target.** There are 90 day-by-day rows, not 150. Extra searching kept returning the same creators. The 72 guide rows add volume but are a weaker demo, since a list won't draft into a good day-by-day trip.
- **Audience is unknown for every row.** Ad-network code is a weak hint of size and nothing more. Several A rows may be very small (a personal blog with a few posts). That's good for reply rates but bad for reach.
- **"Family-focused" was judged from the post** (kid/family word count) and a glance at the site. A few rows are general travel or lifestyle blogs that wrote one family trip, for example Damsel In Dior (fashion), Reading & Eating (an author's Substack), Full Suitcase and Y Travel Blog. Two Oahu guide rows are family photographers. Hawaii's Best Travel and Stepwise Wonders might turn out to be small businesses rather than one person.
- **Day detection is mechanical.** "Day 1 / Day 2" headings were counted, and the body-text-only cases (18 of them) were read by eye. A post could still split by day without saying "Day N" (for example "Saturday/Sunday" or "Morning in Waikiki"). Such posts would be marked `no` here although they really are plans: some guide rows, such as Pitstops for Kids' "One week in San Diego", may be like that.
- **Dates are the page's own `dateModified`.** Many blogs bump this date without real edits, so "updated 2026" doesn't prove the content is fresh.
- **robots.txt was read once, on 2026-11-06.** Mediavine and Raptive push block lists to their sites, so expect more `yes` over time. A `no` only means the post path isn't disallowed for those agents today. It isn't consent. The trust design (claim before publish) still applies.
- **Emails are only ones the site prints publicly.** A few are personal-provider addresses (Gmail, Hotmail, AOL). Some sites print two. Email still counts as cold outreach, so the critique's points about message wording apply before anything is sent.
- **Places:** `la` includes Los Angeles and Southern California road trips that also go to San Diego. Each row has a single `place`, taken from its strongest post.
- **Verification ran from one machine without a browser.** Sites that block scripted fetches (Cloudflare challenges, 403s) were dropped rather than checked by hand, so some good creators may be missing for that reason alone.
