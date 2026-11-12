# GitAway design system (for Stitch): Direction A

GitAway is a family trip planner: compare the whole trip (flight + stay + drive) across places and dates, then choose it together. Feel: joyful, trustworthy, alive, calm; Apple-level spacing and restraint; dense and useful, never crowded. Light first; dark exists too.

## Colour (keep exactly)
- Canvas: neutral grey `#F2F2F5`. Cards and tiles: opaque white `#FFFFFF`. Quiet fill on a card (pills, hover): `#EDEDF1`.
- Ink `#0B0B0D` (text, the one accent). Secondary text `#5C5C66`, captions `#62626B`. Hairlines `#E3E3E8`, stronger `#D7D7DE`.
- The accent is ink: the primary button is a black pill with white text. No other accent colour.
- Kind colours, solid fills with white text, used ONLY to mark a kind of thing (never a day, never decoration): flight `#4338CA`, stay `#8B2FC9`, car/drive `#15803D`, tickets `#C2410C`, weather `#0369A1`, food `#C92A5E`, see and do `#0F766E`, ride `#FFD43B` (dark text). Each kind has a calm tint for backgrounds: flight `#E4E3FB`, stay `#F1E3FA`, car `#DDF3E4`, weather `#DBEFFA`, tickets `#FCE6DA`, see `#D9F2EF`.
- Good/ok `#1F9D50` on tint `#DDF3E4`; warning text `#6B4A00` on `#FFF1C9`.
- Dark mode: canvas `#000000`, cards `#1C1C1F`, raised `#2A2A2E`, ink `#F5F5F7`, secondary `#A1A1AA`; the accent pill turns white with black text. Kind fills stay the same.

## Type
- Geist for everything (headings 700-800 with tight tracking -0.02 to -0.04em; body 400-500). Geist Mono for prices, times and small codes.
- Phone: body 17, secondary 16, fine print 14, all-caps labels 13; titles 34/24/20. Desktop: body 16, secondary 14, fine 13, labels 12; titles 42/22/18.
- Two-tone headings are welcome: the first clause ink, the continuation in secondary grey.

## Shape and depth
- Pills (radius 999) for every button, chip and tab. Fields 14, cards 20, widgets and panels 26.
- Surfaces are opaque. One soft shadow scale: cards a hairline and a 2px shadow; focal cards and menus a soft 24px shadow; sheets and the tab bar a deeper 48px shadow.
- Translucency only on floating islands (the top nav pill, a folded search island) and the phone's bottom tab bar: ~80% card colour with a background blur, always readable. Nothing else is glass.
- Icons: thin rounded stroke icons in ink, 1.75px stroke. Never emoji.

## Rules
- Colour means a kind, never a day. Day chips are neutral; the selected one is ink.
- One strong focal card per screen (an ink card, e.g. "Up next" or the lit discovery).
- Prices are sample/preview and say their age ("Preview · 4 min ago"). The book button says "Booking opens soon".
- Phone: one floating opaque tab bar at the bottom (Trip, Plan, a centre ink Ask button, Book, Family); 48px targets; bottom sheets, never dialogs.
- Laptop: top islands (brand left; a centred nav pill Trip, Book, Family, Ask; a live Beacon pill and avatar right); fits 1440x900 with no page scroll where possible.
