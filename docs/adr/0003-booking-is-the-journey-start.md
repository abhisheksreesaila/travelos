# Booking is where the traveler journey starts; the plan is still what gets shared

Revises ADR-0002. The traveler's journey now starts in a booking workspace: flights, hotels and car rental side by side, with a cost ledger and context panes (weather, news, map, events, community itineraries). Paying hands off to the trip calendar, and sharing turns that calendar into a public, forkable itinerary.

**Why:** The traveler is the primary person, and most trips start with "we're going to X, book it". Informed booking is where TravelOS differs from Expedia, and affiliate booking is the revenue path. The plan stays the unit of sharing, forking and collaboration. It is simply born from a booking instead of from search results.

## Consequences

- The landing page has a split hero: "Plan a trip" (booking) and "Get inspired" (community itineraries).
- A fork no longer opens as a standalone copy. It goes into the traveler's forks list and is applied into the empty slots of a current trip's calendar.
- The plan-first routes (`/plans/{slug}`) remain the public, shareable surface.
