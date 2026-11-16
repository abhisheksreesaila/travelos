LiteAPI `/data/hotel?hotelId=` and `/data/reviews?hotelId=&limit=&getSentiment=true` for Hilton Los Angeles Airport, a live key, 2026-11-16 (F-275, D-860).
Trimmed (16 photos of 112, 4 rooms, 24 facilities of 78, 8 reviews) and put into LiteAPI's own field names (hotelImages, rooms[].roomName, bedTypes, hotelFacilities,
checkinCheckoutTimes; reviews `data` + `sentimentAnalysis`) from docs/design/matrix-v3/hilton-live-sample.json. The text is real guests' text: tests must escape, never trust it.
