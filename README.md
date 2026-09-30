# GitAway

Fork a getaway. GitAway puts everything a traveler needs to book a trip on one screen: flights, stays, getting around, weather, news and a running cost total, side by side. After booking, friends plan the trip together in a shared calendar, and the finished trip becomes a joyful scrapbook itinerary that anyone can fork.

**Status:** design-first frontend on realistic **fake data** (an SFO → LA family trip, Oct 16–20, 2026). No real bookings, payments, accounts or AI yet. The backend (fh-saas, SQLite per tenant) comes later.

## Run it

```bash
pixi install
pixi run dev      # http://localhost:5002
pixi run test
```

## Where things are

- `docs/brief.md`: what we're building and why (approved).
- `docs/plan.md`: tickets F-011 onward and their status.
- `design-system/DESIGN-SYSTEM.md`: GitAway's colours, type, components and motion; `assets/css/tokens.css` implements the tokens.
- `docs/design/`: design handoffs plus the canvas artboard sources in `docs/design/canvas/`.
- `gitaway/catalog.py`: the fake catalog (trip search, offers, cost ledger).
- `gitaway/pages/`: one module per screen, each registering its own routes.
- `CONTEXT.md`: the product vocabulary.

The earlier TravelOS prototype is archived on the `archive/travelos-prototype` branch.
