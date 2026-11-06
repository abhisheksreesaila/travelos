# Feature brief: creators turn a post into a trip in under a minute

Status: approved (captain's answers, 2026-11-05)

## Why
- Content first: "if you get content, people will come; if people come, they'll book." Goal: 150 creators. Creators have no time, so the whole thing is paste a link, glance at the draft, publish.
- Bloggers already earn from their own affiliate links. GitAway must never take that away, or the good ones say no.

## What it does
1. **Paste anything, get a draft trip.** A blog post link, a YouTube link, an Instagram link, or pasted text. GitAway reads what it can and Claude Haiku 5.5 (`claude-haiku-5-5`, about $0.002 a post) drafts the trip: title, place, days, stops per day with times where known, tips, stickers. Each source does what it honestly can:
   - Blog: the page's text and photos (readable article extraction).
   - YouTube: title, description, chapters (the public page / oEmbed); no transcript unless the creator pastes it.
   - Instagram: Meta blocks reading posts without business approval, so the creator pastes the caption (the link is kept as the source).
   - Pasted text: always works, the fallback for all three.
   A wrong place name is worse than a missing one: unsure stops show as "unnamed stop" for the creator to fix.
2. **Approve in a minute.** The draft opens in the F-181 publish editor (days, notes, tips, photos, cover), with the source card linking back to the post. Nothing publishes without the creator ticking "this is my post" and pressing Publish.
3. **Creators keep their affiliate income.** A creator may paste their own Travelpayouts marker; the Book buttons on their trips use it (and their SubID). No marker: GitAway's. Stated on the For creators page and at sign-up.
4. **Trust + takedown.** Every public trip has "Report this trip"; a report hides nothing automatically but reaches the captain, who can take it down in one click.
5. **A For creators page that sells it in ten seconds.** Paste box first, a live example (the captain's Disneyland trip once published), the three promises: under a minute, your links keep paying you, it links back to your post. Free, terms shown on day one.

## Not now
- Reading Instagram or YouTube transcripts through official APIs (Meta app review; YouTube captions need the owner's OAuth).
- Revenue share, payouts, creator analytics beyond fork and click counts.

## How we'll know
- A real blog post becomes a reviewable draft trip in under a minute, for about a fifth of a cent, and publishes under the creator's name with their marker on the Book buttons.
- 150 creators published (tracked on the admin page).
