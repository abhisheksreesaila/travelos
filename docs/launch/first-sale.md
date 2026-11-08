# First sale: Plan it for me, this weekend

Written Friday 6 November 2026, for Saturday 7 and Sunday 8 November. Facts checked on the web that day (sources at the end). This sits next to `weekend-kit.md` (the network post, the $50 Google and Meta tests, where not to post, the scorecard) and doesn't repeat it.

GitAway sends nothing and spends nothing. You send, you pay, you deliver.

**The offer tonight**: Plan it for me, **$29 founding-family price**. I plan your family's whole trip (Disneyland first; also LA, San Diego, Oahu, NYC) day by day in your GitAway account, check it myself as a parent who just did Disneyland with my kids, and deliver it **within 24 hours of your answers**. Full refund within 7 days.

Two words to keep straight:

- **"Within 24 hours", not "in minutes".** Tonight you build each plan by hand. The ads in `weekend-kit.md` say "in minutes" (the F-193 AI version). If an ad points at tonight's Stripe link, change "in minutes" to "within 24 hours" first.
- **Don't write "normally $49".** In the US a "was" price has to be one you really charged, openly, for a reasonable time [F1]. You haven't charged $49 yet, so say "**$29 for the first 10 families, then $49**", and then really raise it. The Stripe link below stops by itself after 10 payments, which keeps the "first 10" true.

`{PAY}` below is your Stripe Payment Link. `{TRIP}` is your published Disneyland trip, the same as in `weekend-kit.md`.

---

## 1. Sell tonight, before the deploy

### 1a. The Stripe Payment Link (about 10 minutes)

Your Stripe account must be activated for live payments. Do it in the Dashboard, not test mode.

