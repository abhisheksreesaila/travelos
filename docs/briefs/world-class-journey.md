# World-class journey: cover → book → plan → share, and a creator's magic import

Status: approved (founder, 2026-11-14, before an overnight run: "that's the challenge you need to win")

## In the founder's words
"Bottom line I need a world class cover page with immersive content in the cover page, lead you to buy/book with the LiteAPI sandbox matrix, then plan using tools and finally share with Insta... then a creator should paste a blog (choose any popular) and it should work like magic, delighting them... it cannot be a developer website, it needs to be colourful, micro-interactions and immersive."

## The journey
1. **Cover** (signed out, `/`): immersive and colourful, not a grey product page. The story pulls you through: compare the whole trip, plan it together, share it. Every step is a moment (colour, micro-interactions, the words and the picture in step, D-456..D-459). Light by default (D-460).
2. **Book** on the trip matrix (`/plan/matrix`): pick a square and book it through LiteAPI's **sandbox** (prebook, guest details, book, a confirmation), said plainly as a sandbox booking with no real charge. The booked stay becomes the family's trip.
3. **Plan** the trip with the tools that exist (the cockpit, the day view, Ask, the family).
4. **Share** to Instagram: a trip card image (the place's art, the dates, the route, a link back) through the phone's share sheet, a download on a laptop (F-226).
5. **Creators**: paste a popular travel blog post and watch it turn into a trip like magic (the draft appears as it is read, days and stops landing one by one), then publish. The For creators page and Community trips get their own joyful looks (docs/design/joyful-pages/compare.html; the founder had not picked yet, so option A of each is built and the other kept for a switch).

## Look and feel
Colourful (each part its own colour, never a monochrome screen), micro-interactions on every tap and arrival, immersive motion on the springs of tokens.css, phone first, light by default, readable (4.5:1) in both modes.

## Not tonight
Real money: LiteAPI's sandbox only; nothing deploys to gitaway.me until the founder looks.

## The journey, step by step (founder, 2026-11-14 evening: "let's go one by one")
Built and polished in this order; each step is finished before the next starts.
1. **Cover**: done.
2. **Sign-in**: the two halves must contrast (F-240).
3. **"What are you after?"** (F-241): after signing in you don't land on the matrix cold. A search-engine-simple page asks what you want: where, when, who, and what you're into (vegetarian, seafood, beaches, museums...). Submit → a skeleton of the matrix → the matrix fills in. What you said you like is kept for planning.
4. **Matrix**: minimal but dense: the totals plus a few recommendations and facts (no widgets yet). Change nights, open squares.
5. **Opened square → book** (F-242): the hotel, the chosen flight and the weather in one view; switch the hotel or flight in place. **"Book this trip"** is bold and impossible to miss. Booking plays out what really owning it would look like (it spins through the steps), then a confirmation with confetti, then **"Plan this trip"**.
6. **Plan** (F-243, after booking is polished): a simple, themed calendar (think a joyful Microsoft Teams calendar), day and week views, starting empty apart from the flight and hotel it already knows. Add events with a click (later a finger), and family can contribute. It helps: links matched to what you said you like (vegetarian restaurants, seafood places), the top places other GitAway travellers went, existing plans, and weather nudges ("rain Thursday: take an umbrella"). Pictures arranged nicely. Save.
7. **Share** (F-244): the finished plan shares as a scrapbook or book you can flip through, and a creator's pasted blog becomes the same book. 3D book themes come later.
