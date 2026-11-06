# Weekend kit: the first paying stranger for Plan it for me

Saturday 7 and Sunday 8 November 2026. Written Friday 6 November; ad limits and policies checked on the web that day (sources at the end).

GitAway sends nothing and spends nothing. You post, you send, you pay for the ads. Everything below is yours to paste.

The offer: **Plan it for me**, $29. An AI agent builds your family's trip in minutes. The proof is your own published family Disneyland trip.

Two addresses appear everywhere. Find and replace them once:

- `{TRIP}`: your published Disneyland trip, `https://gitaway.me/trips/<slug>`. Find it on gitaway.me/creators/stats (each trip's title links to it) or on /admin under "Creators and trips".
- `{OFFER}`: the Plan it for me page on gitaway.me (F-193). Copy its address from the live site.

## 0. Tonight (Friday), before anything goes out

- [ ] gitaway.me runs this branch and F-193. F-182 is waiting for you to say "ship". Without it there is no `{TRIP}` and no `{OFFER}`, so no ads and no posts.
- [ ] Open `{TRIP}` and `{OFFER}` signed out, in a private window on your phone. Both load, and /privacy and /terms open from the footer.
- [ ] Buy it once with your own card, and time it. The ads say "in minutes": if it takes longer, change that line before you publish. Refund yourself in Stripe and check that the refund shows. Write down the AI cost of that one order. That is your baseline.
- [ ] Check that F-193's daily AI ceiling is set (docs/setup.md), so a rush of orders can't run up the model bill.
- [ ] Don't add a Google tag or a Meta Pixel. /privacy promises "We use no tracking or advertising cookies of our own." You will count results by hand instead (section 6).
- [ ] Note your trip's **All time** readers on /creators/stats. You will subtract this number on Sunday.
- [ ] Submit both ad campaigns tonight. Google reviews most ads within one business day and says to submit several days ahead when there is a deadline [9]. Meta usually takes about a day.

## 1. A post for your own network

Post on your own profiles, and message friends you know are planning a trip, one at a time. Before posting in any group (a school class, a parents' WhatsApp, a local Facebook group), read its rules or ask the admin first. Fill in the [brackets] with what really happened; that is what makes the post personal. Keep the refund line only if you will refund people yourself from Stripe.

Long version (Facebook, Instagram caption, LinkedIn):

```text
A personal one. These past months I've been building GitAway, an app for planning family trips together. We just went to Disneyland as a family and planned the whole trip in it. I published it, day by day, with our photos and notes (no names or booking numbers): {TRIP}

Planning it took me [how long it really took], mostly [the part that ate the time]. So I built what I wished I'd had: Plan it for me. You tell it your dates and who's coming, and an AI agent builds your family's trip, day by day, in minutes. Then you change anything you like, and everyone going sees the same plan. It's $29.

I'm looking for the first few families to try it. If you're planning Disneyland, or know someone who is: {OFFER}

If it doesn't help, tell me and I'll refund you. And if you try it, tell me what was wrong with it. That's worth more to me than the $29.
```

Short version (WhatsApp or text, one person at a time):

```text
Hi [name], you said you're doing Disneyland [when]. I just built something for exactly that: you tell it your dates and who's coming, and it builds your family's trip day by day, in minutes. $29, and I'll refund you if it doesn't help. Our own trip, planned in GitAway: {TRIP} Plan it for me: {OFFER}
```

Group version (only where the admin said yes):

```text
Hi all, [admin] said it's OK to share this once. I built an app for planning family trips, and a $29 "Plan it for me": tell it your dates and who's coming and it builds your trip day by day, in minutes. Here's our own Disneyland trip, so you can see what a GitAway plan looks like: {TRIP} If you try it, I'd love honest feedback: {OFFER}
```

Write down who buys because of these posts. They are friends, not strangers: they go on the scorecard, but they don't count as the first stranger.

## 2. Google Search test, $50

| Setting | Value |
|---|---|
| Campaign | Search, goal Website traffic. If Google offers a Smart campaign, choose "Switch to Expert Mode". |
| Budget | **Campaign total budget $50, Fri 6 Nov to Sun 8 Nov.** Three days is the shortest window allowed, and "you will never be charged more than your total budget" [2]. If your account doesn't offer a total budget, set an average daily budget of $12 instead: Google can spend up to twice the daily budget in one day [3], so at worst you spend about $48 over the two days. |
| Bidding | Maximize clicks, with a maximum CPC bid limit of $1.50 [4] |
| Networks | Google Search only. Untick "Include Google search partners" (it is on by default [7]) and "Include Google Display Network". |
| Locations | United States. Under Location options, pick "Presence: People in or regularly in your targeted locations" [8]. |
| Language | English |
| Ad group | One ad group, "Disneyland itinerary", with all three ads below in it. Google suggests at least 2 responsive search ads per ad group, and advises against pinning [1]. |
| Final URL | `{OFFER}` |
| Display path | `disneyland` / `plan-for-me` (for ad C: `family-trip` / `plan-for-me`). Each path field holds up to 15 characters [1]. |

Keywords (paste as they are; quotes mean phrase match, brackets mean exact match):

```text
"disneyland itinerary with kids"
"disneyland itinerary for families"
"disneyland family itinerary"
"disneyland trip planner"
"plan a disneyland trip"
"disneyland vacation planning"
"disneyland 2 day itinerary"
"disneyland 3 day itinerary"
"first time disneyland itinerary"
"disneyland with toddlers itinerary"
"disneyland day by day plan"
"disneyland and california adventure itinerary"
"anaheim family vacation itinerary"
[disneyland itinerary]
[disneyland trip planning]
```

Negative keywords (set on the campaign):

```text
tickets
ticket
jobs
careers
hours
weather
wait times
parking
disney world
orlando
florida
paris
tokyo
hong kong
shanghai
cruise
free
printable
template
reddit
```

Google's limits: headlines up to 30 characters, descriptions up to 90, and each ad needs at least 3 headlines and 2 descriptions [1]. Every line below was counted and fits. None of them uses an exclamation mark, a phone number or gimmicky capitals or repetition [6].

**Ad A: the proof**

| Headline | Chars |
|---|---|
| Disneyland Plan for Your Kids | 29 |
| Built From a Real Family Trip | 29 |
| Your Disneyland Days, Planned | 29 |
| See Our Real Disneyland Trip | 28 |
| Family Trip Plan for $29 | 24 |

| Description | Chars |
|---|---|
| Share your dates and who's coming. AI builds your Disneyland plan, day by day, in minutes. | 90 |
| Made by a parent who planned his own family's Disneyland trip. Change anything. $29. | 84 |

**Ad B: the speed**

| Headline | Chars |
|---|---|
| Disneyland Itinerary, Done | 26 |
| AI Plans Your Disneyland Trip | 29 |
| Your Park Days, in Minutes | 26 |
| Skip the Planning Spreadsheet | 29 |
| One Plan the Whole Family Sees | 30 |

| Description | Chars |
|---|---|
| Answer a few questions and get a day-by-day plan for your family's Disneyland trip. $29. | 88 |
| Everyone going sees the same plan and can change it. Built in minutes, not evenings. | 84 |

**Ad C: no trademark**

| Headline | Chars |
|---|---|
| Theme Park Trip Plan for Kids | 29 |
| Anaheim Family Trip, Planned | 28 |
| Your Family Trip in Minutes | 27 |
| Day-by-Day Trip Plan, $29 | 25 |
| Plan It for Me, by GitAway | 26 |

| Description | Chars |
|---|---|
| Tell us when you go and who's coming. Get your family's trip, day by day, in minutes. | 85 |
| Started from a real family's trip. Share it with everyone going and change anything. $29. | 89 |

Why ad C exists: you may use "Disneyland" as a keyword, but if Disney complains about it appearing in ad text, Google may restrict it [5]. If ads A and B show as limited because of a trademark, ad C keeps the campaign running. Never write "official", and never suggest any tie to Disney.

Why the ads say "AI" and not "agent": a stranger may read "agent" as a travel agent who books the trip for them. "AI" says what the product actually does.

**Stop rule (Google)**

1. It stops by itself at $50 (the total budget).
2. Pause at once if `{OFFER}` or the checkout breaks, or an ad is disapproved. Fix it, then turn it back on.
3. On Saturday at noon and at 6pm, open Insights and reports, then Search terms, and add anything off-target as a negative keyword.
4. If $25 is spent and no new intakes have started since the ads went live, pause. Look at `{OFFER}` on your phone the way a stranger would before you spend the rest.
5. Sunday at 9pm, pause and fill in the scorecard.

## 3. Meta test (Facebook and Instagram), $50

| Setting | Value |
|---|---|
| Objective | Traffic, with the performance goal "Maximize number of link clicks". This needs no pixel. |
| Budget | **Ad set lifetime budget $50**, scheduled from Sat 7 Nov 7:00 to Sun 8 Nov 21:00 Pacific. "You won't be charged more than your lifetime budget for your ad set's results unless you change your delivery settings." A daily budget, by contrast, can run up to 25% over on a good day [11]. |
| Audience | United States, minimum age 25. With Advantage+ audience on, location, minimum age, languages and exclusions are hard limits; everything else is only a suggestion [14]. Suggestions: Parents with preschoolers (03-05 years), Parents with early school-age children (06-08 years), and the interests Disneyland and Disney California Adventure Park. Check that they still exist in Ads Manager, because Meta renames and retires these often. |
| Placements | Manual: Facebook Feed and Instagram Feed only. (My call: for a $50 test, you want clicks from people reading their feed, not stray taps from other apps.) |
| Page | Ads run from a Facebook Page. If GitAway doesn't have one yet, make one first. |
| Link and button | `{OFFER}`, "Learn more" |

Meta's feed guide recommends primary text of 50 to 150 characters and a headline of 27 characters [10]. Both ads below use the same image.

**Ad 1**

```text
We planned our family's Disneyland trip day by day, then built a tool that does it for you. Tell it your dates and who's coming. $29.
```

Headline: `Your Disneyland plan, $29` (25 characters). Primary text: 133 characters.

**Ad 2**

```text
Planning Disneyland with little ones can take evenings. Plan it for me builds your family's trip, day by day, in minutes. $29.
```

Headline: `A family trip in minutes` (24 characters). Primary text: 126 characters.

What not to write: Meta bans ads that assert or imply a personal attribute of the viewer or their family, age included, and ads that ask about one ("Are you...?") [12]. So no "your toddler", no "Parents of 3-year-olds:", no "Are you planning Disneyland?". Talk about your trip and your family, never about theirs.

**Image idea**: 4:5, 1440 × 1800 pixels [10]. Take it from your Disneyland trip photos: your phone in your hand, showing Day 1 of the trip in GitAway, with the park out of focus behind it. Add one short line of text at the top: "Our Disneyland trip, day by day". Keep Disney characters, logos and the castle out of the centre of the picture, because Meta may reject an ad that looks like it infringes someone's trademark or copyright, even before anyone reports it [13]. Keep your kids' faces out too: strangers will see this ad.

**Stop rule (Meta)**

1. It stops by itself at $50 (the lifetime budget).
2. After $20 is spent, if one ad's link clicks cost over $2 each, turn that ad off.
3. The rest is the same as Google: pause at once if something breaks; at $25 with no new intakes, pause and look at `{OFFER}`; on Sunday at 9pm, pause.

## 4. Where not to post

These places ban self-promotion. Posting there risks getting your account banned, and it makes GitAway look like spam.

| Place | Their rule | Source |
|---|---|---|
| r/Parenting | "No linking, promotion, or advertising". It also bans surveys and requests for feedback. | [18] |
| r/WaltDisneyWorld | Blogs, channels and projects go only in the monthly self-promotion megathread, and promotion should be about 10% of your activity there. (And it is about Florida anyway.) | [19] |
| r/Disneyland, r/travel, r/familytravel | Not confirmed: Reddit blocked reading their rules from here. Read each sidebar yourself, and until you have, post no links. Answering someone's question without a link is fine. | none |
| DISboards | You may not solicit customers, generate leads, share affiliate links or promote goods or services without written approval, or you may lose your posting rights. Signatures count too. | [15] |
| Tripadvisor forums | "We do not allow advertisements or solicitations", including links with referrer or affiliate codes. | [16] |
| Nextdoor (main feed and direct messages) | Promotion of a business or paid service must come from a free Business Page, not your personal account (policy of 19 Aug 2026). | [17] |
| Big Disneyland fan and planning groups on Facebook | Each group's admins set the rules, and most ban selling. Read the group's About and Rules first; if they don't say, ask an admin. | none |
| Comments and DMs on other people's posts (bloggers, Instagram creators) | Dropping your link reads as spam, and it would sour the blogger messages in section 5. | none |

Where posting is fine: your own profiles; one-to-one messages to people you know; groups whose admin said yes; a free Nextdoor Business Page [17]; and r/SideProject, which allows posts about things you built [20]. r/SideProject gets you feedback from other makers, not buyers.

## 5. Top 10 blogger claim messages

The branch already writes these messages: `outreach()` in `gitaway/creatorclaim.py`, shown on /admin. Don't rewrite them. To get them:

1. On gitaway.me, sign in with Google using an address listed in `GITAWAY_ADMIN_EMAILS` (Railway, service web). Drafting needs `ANTHROPIC_API_KEY`. Without it, the section says "No AI key is set, so drafting is switched off here."
2. Go to gitaway.me/admin, then "Draft for a creator", then open "From the list of creators (50)". A-priority creators are listed first.
3. Tick 5 and press **Draft the ticked ones** (5 is the most per batch). Each result has a message with that creator's own claim link, and a **Copy the message** button. Copy all five before you leave the page: the link appears only on that page, and GitAway keeps only a hash of it. Then do the next 5.
4. If you lose one, find it under "Drafts and claim links" and press **New link and message**. The old link stops working.

Use the admin page on gitaway.me, not `pixi run draft-creators` on your laptop. The script writes drafts into whichever data folder it runs against, so links made locally don't work on the live site. It also prints only the links, not the messages.

Which 10: the A-priority creators who write about Disneyland, plus one from California.

1. Hawaii Travel with Kids (Marcie Cheung)
2. Trips With Tykes (Leslie Harvey)
3. La Jolla Mom (Katie Dillon)
4. The Wandering Daughter (Astrid Vinje)
5. SoCal Disney Dad (Traver). His example is a YouTube video; if the draft fails, the result says why.
6. Life With My Littles (Chelsea)
7. No Back Home
8. Travels Between (Colleen Lanin)
9. Mommy Mouse Clubhouse (Mindy)
10. Kids Are A Trip (Kirsten Maxwell)

Send each message yourself, by email or through the creator's contact page (the `contact_url` column in `docs/research/creators.csv`). Before you send, add these two lines at the bottom. US law (CAN-SPAM) requires a way to opt out and a postal address in commercial email, and it makes no exception for business-to-business email [21].

```text
P.S. If you'd rather not hear from me about this, reply "no thanks" and I won't write again.
[your postal address]
```

This is the slow lever. A claimed trip gives you another proof page and a blogger's audience, but don't expect an order from it by Sunday.

## 6. Sunday-night scorecard (fill in at 9pm)

| Number | Where to read it | Google | Meta | Network and bloggers | Total |
|---|---|---|---|---|---|
| Ad spend | Google Ads: Cost. Meta Ads Manager: Amount spent. | | | $0 | |
| Visits | Google: Clicks. Meta: Link clicks. Network: your trip's All time readers on /creators/stats now, minus Friday's number. | | | | |
| Intakes started | F-193's count (total only) | | | | |
| Paid orders | Stripe: Payments, succeeded, 7–8 Nov. Split them by asking each buyer. | | | | |
| ...of them strangers | Your note from section 1 | | | | |
| Refunds | Stripe: Payments, Refunded | | | | |
| AI cost | Anthropic Console: Cost, 7–8 Nov (or whichever provider F-193 uses) | | | | |

GitAway does not record where a buyer came from: there are no ad cookies, on purpose. To split orders by channel, email each buyer yourself: "Thanks for trying it. How did you find it?"

Work these out:

- **Cost per click** = ad spend ÷ ad clicks
- **Intake rate** = intakes started ÷ visits
- **Kept per order** = $29 − $1.14 Stripe fee (2.9% + 30¢ [22]) − AI cost per order. A refund also loses the fee, which Stripe does not return [22], and the AI cost.
- **Ad cost per stranger order** = ad spend ÷ stranger orders. It needs to be under about $27 before the ads pay for themselves. This weekend buys a signal, not a profit.

Read the numbers honestly: $100 buys roughly 60 to 100 clicks, which is a small sample. One stranger paying is a real yes. Zero is only a weak no.

**Decide.** If any STOP line is true, it wins.

- **Keep going**, if all of these are true: at least 1 stranger paid; fewer refunds than paid orders; AI cost per order under $5. Next weekend, run the same offer and put the whole $100 on the channel that sold (from what buyers told you). Add the claimed blogger trips as more proof.
- **Change the offer.** Change one thing, then run the same $100 again:
  - Intake rate is 5% or more, but nobody paid. People want it, but not at this price or with this promise. Try $19, or put the refund promise on the page itself.
  - Intake rate is under 5%. The page doesn't convince people. Keep $29, and lead the page with your Disneyland trip.
  - People paid, then half or more asked for refunds. The plans themselves disappoint. Fix the plans before you spend again.
- **Stop the ads** (not the product), if any of these is true: clicks cost over $2.50 on average (fewer than 40 clicks for $100); 80 or more ad clicks brought no intakes at all; AI cost per order is over $10. Next weekend, use only your network and the bloggers.

## Sources (checked 6 Nov 2026)

1. Google Ads Help, About responsive search ads (30-character headlines, 90-character descriptions, 15-character paths, 3 to 15 headlines, 2 to 4 descriptions, at least 2 ads per ad group, pinning): https://support.google.com/google-ads/answer/7684791
2. Google Ads Help, About campaign total budgets (3 to 90 days; "never be charged more than your total budget"; works with Maximize clicks): https://support.google.com/google-ads/answer/10486938
3. Google Ads Help, About average daily budgets (up to twice the daily budget in one day): https://support.google.com/google-ads/answer/2375423
4. Google Ads Help, About Maximize clicks (maximum CPC bid limit): https://support.google.com/google-ads/answer/6268626
5. Google Ads policy, Trademarks (keywords not restricted; ad text may be restricted after a trademark owner's complaint): https://support.google.com/adspolicy/answer/6118
6. Google Ads policy, Editorial (punctuation, capitalization, repetition, no phone numbers in ad text): https://support.google.com/adspolicy/answer/6021546
7. Google Ads Help, About the Google Search Network (search partners are included by default): https://support.google.com/google-ads/answer/1722047
8. Google Ads Help, Prevent clicks outside of your geo-targeted locations (the "Presence" option): https://support.google.com/google-ads/answer/9376662
9. Google Ads Help, About the ad review process (most reviews take one business day; submit several days ahead of a deadline): https://support.google.com/google-ads/answer/1722120
10. Meta Ads Guide, Facebook Feed image ads (primary text 50 to 150 characters, headline 27, 4:5 at 1440 × 1800): https://www.facebook.com/business/ads-guide/update/image/facebook-feed
11. Meta Marketing API, Budgets (lifetime budget is a ceiling; a daily budget may run up to 25% over on some days): https://developers.facebook.com/documentation/ads-commerce/marketing-api/bidding/overview/budgets.md
12. Meta Advertising Standards, Privacy violations and personal attributes: https://transparency.meta.com/policies/ad-standards/objectionable-content/privacy-violations-personal-attributes/
13. Meta Advertising Standards, Copyrights and trademarks: https://transparency.meta.com/policies/ad-standards/intellectual-property-infringement/copyright-and-trademarks
14. Jon Loomer, Advantage+ Audience vs. Original Audiences (which inputs are controls and which are suggestions; Meta's own help page did not load from here): https://www.jonloomer.com/advantage-audience-vs-original-audiences/
15. DISboards posting guidelines: https://www.wdwinfo.com/guidelines.htm
16. Tripadvisor Content & Community Guidelines (the Australian page; the US page did not load from here): https://www.tripadvisor.com.au/Trust-llmsjBtituuk
17. Nextdoor, Changes to self-promotion policy, 19 Aug 2026: https://blog.nextdoor.com/self-promotion-update
18. r/Parenting sidebar, read through a search index of a mirror because Reddit blocks automated reading. Check it on Reddit before relying on it: https://r-weld.vercel.app/r/Parenting
19. r/WaltDisneyWorld sidebar, read through a search index of a mirror, with the same caveat: https://reddit.sudovanilla.org/r/waltdisneyworld
20. Soar, self-promotion rules by subreddit (r/SideProject): https://www.soar.sh/blog/self-promotion-rules-by-subreddit-database
21. FTC, CAN-SPAM Act: A Compliance Guide for Business: https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
22. Stripe pricing (2.9% + 30¢ for US domestic cards; fees from the original payment are not returned on a refund): https://stripe.com/pricing
