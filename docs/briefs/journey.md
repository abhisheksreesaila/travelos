# My trip as a journey

Status: approved (founder, 2026-11-18: "unbelievable … I want this … I love it absolutely … do it"), prototype docs/design/journey/index.html (round 2)

## In the founder's words (condensed)
- "Represents journey (like travel) with finer time control and add events … looks more travel and less meeting."
- "You put sunlight and daylight, which is awesome. You can put the weather as well, so they'll get a bird's eye view of what needs to happen."
- Packed schedules: "when you have too many events … I was thinking of a ghostly line where you don't have to put everything if it's too crumpled … just leave it and show it on demand, like when they hover."
- "You need the whole width of the page … you have to use the entire width, which I'm totally fine with."

## What it is
My trip (`/trip/plan`) drawn as a road you scroll along instead of a week grid. Time runs left to right; the scene behind it is the place's own colours and follows the hour at the centre of the view (night, dawn, day, dusk, with the sun or moon on an arc at the place's real sunrise and sunset), greys under cloud and snows or rains when that hour's weather says so.

## Must have
- **The journey view** in `/trip/plan`, using the full width and height of the screen (not the 46rem column), phone and laptop, light and dark (dark keeps the scene; cards follow the mode).
- **Zoom** Trip · Day · Hours (buttons; ctrl or pinch + wheel), keeping the time at the centre where it was; **Now** during the trip.
- **Booked things** (flights, the stay, anything from a booking) come from the booking, carry a lock, cannot be dragged and open the booking as today's locked blocks do. Flights are arcs; the stay is a band under the line from check-in to check-out.
- **Plans**: drag along the road to retime (snaps to 15 min, a bubble says the new time), hover or tap the line to "+ Add at …", written through `planedit` as today, with the same roles (viewers can't write).
- **Weather from `weather.py` only**: each tick's sky and temperature where MET Norway gives an hourly (or six-hourly) forecast, a snow or rain window as a soft curtain over the road with its words, the day's line under each day; typical weather labelled "not a forecast yet"; nothing invented; `weather.notes` shown. With no weather, a plain clear sky by hour.
- **Crowded times**: when plans sit too close for the rows there is room for (at most 3 rows), the extra ones fold into one ghost card ("5 plans, close together", their time span, hollow rings on the line where each one is); hover on a laptop or tap on a phone opens the list; "Spread them out" zooms to Hours there. Booked things are never the ones folded first.
- **Heads up** on a plan only from real facts we already have (the rain nudge from a real forecast).
- **The week grid stays** one tap away (Journey · Grid); Journey is the default.

## Not now
Drawing each place's own landscape beyond its colour (ridges take `--pc` tones; the ten place-art places can come later); weather alerts by push; multi-family overlays.

## Decisions I made (reversible, say if you want otherwise)
- Journey is the default view; the grid is kept for heavy editing.
- The phone keeps the horizontal road (a thumb swipe), cards a little narrower; a vertical phone version only if it feels cramped on a real phone.
- At most three rows of cards, so a packed afternoon never becomes a tower.

## Done when
On the running app, a real trip with a booked stay (and a flight where there is one) shows on the road with its locks, weather from weather.py, a plan can be added, dragged and kept after a reload, a crowded afternoon folds and opens, and the grid is one tap away; phone 390 and laptop 1440, light and dark.
