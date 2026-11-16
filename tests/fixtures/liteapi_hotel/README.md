LiteAPI `/data/hotel?hotelId=` and `/data/reviews?hotelId=&limit=&getSentiment=true` for Hilton Los Angeles Airport, a live key, 2026-11-16 (F-275, D-860).
Trimmed (16 photos of 112, 4 rooms, 24 facilities of 78, 8 reviews) and put into LiteAPI's own field names (hotelImages, rooms[].roomName, bedTypes, hotelFacilities,
checkinCheckoutTimes; reviews `data` + `sentimentAnalysis`) from docs/design/matrix-v3/hilton-live-sample.json. The text is real guests' text: tests must escape, never trust it.

`reviews100.json` (F-278): shaped like `/data/reviews?limit=100&getSentiment=true` (data newest first, `sentimentAnalysis`, `total`), made by a seeded script, not real guests: 100 reviews over 18 days, 64 with words, types couple 51, solo_traveller 28, extended_group 13, family_with_children 8, `source` "nuitee" on each review (the live field name is assumed), the newest ten averaging 9.1. The sentiment block is reviews.json's.
