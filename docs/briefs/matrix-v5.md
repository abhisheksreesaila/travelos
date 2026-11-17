Status: approved (founder, 2026-11-16. On round 2: "much, much better … I like the Harbour … the Fill and the Light as default". On the fly-around: "build it now. I love it … that's pretty much what I wanted to know all this while". On email: "once you finish the booking, you have to send emails … Resend … works out really well")

# The matrix v5: show what others hide

## In the founder's words (condensed)
- **Contrast.** Even in light mode, frosted glass needs a deep ground behind it. The art should be like Omarchy's themed wallpapers and should gel with the logo. Harbour is the pick for now.
- **Extra info has to invite a tap.** The Fill chips have a gradient, a teaser line and a count.
- **"It still reads like any other site."** The hotel should be a decision dashboard:
  - the score and the last-100 trend (loved);
  - the category bars (loved: "it paints the picture");
  - a review drawer: "click, see, close".
- **What others hide, we show proudly:** parking, the resort fee, the shuttle, refundability, kid-friendliness. Unusual items are separated out. The ordinary ones stay, but quietly.
- **Stay and flights must be obviously different.** More rooms means a scrolling row. The photo scrubber was dropped ("too much stress on the page"), so the gallery stays the mosaic and lightbox.
- **See it from above.** "It paints a picture as to what the landscape is … puts various pins … that's pretty much what I wanted to know." Start basic and give a flavor. Build something more impressive once margins allow.
- **Emails after booking.** Send through Resend, the provider set up for the domain.

## Designs (approved prototypes)
- docs/design/matrix-v5/index.html: the ground, the chips, the fine print, the dashboard, the review drawer, the rooms row, the stay and flight zones (the prototype's scrubber is not built).
- docs/design/flyaround/index.html: satellite and map views plus truth pins, and photoreal (Google 3D Tiles) on tap.

## Rules
- **Never invent a fact.** A fee, policy, facility or pin is shown only when LiteAPI, OpenStreetMap or Google gave it. Otherwise say "not listed". Sample data is labelled as such.
- **Nothing heavy loads before a tap.** Closing frees the map. Photoreal is capped per day on the server, because each open is a billed Google root request.
- **Email holds only what the booking needs.** It is sent once, off the request thread, and never logs the guest's address. With no SMTP settings, nothing is sent and nothing breaks.

## Out of scope now
- Flights booked here (F-276).
- Photoreal beyond one orbit and pins.
- The Aerial View video.
- SMS and push notifications.
