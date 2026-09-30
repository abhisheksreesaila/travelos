# The travel plan is the atomic unit of value — not search, not the user, not a booking

Every feature in TravelOS is organized around the travel plan as the central object. Search returns plans, not destinations. Discovery surfaces plans, not creators. Collaboration edits a shared plan. Sharing sends a link to a plan. Publishing makes a plan community-visible. The plan carries all context (weather, places, friend recommendations, travel stubs) rather than scattering it across separate pages.

**Why:** The obvious path for a travel site is a search-first booking funnel (Expedia, Kayak) where the destination and dates are the entry point and the output is a transaction. TravelOS inverts this: the plan is the persistent, shareable, forkable object. This is the GitHub-for-travel model—the repo is the unit, not the deploy. This decision is hard to reverse because it shapes every route, every data model, and every UI component. A search-first architecture would put the search form on the landing page and treat plans as a secondary output; a plan-first architecture puts plans in discovery and makes search a filtering tool.

## Considered Options

- **Search-first (rejected):** Landing page is a search form. User enters destination + dates → sees flights, hotels, activities → optionally saves an itinerary. Rejected because this is every existing travel site. It optimizes for the booking transaction, not the planning, sharing, and collaboration loop that differentiates TravelOS.

- **User/profile-first (rejected):** The user's workspace is the home page. Plans belong to users. Discovery is secondary. Rejected because it requires accounts before value, contradicts the anonymous-first publishing model (ADR-0001), and makes the platform about people rather than plans.

- **Plan-first (chosen):** Plans exist independently of users. They can be discovered, viewed, forked, and shared without accounts. The plan carries its own context and quality signals. Users (travelers, collaborators, creators) interact with plans, not the other way around.

## Consequences

- Routes are organized around plan slugs (`/plans/{slug}`, `/plans/{slug}/preview`, `/plans/{slug}/fork`) rather than user workspaces or search results.
- Search was simplified from a multi-section results page to a lightweight plan gateway — all rich context (weather, places, friends, flights/hotels) moved to the plan detail page.
- The creator pipeline generates plans as its output, not creator profiles or content pages. Creator attribution is embedded in the plan, not in a separate creator directory.