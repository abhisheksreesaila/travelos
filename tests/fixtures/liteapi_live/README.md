# Live LiteAPI hotel-rates answer (hand-shaped)

`hotel_rates.json` is hand-shaped from a live probe on 2026-11-16 (`scripts/probe_liteapi_prices.py`, San Diego, 3 nights, 2 adults and kids 7 and 10), not a recording:
the probe prints the fields (`offerRetailRate`, `suggestedSellingPrice` on the room type, `retailRate.taxesAndFees` with their `included` flags,
`cancellationPolicies.refundableTag`), and the shape of the rest is the sandbox answer's (`../liteapi/hotel_rates.json`). Two hotels, with the numbers the probe printed:

| Hotel | retail (`offerRetailRate`) | public (`suggestedSellingPrice`) | paid at the hotel |
|---|---|---|---|
| Best Western PLUS Island Palms Hotel & Marina | 337.31 | 387.91 | none |
| Margaritaville San Diego Resort | 361.69 | 415.94 | resort fee 120.00 (`included: false`) |

Hotel ids, offer ids and rate ids are made up ("LIVE-..."); the photos, addresses and ratings are the sandbox fixture's. No key is in this folder, ever.