1. Go to **Payment Links**, then **+ New**. Choose **Products or subscriptions** (not "Customers choose what to pay") [S1].
2. **+ Add a new product**:
   - Name: `Plan it for me: founding family`
   - Description (it's the first thing they read, so use the subhead from section 6): `Your family's trip, planned day by day in GitAway, on every phone in the family. Checked by a parent who just did Disneyland with their kids. Within 24 hours of your answers. Full refund within 7 days.`
   - Price: **$29.00, one-off**. Add an image: your phone showing Day 1 of `{TRIP}`, with no kids' faces.
   - **Add product**.
3. **Options** [S2]:
   - **Collect customer names**: on.
   - **Require customers to provide a phone number**: on. You'll text them the questions.
   - **Add custom fields**. Stripe allows 3 at most [S3], and says not to use them for personal or sensitive data [S2], so ask nothing about the kids here:
     1. Dropdown, required, "Where are you going?": Disneyland, Los Angeles, San Diego, Oahu, New York City, Not sure yet.
     2. Text, required, "Roughly when?" (for example "late March").
   - **Limit the number of payments**: 10. Deactivation message: `The 10 founding-family spots are taken. Write to me and I'll tell you when it reopens.`
   - Terms of service checkbox: on, if your Stripe "Public details" lists `https://gitaway.me/terms`.
   - Leave "Let customers adjust quantity" off.
4. **After the payment**: choose **Confirmation page** and replace the default message with this [S4]:

   ```text
   Thank you, you're one of the first 10 families. Within 2 hours I'll text you 6 quick questions. Your plan will be in your GitAway account within 24 hours of your answers. If it doesn't help, tell me within 7 days and I'll refund the full $29.
   ```

5. **Create link**, then copy it. That's `{PAY}`.
6. Pay it once with your own card on your phone and time it. Then refund yourself: **Payments**, then **⋯** next to the payment, then **Refund payment** (a full refund is the default) [S5]. Stripe keeps its fee of about $1.14 (2.9% + 30¢) on a refund [S5][S6]. That's your cost of testing it.
7. Make sure Stripe emails you on every payment, so the 2-hour clock starts when someone pays and not when you next look.

Know these before the money comes in:

- Your first payout usually arrives 7 to 14 days after the first live payment [S7]. Money taken this weekend won't be in your bank this weekend.
- A dispute costs $15 [S6]. The 7-day refund is cheaper than any dispute, so refund at once when asked.
- Stripe restricts "travel reservation services" [S8]. GitAway books nothing, so it's very likely outside that, but that's my reading, not Stripe's. Never say "we book it for you".

### 1b. Fulfilment runbook (about an hour a family)

The family owns the trip, and you work inside their family as an editor. That's how the plan ends up "in their GitAway account" (`docs/family-members.md`).

**T+0, within 2 hours of the payment**: text them the 6 questions (WhatsApp or SMS, to the phone they gave Stripe).

```text
Hi [name], it's [you] from GitAway. Thank you for being one of our first families! 6 quick questions and I'll get started (voice notes are fine):

1. Dates: which days, and which of them are park days? (Or how many park days you'd like.)
2. Who's going: how many adults, and each child's age. (Ages only, no birthdays.)
3. What's booked already: hotel, tickets, flights, car? Just names and dates. Please don't send confirmation numbers.
4. Each person's one must-do: a ride, a character, a meal, a show.
5. Your pace: rope drop or slow mornings? Naps, stroller, early bedtimes? Any height, mobility or food needs?
6. Your email for GitAway, and who else should see the plan (grandparents, the other parent).

Last step, 1 minute: sign in at gitaway.me with that email, open Family, invite me ([your email]) as an editor, then send me the link it shows. That's how I build the plan right inside your account.
```

If they're stuck on the invite step, offer a 5-minute call. Their answers start the 24-hour clock.

**Build it** (in the founder's own account flow, on gitaway.me):

1. Open their `/join/…` link, signed in with the email they invited, and tap **Join**. On `/family`, switch to their family.
2. Create the trip with **Answer a few questions** at `/trips/build`: where, dates, who, flights, hotel, car, notes. Then save it. If they forwarded a booking email, use `/trips/import` instead.
3. Add the plans day by day. On each empty day, **Paste a plan** opens the Ask box. Paste that day as plain lines, like `8:00 rope drop Disneyland, Peter Pan's Flight, then Dumbo`. Check what it proposes, then apply it. For single changes, use the canvas **+ add**.
4. Put the **booking checklist** in the trip's notes, with real dates worked out from their trip. Check each window on Disney's site that day, because they change [D1]:
   - Dining reservations: open 60 days before each day, at 6:00 AM PT, one day at a time [D2].
   - Park reservations: needed for most tickets. The booking window is unclear (sources say 180 or 240 days), so check it [D3].
   - Lightning Lane Multi Pass: bought with the tickets, or else only after the first scan into a park on the day. Single Pass is bought on the day [D4].
   - Virtual queues: join in the Disneyland app at 7:00 AM, and a spot isn't guaranteed [D5].
   - Disneyland Hotel guests: one free Lightning Lane entry per stay since January 2026 [D6].

**Check it, as the parent who just went** (this is what they're paying for):

- [ ] Check every day on your phone, the way they'll see it.
- [ ] Check the park hours for those dates on Disney's calendar, and that no ride in the plan is closed for refurbishment.
- [ ] Check height limits for each child's age.
- [ ] No more than 3 or 4 big rides before lunch for small kids. Put in a midday break or nap, and meals at real times.
- [ ] Every must-do from question 4 is in the plan.
- [ ] Nothing you're unsure of is stated as fact. Write "check" next to it.

**Deliver** (inside 24 hours):

```text
Your plan is ready: open gitaway.me on your phone and it's your trip, day by day. The booking dates are in the notes, starting with [the first one, e.g. "dining for Day 1 opens Thu 15 Jan, 6 AM"]. To share it, invite your family from Family. They'll see the same plan on their phones.

Anything you'd change, just reply. One round of changes is included. When you're happy, you can remove me from your family (Family, then my name).
```

**Close out**: after 7 days, or when they say they're happy, ask them to remove you, or leave yourself. For each order, write down: paid at, answers at, delivered at, minutes spent, refunded? (yes or no). The minutes per order tell you whether $29 by hand is worth it, and what F-193 has to beat.

**Refunds**: Stripe, **Payments**, **⋯**, **Refund payment** [S5]. Don't ask why. Say thank you and ask what was missing.

---

## 2. Warm outreach (the highest-probability channel)

A friend who is already planning, hearing from you personally, is the likeliest first $29. Cold ads are a long shot for a first sale (section 4).

### 2a. The list: 40 names in 30 minutes

Make a sheet with these columns: name, how you know them, kids' ages, trip they mentioned, channel, sent, reply, follow-up, outcome. Go through each prompt below and write down every name that comes to mind. Sort later.

- People who liked or commented on your Disneyland photos. Scroll your own posts, and the stories' viewer lists if you still have them.
- School and daycare parents: the class WhatsApp, the birthday-party regulars, the pickup line.
- Coworkers and ex-coworkers with kids, especially anyone who's asked you "how was Disney?"
- Cousins, siblings, in-laws. Who is overdue for a family trip, or has a kid turning 5 to 8?
- Neighbours. Who did you see on Halloween with little ones?
- Sports, swim, dance and music parents. Church, temple or community groups.
- Friends who moved away (a trip to visit family often includes LA, San Diego or Oahu).
- People who asked you for travel tips, ever.
- Your phone's recent WhatsApp and text threads, from the top down.
- Parents in your founder or tech circles (LinkedIn, Slack groups) who post about their kids.

Score each one: **A** = mentioned a trip in the next 6 months; **B** = has kids under 12 and travels; **C** = might know someone who travels. Send to all the A's first, then the B's. For the C's, ask for a referral, not a sale.

### 2b. Three scripts (personal, not salesy)

Fill in the brackets with something true. One person at a time, never a group blast.

**Text or WhatsApp** (for A's and close B's):

```text
Hey [name]! Random one: since our Disneyland trip I've been building a family trip planner, and this weekend I'm trying a "plan it for me" for the first 10 families. You tell me your dates and the kids' ages, and I plan the whole trip day by day in the app, so everyone sees it on their phone, with the dates to book dining and Lightning Lane. $29, refunded if it doesn't help. You mentioned [Disneyland / Hawaii / that trip]. Want me to do yours? If not, do you know anyone planning one?
```

**Instagram DM** (people who reacted to your Disney photos):

```text
Thanks for the love on our Disneyland pics! I ended up building the planner I wish we'd had: our whole trip is here, day by day: {TRIP}

I'm planning trips for 10 founding families this weekend, $29, and I check every plan myself. If you've got a trip coming up, I'd love to do yours. And if not, a share to a friend who's planning one would mean a lot.
```

**Email** (coworkers, ex-coworkers, the extended family):

```text
Subject: Planning a family trip? I'd love to do yours

Hi [name],

Hope [the kids / the new job / something real] is going well. Since our Disneyland trip with the kids I've been building GitAway, a planner the whole family shares on their phones. Here's our own trip: {TRIP}

This weekend I'm opening "Plan it for me" to the first 10 families: tell me your dates and who's going, and within 24 hours your trip is planned day by day in your GitAway account, checked by me, with a list of what to book and when. It's $29, and I'll refund it within 7 days if it doesn't help: {PAY}

If you're not travelling soon, I'd be really grateful if you'd forward this to someone who is.

[you]
```

### 2c. The follow-up, 48 hours later (only if there was no reply)

```text
No worries if it's not for you! The 10 spots are filling. If anyone comes to mind who's planning Disneyland or a family trip this winter or spring, I'd be really grateful for an intro.
```

Only send it if it's true that spots are filling. If they aren't, cut that line. One follow-up only: no third message.

### 2d. Replies to the 6 likely objections

| They say | You say |
|---|---|
| "I can plan it myself." | "You totally can, I did! It took me [real number] evenings. This is for people who'd rather spend those evenings on something else. Know anyone like that?" |
| "ChatGPT does this." | "It's a good start. When people tested it for Disney, it suggested FastPass, which Disney retired, put a closed ride in the plan and packed the days too tight [C2][C3]. I check the hours, closures and height limits for your dates, and the plan lives where your whole family can see it, with the booking dates in it." |
| "Disney travel agents are free." | "They are, and they're great if you want them to book a package. Disney pays them when you book through them [C4]. I don't book anything. I plan the days around your kids, and you book wherever you like, agent included. Some agents charge $100 to $300 for planning without a package [C5]." |
| "Too expensive." | "Fair. One park day is $104 to $224 per ticket [D7]. The $29 is about not wasting one. And if it doesn't help, I refund all of it." |
| "We're not going soon." | "No rush! Dining opens 60 days before, so the plan is most useful a couple of months out. Want me to message you then? And if you know anyone going sooner, an intro helps a ton." |
| "Is it safe to pay?" | "It's a Stripe checkout, the same one millions of shops use. I never see your card. If you'd rather, plan first and pay after you've seen Day 1." |

That last line is a real option for close friends: pay-after-preview lowers the bar, and a friend's $29 still counts.

---

## 3. Honest positioning against the free options

| Option | Cost | What it does well | What it doesn't do |
|---|---|---|---|
| **Get Away Today** | Free help; earns on tickets and packages | Discounted tickets with a 365-day refund, hotel packages, layaway, phone experts [C6] | No plan made for your family, and its sample itineraries are old (some still mention FASTPASS) [C7] |
| **Authorized Disney agents** (Mouse Fan Travel, Dreams Unlimited) | Usually free if you book through them [C4][C8] | Book packages, apply new discounts, some make custom itineraries [C4][C8] | Free only when you book with them; some charge $100 to $300 for planning or tickets only [C5]; the plan stays a PDF or an email |
| **ChatGPT** | Free | Fast first draft; shared projects for up to 5 people [C1] | Mistakes from out-of-date facts (FastPass, closed rides, wrong virtual-queue rules) [C2][C3]; 90% of AI itineraries in one survey had at least one error [C9]; no live family plan, no booking dates |
| **Touring Plans** | $13.97 a year | Optimized ride orders, crowd calendar, wait times [C10] | You build it yourself; no family sharing listed |
| **Wanderlog** | Free (Pro costs extra) | Shared, editable trip plans [C11] | You build it yourself; not Disney-specific |
| **GitAway: Plan it for me** | $29, refunded within 7 days | Planned for you around your kids, checked by a parent who just went, on every phone in the family, with the booking checklist dated for your trip | **Books nothing, holds nothing, gets no discounts.** Delivered within 24 hours, not instantly. |

**The honest line**: "Agents book, ChatGPT drafts, blogs are generic. I plan your family's days, check them as a parent who just went, and put the plan on everyone's phone with the dates you need to book. Use an agent to book if you like, it works with that."

Don't claim to be cheaper than free, to be more accurate than Disney, or to have anything to do with Disney.

---

## 4. Fast paid channels: what $100 could get you in 48 hours

Ranked by my estimate of the chance of a sale by Sunday night. These are judgment calls, not measurements.

| Rank | Channel | Chance of a sale in 48h | Why |
|---|---|---|---|
| 1 | **Google Search**, high-intent Disneyland planning keywords (set up in `weekend-kit.md` §2) | Low to moderate | The intent is right ("disneyland itinerary with kids"). But $50 buys about 30 to 50 clicks at the kit's $1.50 cap, and a stranger on a new page converts at maybe 1 to 3%, so expect about 0 or 1 sale. Review takes up to one business day [G1], so submit it tonight. Point it at `{PAY}` only if the page they land on explains the offer; a bare Stripe page converts worse. |
| 2 | **Meta feed ads** (`weekend-kit.md` §3) | Low | It finds parents, but not people planning right now. It earns its keep as reach for `{TRIP}`. |
| 3 | **Etsy** | Very low this weekend | Disneyland planners do sell there, but mostly as $3 to $14 do-it-yourself templates [E1][E2][E3]. One done-for-you plan exists, for Walt Disney World [E4]. Etsy allows only services that produce a new tangible item [E5], so a personalized digital plan is a grey area. "Disney" in a title invites a takedown [E6]. A new listing gets only "a small, temporary boost" in search [E7], new sellers wait about 14 days for payouts [E8], and fees are about $3 of every $29 [E9]. Worth a later test, as a "custom family itinerary PDF" listing without "Disney" in the title, not as a weekend lever. |
| 4 | **Facebook Marketplace** | Not allowed | Meta's commerce rules ban selling services and digital products on Marketplace and in buy-and-sell groups [M1]. Don't list it there. |
| n/a | **Local Facebook groups, Nextdoor** | Free, not paid | Post in a group only where an admin says yes (`weekend-kit.md` §4). Nextdoor's newsfeed takes only local businesses, from a Business Page [N1], so it's a poor fit. |

The honest summary: $100 of ads this weekend buys a **signal**, not likely a sale. Your 40 warm messages are the real shot at a first order. Run the ads for the data, and put your hours into section 2.

---

## 5. The weekend, hour by hour

Target: **1 paid order by Sunday 9pm. Stretch: 3.** About 6 hours a day, leaving room for your other projects. Each order you get takes about an hour to fulfil inside 24 hours, so keep the fulfilment slots free.

**Friday night (tonight, 1.5 hours)**

| Time | Do | Messages |
|---|---|---|
| 20:00 | Make the Stripe link (§1a) and test it with a $29 payment and refund. Submit the ads (`weekend-kit.md` §0). | 0 |
| 20:45 | Build the 40-name list (§2a) and score each name A, B or C. | 0 |
| 21:15 | Send texts to your top 5 A's (people answer texts on Friday nights). | **5** |

**Saturday**

| Time | Do | Messages |
|---|---|---|
| 08:00 to 08:30 | Answer last night's replies. Send the 6 questions to anyone who paid. | replies |
| 09:00 to 10:00 | Texts and WhatsApps to the rest of the A's. | **10** |
| 10:00 to 12:00 | Your other projects. Glance at replies once. | 0 |
| 12:00 to 12:30 | Replies and objections (§2d). Check Google search terms (kit §2). | replies |
| 12:30 to 13:00 | Post on your own network (kit §1), with `{PAY}` alongside `{TRIP}`. | **1 post** |
| 14:00 to 15:00 | Instagram DMs to people who reacted to your Disney photos. | **10** |
| 15:00 to 17:00 | Fulfilment slot: build any paid plan (§1b). If none came in, do other projects. | 0 |
| 17:00 to 17:30 | Emails to coworkers and extended family (B's). | **8** |
| 18:00 | Check the ads (kit §2 and §3 stop rules). | 0 |
| 20:30 to 21:00 | Replies. Ask your 2 or 3 warmest "not going soon" people for an intro. | **3** |

**Sunday**

| Time | Do | Messages |
|---|---|---|
| 08:30 to 09:00 | Replies. Deliver any plan that's due (within 24 hours). | replies |
| 09:00 to 09:30 | Last first messages: the remaining B's and C's (referral ask). | **7** |
| 09:30 to 10:00 | 48-hour follow-ups (§2c) to Friday night's 5. | **≤5** |
| 10:00 to 13:00 | Fulfilment slot, or other projects. | 0 |
| 13:00 to 13:30 | Replies. Contact every intro you were given, the same day. | intros |
| 16:00 to 16:30 | Last call to the A's who said "maybe": "Closing the founding spots tonight, want one?" Only if it's true. | **≤5** |
| 21:00 | Pause the ads and fill in the kit §6 scorecard. Add a row for warm outreach: sent, replied, paid, referrals. | 0 |
| Mon to Tue | 48-hour follow-ups to Saturday's messages. | **≤30** |

That's 40 first messages and up to 10 follow-ups by Sunday night. Rough odds, guessed and not measured: 40 warm messages bring 10 to 15 replies, 3 to 5 who are going soon, and 1 or 2 who pay. If none of them pay, ask the 3 warmest why. That answer is worth more than the ad data.

---

## 6. The landing and the offer page: the first 3 seconds on a phone

Tonight the "offer page" is the Stripe Payment Link itself: its product name, description and image are what a parent sees first. Once F-193 ships, use the same words at the top of `{OFFER}`. On the GitAway landing, a short band above the fold that links to `{PAY}` is enough.

On a 390px screen, the first 3 seconds should show, in this order: the headline, the subhead, the price with the refund promise, one button, and one line of proof. Nothing else above the fold.

**Headlines** (pick one):

1. Your Disneyland trip, planned for you.
2. A parent who just did Disneyland plans yours.
3. Your family's park days, planned day by day.

**Subheads** (pick one):

1. Tell me your dates and your kids' ages. Within 24 hours your day-by-day plan is in GitAway, on every phone in the family.
2. Planned around naps, heights and must-dos, with the dates to book dining and Lightning Lane. Checked by a parent who just went.
3. Answer 6 questions. Get one plan the whole family can see, plus a checklist of what to book and when.

**Price line**: `$29 for the first 10 families, then $49. Full refund within 7 days.`
**Button**: `Plan my trip, $29`
**Proof line**: `See our own family's Disneyland trip →` linking to `{TRIP}`.

Words to avoid: "official", "Disney-approved", "we book", "instant", "AI agent" (a parent reads that as a travel agent), "normally $49", and anything that says who the reader is or how old their kids are (Meta's rule, `weekend-kit.md` §3).

---

## Sources (checked 6 Nov 2026)

Stripe

- S1. Create a payment link: https://docs.stripe.com/payment-links/create
- S2. Customize a payment link (custom fields, phone, names, payment limit, terms, and the warning about sensitive data): https://docs.stripe.com/payment-links/customize
- S3. Custom fields, at most 3: https://docs.stripe.com/payments/checkout/custom-components.md?ui=full-page
- S4. After the payment (confirmation message or redirect): https://docs.stripe.com/payment-links/post-payment
- S5. Refunds (Dashboard path; the fee is not returned; 5 to 10 business days to reach the customer): https://docs.stripe.com/refunds
- S6. Pricing (2.9% + 30¢; $15 dispute fee): https://stripe.com/pricing
- S7. Payouts (the first payout is typically 7 to 14 days after the first live payment): https://docs.stripe.com/payouts
- S8. Restricted businesses ("travel reservation services and clubs"): https://stripe.com/legal/restricted-businesses

Pricing law

- F1. FTC Guides Against Deceptive Pricing, 16 CFR 233.1 (former price comparisons): https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-233

Disneyland dates

- D1. Disneyland Resort guest services: https://disneyland.disney.go.com/guest-services/
- D2. Dining reservations, 60 days ahead, from 6:00 AM PT: https://disneyland.disney.go.com/guest-services/priority-reservations-hotel-guests/ and https://plandisney.disney.go.com/question/dining-reservations-open-length-stay-book-one-time-one-570839/
- D3. Park reservations (the window is uncertain; check it): https://www.undercovertourist.com/blog/disneyland-park-reservations/
- D4. Buying Lightning Lane Multi Pass ahead (Disney Q&A, May 2026): https://plandisney.disney.go.com/question/prepurchase-lightning-passes-go-ca-disneyland-park-638512/
- D5. Virtual queue: https://disneyland.disney.go.com/guest-services/virtual-queue/
- D6. The hotel guest Lightning Lane entry (since January 2026): https://disneyland.disney.go.com/guest-services/extra-magic-hour-early-admission/
- D7. Tickets, $104 to $224 for a 1-day ticket by date: https://disneyland.disney.go.com/tickets/

Alternatives

- C1. ChatGPT Projects, sharing on the Free tier: https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt
- C2. Touring Plans tests ChatGPT on a Disney plan (Oct 2025): https://touringplans.com/blog/chatgpt-says-what-ai-plan-disney-vacation/
- C3. Mickey Visit asks ChatGPT about Disneyland (retired FastPass and MaxPass): https://mickeyvisit.com/we-asked-chatgpt-if-you-could-go-to-disneyland-what-would-you-do-it-gave-some-advice-you-definitely-shouldnt-follow/
- C4. Authorized Disney Vacation Planner, how agents are paid (an agency's own explainer): https://magicguides.com/what-is-an-authorized-disney-vacation-planner/
- C5. Agencies that charge fees: https://travelingears.com/disney-vacation-design-fee/ and https://insidethemagic.net/2024/01/disney-travel-agents-charging-guests-wrongly-jc1/
- C6. Get Away Today, tickets, layaway and planning guide: https://www.getawaytoday.com/disneyland-resort-tickets, https://getawaytoday.com/layaway, https://getawaytoday.com/ultimate-disneyland-planning-guide
- C7. Get Away Today sample itinerary (2015): https://www.getawaytoday.com/blogs/2015-02-16/disneyland-the-perfect-spring-break-itinerary
- C8. Mouse Fan Travel ("NEVER a fee"): https://www.mousefantravel.com/ and Dreams Unlimited: https://www.dreamsunlimitedtravel.com/packages/
- C9. A survey that found errors in AI itineraries: https://travolution.com/news/marketing/survey-finds-chatgpt-itineraries-to-be-riddled-with-inaccuracies
- C10. Touring Plans, Disneyland membership: https://touringplans.com/disneyland-resort/join
- C11. Wanderlog: https://apps.apple.com/us/app/wanderlog-travel-planner/id1476732439

Channels

- G1. Google Ads review process: https://support.google.com/google-ads/answer/1722120
- E1. Etsy, an editable Disneyland planner: https://www.etsy.com/listing/1102996754/editable-disneyland-vacation-planner
- E2. Etsy, Disneyland planner market: https://www.etsy.com/market/disneyland_planner
- E3. Etsy, a Disneyland Google Sheets planner: https://www.etsy.com/listing/4306793548/disneyland-trip-planner-google-sheet
- E4. Etsy, a custom Walt Disney World itinerary service: https://www.etsy.com/listing/1732843844/custom-theme-park-itinerary-wdw
- E5. Etsy, what can I sell (services): https://help.etsy.com/hc/en-us/articles/360024112614-What-Can-I-Sell-on-Etsy
- E6. Etsy Seller Handbook on intellectual property: https://www.etsy.com/seller-handbook/article/1075628311049
- E7. How Etsy search works: https://www.etsy.com/seller-handbook/article/how-etsy-search-works/375461474487
- E8. Etsy, when new sellers get deposits: https://help.etsy.com/hc/en-us/articles/360002080688-Why-Hasn-t-My-Money-Been-Deposited-Yet
- E9. Etsy fees: https://help.etsy.com/hc/en-us/articles/360000344908, https://help.etsy.com/hc/en-us/articles/360035902374, https://help.etsy.com/hc/articles/115015628847
- M1. Meta Commerce Policies (no services, no digital products): https://www.facebook.com/policies_center/commerce
- N1. Nextdoor business posting guidelines: https://help.nextdoor.com/s/article/Business-posting-guidelines?language=en_US
