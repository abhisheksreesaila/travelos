"""Send a sample booked email, with made-up data, through the same code a real booking uses (F-285): `pixi run python scripts/send_test_email.py --to you@example.com`.

It needs the SMTP settings in the environment (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_MAIL_FROM; for Resend: smtp.resend.com, user `resend`, the API key as the password, port 465 with
SMTP_SSL=true). It never prints the password or the address. `--cancelled` sends the cancelled email instead. `--preview DIR` sends nothing: it writes booked.html and cancelled.html
(docs/design/emails) so the emails can be looked at in a browser.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GITAWAY_DATA_DIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "send-test-email"))

from gitaway import bookingmail  # noqa: E402

BOOKED = {"first": "Alex", "hotel": "Margaritaville Hotel San Diego Gaslamp Quarter", "address": "660 K Street, San Diego, CA 92101", "checkin": "2026-12-16", "checkout": "2026-12-19",
          "guests": "2 adults, 2 kids (ages 7, 10)", "room": "Standard Room, 2 Queen Beds", "booking_id": "uuJxfM0--", "confirmation": "HX4T9Q", "charge_cents": 72993, "due_cents": 12000,
          "policy": "Free cancellation until Dec 10, 6:59 PM GMT. After that, cancelling costs $148.88; from Dec 11, 6:59 PM GMT, $729.93.", "token": "SAMPLE0token0only", "sandbox": True}
CANCELLED = {"hotel": BOOKED["hotel"], "checkin": BOOKED["checkin"], "checkout": BOOKED["checkout"], "booking_id": BOOKED["booking_id"], "refund_cents": 58105, "fee_cents": 14888, "sandbox": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--to", help="the address to send the sample to")
    ap.add_argument("--cancelled", action="store_true", help="send the cancelled email instead of the booked one")
    ap.add_argument("--preview", metavar="DIR", help="write booked.html and cancelled.html into DIR and send nothing")
    args = ap.parse_args(argv)
    booked, cancelled = bookingmail.booked_mail(BOOKED), bookingmail.cancelled_mail(CANCELLED)
    if args.preview:
        out = Path(args.preview)
        out.mkdir(parents=True, exist_ok=True)
        (out / "booked.html").write_text(booked.html, encoding="utf-8")
        (out / "cancelled.html").write_text(cancelled.html, encoding="utf-8")
        print(f"wrote {out / 'booked.html'} and {out / 'cancelled.html'}")
        return 0
    if not args.to or not bookingmail.address_ok(args.to):
        print("Give --to <address> (one plain address).", file=sys.stderr)
        return 2
    if bookingmail.smtp() is None:
        print("SMTP_HOST, SMTP_USER, SMTP_PASSWORD and SMTP_MAIL_FROM are not all set.", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mail = cancelled if args.cancelled else booked
    try:
        bookingmail.deliver(args.to, mail)
    except Exception as e:  # noqa: BLE001 - say the kind of failure, never the address or the server's words (they repeat it)
        print(f"Not sent: {type(e).__name__}.", file=sys.stderr)
        return 1
    print(f"Sent the sample {'cancelled' if args.cancelled else 'booked'} email.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
