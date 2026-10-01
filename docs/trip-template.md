# Trip import template

Fill in the block below (copy it from your Expedia confirmation), then paste the whole block into **Import a trip** (`/trips/import`) in GitAway.

- Delete any section you didn't book: for example, drop `car:` if you're using rides.
- Times are **local times at that airport or place**, in 24-hour `HH:MM`. Dates are `YYYY-MM-DD`.
- Confirmation numbers are only shown to members of your family.
- Lines starting with `#` are comments and are ignored.

```yaml
trip:
  title: LA with the kids            # what the family will see
  destination: Los Angeles
  start: 2026-10-16                  # first day of the trip
  end: 2026-10-20                    # last day of the trip
  booked_on: Expedia                 # where you booked (shown as "Booked elsewhere: Expedia")
  itinerary_number: "7123456789012"  # Expedia itinerary number (optional)

travelers:
  - name: Abhi
    email: you@gmail.com             # family members with an email can be invited to the trip
  - name: Priya
    email: priya@gmail.com
  - name: Kid 1
    age: 7
  - name: Kid 2
    age: 4

flights:                             # one entry per leg (a connection is two legs)
  - airline: Alaska Airlines
    number: AS 1234
    from: SFO
    to: LAX
    depart: 2026-10-16 08:05
    arrive: 2026-10-16 09:32
    confirmation: ABCDEF              # airline record locator
    seats: 12A, 12B, 12C, 12D         # optional
  - airline: Alaska Airlines
    number: AS 1235
    from: LAX
    to: SFO
    depart: 2026-10-20 14:10
    arrive: 2026-10-20 15:37
    confirmation: ABCDEF

hotel:
  name: The Example Hotel Santa Monica
  address: 123 Ocean Ave, Santa Monica, CA 90401
  check_in: 2026-10-16 15:00
  check_out: 2026-10-20 11:00
  confirmation: "987654321"
  room: 2 Queen Beds, Ocean View      # optional
  rooms: 1                            # optional
  phone: "+1 310 555 0100"           # optional

car:                                 # optional; delete if not renting
  company: Hertz
  pickup: LAX, 2026-10-16 10:00
  dropoff: LAX, 2026-10-20 12:00
  confirmation: "H1234567"
  car: Midsize SUV                    # optional

notes: |
  Anything else: allergies, parking codes, who's picking up whom.
```

What GitAway does with it:
- **Calendar:** flights, check-in and check-out go on the trip calendar as booked blocks, marked "Booked elsewhere: Expedia".
- **Car:** if you included one, the car pickup and dropoff appear as small calendar notes.
- **Rides:** with no car, the rides card can schedule (simulated) Ubers timed to your landing and your flight home.
- **Family:** travelers with an email address can be invited to the trip as editors or viewers.
