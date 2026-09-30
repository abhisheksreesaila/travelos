# GitAway (formerly TravelOS)

GitAway helps travelers build, adapt, share, and collaborate on travel plans with useful destination context. Travelers can become contributors by sharing their plans; professional creators can also contribute plans that lead viewers back to their original content.

## Language

**Travel plan**:
A traveler's evolving collection of journey choices, activities, and practical knowledge, which can be developed alone or with friends. A plan need not be publicly shared to be useful.
_Avoid_: Booking, blog post, public guide

**Itinerary**:
The chronological schedule assembled from selected travel arrangements and activities, including flight events and hotel check-in and check-out. Unscheduled time is valid; travelers choose how much detail to add.

**Activity**:
An individual itinerary item that travelers can arrange within or move between days of a travel plan.

**Activity recommendation**:
An optional suggestion relevant to a trip's location and dates that a traveler may add to the itinerary. Recommendations do not automatically fill unscheduled time.

**Fork**:
A saved copy of a published travel plan, kept in the traveler's forks list. It retains the full itinerary and is not automatically shortened. A traveler can fork any number of plans.

**Apply (a fork)**:
Previewing a fork's activities placed into the empty slots of a current trip's calendar, around existing bookings and friends' additions, unchecking the unwanted ones, then adding the rest. Applying never replaces existing items.

**Booking workspace**:
The tmux-style screen where a trip starts: flight, hotel and car-rental lanes side by side, surrounded by context panes (weather, news, map, events, community itineraries), with the cost ledger on top.

**Cost ledger**:
The running total of the currently selected flight, hotel and car combination, showing which combination offers the best overall value.

**Traveler**:
A person planning or taking a journey, alone or with others. A traveler may also contribute plans for others to use.

**Viewer**:
A person exploring travel plans or receiving a shared plan, whether or not they currently intend to travel. Viewing is a participation role, not a separate product persona.
_Avoid_: Third persona, prospective traveler (as a requirement)

**Contributor**:
A person sharing travel knowledge through a reusable plan, including everyday travelers and professional creators.
_Avoid_: Influencer (as a synonym for every contributor)

**Professional creator**:
A contributor who also publishes travel content, such as videos or social posts, and can use a shared plan to help people discover that original content.

**Destination context**:
Information relevant to a destination and proposed travel dates, such as weather and local events, that helps travelers make informed decisions.

**Link sharing**:
Giving others access to a travel plan through a link, either open to anyone holding it or restricted to selected recipients. Sharing is distinct from community publishing; viewing and editing are separate permissions.
_Avoid_: Public publishing

**Anyone-with-link access**:
Access that does not require a recipient to sign up or identify themselves; anyone holding a valid link can exercise its granted permission. A link can expire, but no fixed lifetime is inherent to this access mode.

**Restricted access**:
Access limited to selected recipients whose identity must be verified. Identifying a recipient and granting them permission to view or edit are distinct concerns.

**Plan collaboration**:
Working with friends on one shared travel plan, at the same time or asynchronously, including comparing travel options and arranging itinerary activities. Saved edits appear to all participants; payment or PDF export does not split the plan into independent copies.

**PDF itinerary**:
A read-only exported snapshot of the itinerary at a particular time. It does not update when the shared plan changes; participants can return to the shared plan for its current state.

**Plan history**:
An automatically maintained record of saved changes to the shared plan, including when they happened and the contributing participant where known. It is distinct from whether those changes or participant identities are publicly visible.

**Collaborative search**:
Travelers researching options for the same trip, sharing candidate hotels or other arrangements, and discussing them in context before making a choice. It does not imply sharing account credentials or a payment session.

**Access role**:
The permission granted to a trip participant: Viewer, Commenter, or Editor. Roles apply to explicitly invited recipients or anyone-with-link access; having a Gmail account is not itself an editing permission.

**Commenter**:
A participant permitted to discuss travel options and itinerary items without directly changing the shared plan.

**Editor**:
A participant permitted to change the shared travel plan, rather than only view or comment on it. Editing permission alone does not authorize payment.

**Trip organizer**:
The person who creates the shared trip and centrally controls who is authorized to enter payment. The organizer is normally also the payer but can nominate another participant to pay.

**Designated payer**:
The single participant currently authorized by the organizer to enter payment for the group; nomination transfers rather than duplicates that authority. Even the organizer cannot bypass an ongoing checkout, and itinerary editing permission does not grant payment authority.

**Public publishing**:
The optional act of making a reusable itinerary discoverable to the wider TravelOS community, not exposing the private group's discussions, participant details, or payment information. Published plans have no platform username; professional creators may optionally attach external social channels as attribution.
_Avoid_: Link sharing, username, profile

**Published version**:
An edition retained automatically as the contributor edits their public itinerary, with the latest edition shown by default and earlier editions available to inspect and fork. Contribution usually follows travel but may occur while the trip is in progress; public history excludes the private trip's sensitive information.

**Community endorsement**:
A viewer's positive signal that a published itinerary is useful. It is distinct from permission to publish; using endorsements to rank plans is a future discovery capability.

**Payer receipt**:
Payment-related information intended for the payer and delivered to the payer's email, distinct from the itinerary shared with trip participants.

**Anonymous publishing**:
Publicly sharing a plan without requiring a platform username or identity. All community-published plans are anonymous by default; the contributor is identified only by the plan itself—not by a TravelOS username. Professional creators may optionally attach their existing social channels (YouTube, Instagram, etc.) as attribution, but those are external identities, not TravelOS accounts.
_Avoid_: Username, platform identity, pseudonymous
