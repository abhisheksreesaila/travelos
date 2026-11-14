# Share the trip to Instagram (F-234)

The family finishes planning, taps **Share to Instagram** on the cockpit and posts a card of the trip. Decisions: D-490 to D-495 in `decisions.md`.

- **The card** (`gitaway/sharecard.py`): 1080 x 1350 PNG. The place's art on top (`placeart`; a soft dawn for a place with no art), a paper panel with a ribbon of the kinds' colours, the title, place and month, where from and to, the length, the optional first names, GitAway's mark and the link. `Card` is the only input: no field for a booking, price, email, hotel or address.
- **The share** (`gitaway/tripshare.py`): one row per trip in `community.db` (`trip_shares`, made on first use), a 16-character token that never changes, switches for `names` and `exact` dates (off by default), `off()` to stop. `snapshot()` reads only the title, place, route, dates and the account members' first names.
- **The pages** (`gitaway/pages/tripshare.py`): `GET /trip/share` (the sheet; with `X-Share: 1` a fragment), `POST /trip/share` (the switches), `POST /trip/share/off`, public `GET /s/<token>` and `GET /s/<token>/card.png`. A published trip is linked at `/trips/<slug>` instead.
- **The sheet** (`assets/js/share.js`, `assets/css/share.css`): grows out of the button with GA.motion; Share = `navigator.share({ files })` on a phone, Download and Copy link everywhere.
- **Tests**: `tests/test_sharecard.py`, `tests/test_tripshare.py`, `tests_browser/test_share_card_flow.py` (`F234_SHOTS=<folder>` with `-k screenshots` writes the screenshots and one card PNG; ours are in `docs/report/f234-*.png`).
