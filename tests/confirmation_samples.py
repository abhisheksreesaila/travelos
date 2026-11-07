"""Synthetic confirmation emails for F-198's paste-back (written for these tests: invented names, addresses and numbers, no real person's data).

Each is what a family would get by copying the body of the partner's confirmation email; the layout follows what the partners' emails look like (labels, then values),
not any one real message. Prices, PINs and card digits are in them on purpose: the readers must never copy those.
"""

BOOKING = """Booking.com
Thanks, Ari! Your booking in South Lake Tahoe is confirmed.
Lakeside Lodge Tahoe
123 Lake Tahoe Blvd, South Lake Tahoe, CA 96150, United States
Booking number: 4021.889.317
PIN code: 7741
Check-in
Saturday, December 19, 2026 (from 4:00 PM)
Check-out
Saturday, December 26, 2026 (until 10:00 AM)
Your reservation
7 nights, 1 room
Guests: 2 adults, 2 children (8 and 11 years old)
Total price: US$2,940
Paid with card ending 4242
"""

AIRBNB = """Airbnb
Your reservation is confirmed
You're going to South Lake Tahoe!
Cozy A-Frame Cabin near Heavenly
Entire home hosted by Jordan
Check-in
Sat, Dec 19, 2026
4:00 PM
Checkout
Sat, Dec 26, 2026
10:00 AM
Address
45 Pine Ridge Rd, South Lake Tahoe, CA 96150, United States
Guests
2 adults, 2 children
Confirmation code
HMAB12CD34
Total (USD) $3,112.50
"""

VRBO = """Vrbo
Your booking is confirmed
Reservation ID: HA-7Q2K9P
Cedar Ridge Cabin with Hot Tub
Property address: 88 Cedar Ridge Dr, Tahoe City, CA 96145
Check-in: Sat, Dec 19, 2026, 4:00 PM
Checkout: Sat, Dec 26, 2026, 10:00 AM
Guests: 2 adults, 2 children
Total: $2,604.00
"""

GETYOURGUIDE = """GetYourGuide
Your booking is confirmed!
Lake Tahoe: Guided Snowmobile Tour with Sierra Views
Date: Monday, December 21, 2026
Time: 10:00 AM
Duration: 2 hours
Meeting point: Zephyr Cove Resort, 760 US-50, Zephyr Cove, NV 89448
Participants: 2 x Adult, 2 x Child (age 8-12)
Booking reference: GYG8XKQ2P
PIN: 4471
Total price: $1,060.00
"""

KLOOK = """Klook
Booking confirmed
Booking reference ID: KLK-55821934
Lake Tahoe Snowshoe Rental and Self-Guided Tour
Participation date: 22 Dec 2026
Time: 9:00 AM
Location: Tahoe City, CA
Units: 2 x Adult, 2 x Child
Total: USD 96.00
"""

CAR = """Enterprise Rent-A-Car
Your reservation is confirmed
Confirmation Number: 1234567890
Pick-up: Reno-Tahoe International Airport (RNO)
Sat, Dec 19, 2026 @ 10:00 AM
Return: Reno-Tahoe International Airport (RNO)
Sat, Dec 26, 2026 @ 3:00 PM
Vehicle: Standard SUV - Jeep Grand Cherokee or similar
Estimated total: $612.40
"""

ALL = {"booking": BOOKING, "airbnb": AIRBNB, "vrbo": VRBO, "getyourguide": GETYOURGUIDE, "klook": KLOOK, "car": CAR}
