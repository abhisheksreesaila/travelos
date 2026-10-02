"""Made-up Expedia itineraries in the layout of the real PDF (fake hotels, numbers and people), in the three text orders it comes out in:
pdftotext's plain order (PLAIN), its -layout order (LAYOUT) and pypdf's (PYPDF), plus a tiny PDF writer for the upload tests."""

FOOTER = """Expedia support
Contact Expedia if you need help managing this itinerary.

Phone number
+1-555-010-0000
"""

PAYMENT = """Payment details
Room price
Sun, Oct 4

$111.11

Taxes & fees

$22.22

Total

$133.33

Paid
[Visa 4242]

Book now and save
Prices shown after $9.99 savings
"""

ROOM_PERKS = """Silve r

Your Silver status got you an extra perk.
•

Your VIP perk: Free self parking

Mention your Silver Expedia Rewards status at check-in to collect your exclusive
perk.
Learn more about VIP access

"""

CAR_PLAIN = """Car rental in Burbank
Oct 4, 2026 - Oct 10, 2026

Avis
+1 555-010-0101
Confirmation: #Q123X456789
Expedia itinerary: 70000000000001

Reservation details
Pick-up

Drop-off

Sun, Oct 4

Sat, Oct 10

6:30pm

11:30am

Pick-up location
Avis
1 Sample Way Hollywood-Burbank Airport, 100 Test Road 1st Floor
Burbank 91505

Hours of operation
6:00am - 11:00pm

Rental counter phone number
+1 555-010-0101

\x0cRental information
Fullsize
Nissan Altima or similar
2 or 4-Door Car
5 passengers
Reserved for
Casey Driverson
Amenities
Air conditioning
Automatic transmission
Important information
International rentals may have different driver license requirements. Please check
what exact documentation is required.
Additional charges or restrictions may apply for drivers under 25.

Payment details
Car rental fee

$400.98

Total

$400.98
Paid
[Visa 4242]

Rental fees are due at pick-up.

"""

STAY1_PLAIN = """Stay in Valencia
Oct 4, 2026 - Oct 6, 2026

Maple Grove Inn & Suites
Confirmation: 055512345
Expedia itinerary: 70000000000002

Reservation details

\x0cBooked

Check in

Check out

Sun, Oct 4

Tue, Oct 6

3 PM

11:00 AM

Check in and special instructions
Check-in time starts at 3 PM
Check-in time ends at midnight
An adult age 18 or older must assume all liability for the booking.

Location
1 Example Road, Valencia, CA, 91355 United States of America

Room details
""" + ROOM_PERKS + """Standard Room, 2 Queen Beds, Non Smoking,
Refrigerator & Microwave
Reserved for
jordan TESTERSON, 3 adults, 1 child
Included amenities
Full Breakfast
Requests
Nonsmoking

\x0c""" + PAYMENT + "\n"

STAY2_PLAIN = """Stay in Burbank
Oct 6, 2026 - Oct 7, 2026

Sample Suites Burbank Airport
Confirmation: 8754000011
Expedia itinerary: 70000000000003

Reservation details
Booked

Check in

Check out

Tue, Oct 6

Wed, Oct 7

3 PM

11 AM

Check in and special instructions
Check-in time starts at 3 PM

\x0cLocation
2 Sample Ave, Burbank, CA, 91504 United States of America

Room details
Studio, 2 Double Beds, Non Smoking
Reserved for
Jordan Testerson, 2 adults
Requests
Nonsmoking

Payment details
Room price
Tue, Oct 6

$174.99

Total

$195.92

Pay at property

"""

PLAIN = CAR_PLAIN + STAY1_PLAIN + STAY2_PLAIN + "\x0c" + FOOTER

# -layout: columns side by side, with runs of spaces between them
LAYOUT = PLAIN.replace("Pick-up\n\nDrop-off\n\nSun, Oct 4\n\nSat, Oct 10\n\n6:30pm\n\n11:30am\n",
                       "Pick-up                                 Drop-off\nSun, Oct 4                              Sat, Oct 10\n6:30pm                                  11:30am\n") \
                .replace("Check in\n\nCheck out\n\nSun, Oct 4\n\nTue, Oct 6\n\n3 PM\n\n11:00 AM\n",
                         "Check in                                Check out\nSun, Oct 4                              Tue, Oct 6\n3 PM                                    11:00 AM\n") \
                .replace("Check in\n\nCheck out\n\nTue, Oct 6\n\nWed, Oct 7\n\n3 PM\n\n11 AM\n",
                         "Check in                                Check out\nTue, Oct 6                              Wed, Oct 7\n3 PM                                    11 AM\n") \
                .replace("Total\n\n$400.98", "Total                                 $400.98")

# pypdf: a label, then its day and time
PYPDF = (PLAIN.replace("Pick-up\n\nDrop-off\n\nSun, Oct 4\n\nSat, Oct 10\n\n6:30pm\n\n11:30am\n",
                       "Pick-up\nSun, Oct 4\n6:30pm\nDrop-off\nSat, Oct 10\n11:30am\n")
         .replace("Check in\n\nCheck out\n\nSun, Oct 4\n\nTue, Oct 6\n\n3 PM\n\n11:00 AM\n", "Check in\nSun, Oct 4\n3 PM\nCheck out\nTue, Oct 6\n11:00 AM\n")
         .replace("Check in\n\nCheck out\n\nTue, Oct 6\n\nWed, Oct 7\n\n3 PM\n\n11 AM\n", "Check in\nTue, Oct 6\n3 PM\nCheck out\nWed, Oct 7\n11 AM\n"))


def pdf_of(text: str) -> bytes:
    """A one-column PDF holding `text` (Helvetica, one line per row, new pages as needed), written by hand: enough for pypdf to read back."""
    rows = [r for r in text.replace("\x0c", "\n").split("\n")]
    pages = [rows[i:i + 55] for i in range(0, len(rows), 55)] or [[]]
    objs = []

    def add(body):
        objs.append(body)
        return len(objs)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")  # pages, filled below
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    kids = []
    for page_rows in pages:
        stream = b"BT /F1 10 Tf 12 TL 40 760 Td " + b" ".join(
            b"(" + r.encode("latin-1", "replace").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b") ' " for r in page_rows) + b" ET"
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(add(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>" % (content, font)))
    objs[1] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids) + b"] /Count %d >>" % len(kids)
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
