"""Add a stay to Apple or Google Wallet (F-288, D-931..D-935): the routes behind the buttons (the builders are gitaway/walletpass.py).

GET /wallet/apple/<token>    the signed .pkpass of one booked stay, as a download
GET /wallet/google/<token>   a redirect to Google's "Save to Google Wallet" link for the same stay

The token is made by this server for one vendor, one booking and one family, and expires (a button on a page: an hour; the confirmation email's link: two weeks). A download also needs the
person signed in as a member of that family: signed out goes to sign-in and comes back here (so the email link signs in first, then downloads). The stay is read from the signed-in
family's own database, never from the token alone, so another family's booking cannot be reached by any address. Nothing is logged but the booking id.
"""

import logging
from datetime import datetime, time

from starlette.responses import RedirectResponse, Response

from gitaway import blogbutton, familydb, importer, liteapi, matrixbook as mb, session as ses, showcase, tripimport as ti, walletpass as wp
from gitaway.layout import notice
from gitaway.pages import booking as booking_page

log = logging.getLogger(__name__)
NO_STORE = {"Cache-Control": "no-store"}


def _time_of(text: str):
    """"04:00 PM" (LiteAPI's check-in and check-out times) as a time, or None."""
    try:
        return datetime.strptime(" ".join(str(text or "").split()).upper(), "%I:%M %p").time()
    except ValueError:
        return None


def load(session, ref: str):
    """The `walletpass.Stay` of booking `ref` in the signed-in person's own family, or None when it is not there, is cancelled, or is a sample off the showcase."""
    family = session.get("tenant_id") or ""
    if not ref or (ref.startswith("SAMPLE-") and not showcase.on()):
        return None
    with ses.family(session) as fam:
        if not fam:
            return None
        row = familydb.row(fam.db, "SELECT * FROM matrix_bookings WHERE booking_id = :b", b=ref)
        pay = familydb.row(fam.db, "SELECT guests, hotel_address FROM matrix_payments WHERE booking_id = :b", b=ref) or {}
        cancelled = mb.cancelled(fam.db, ref)
        trip_id = (row or {}).get("trip_id") or fam.trip_id
    plan = importer.plan_of(session, trip_id)
    spec = next((s for s in ti.block_specs(plan) if s.kind == "checkin" and s.item.confirmation == ref), None) if plan else None
    lodging = spec.item if spec else None
    if cancelled or (lodging and lodging.booked_on.startswith("Cancelled")) or not (lodging or row):
        return None
    if lodging:
        check_in, check_out, hotel, address = lodging.check_in, lodging.check_out, lodging.name, lodging.address
    else:
        check_in, check_out = (datetime.combine(datetime.fromisoformat(row[k]).date(), time(h)) for k, h in (("checkin", 15), ("checkout", 11)))
        hotel, address = row["hotel"], ""
    lat = lng = None
    if row and row.get("hotel_id") and not row["sample"]:
        try:
            details = liteapi.hotel(row["hotel_id"], family)
        except Exception:  # noqa: BLE001 - no coordinates is a pass without a location, never a failed download
            details = None
        if details:
            lat, lng, address = details.lat, details.lng, details.address or pay.get("hotel_address") or address
            t_in, t_out = _time_of(details.checkin), _time_of(details.checkout)
            if lodging is None or lodging.booked_on.startswith(("LiteAPI", "GitAway sample")):      # a stay booked here had LiteAPI's times assumed: the hotel's own replace them
                check_in = datetime.combine(check_in.date(), t_in) if t_in else check_in
                check_out = datetime.combine(check_out.date(), t_out) if t_out else check_out
    address = address or pay.get("hotel_address") or ""
    code = (row or {}).get("confirmation") or (lodging.confirmation if lodging else "")
    url = blogbutton.base_url() + booking_page.href(spec.id) if spec else ""
    return wp.Stay(wp.uid_of(family, ref), ref, hotel, check_in, check_out, ses.trip_zone(session), code, address, pay.get("guests") or "", lat, lng, url, bool((row or {}).get("sample")) or ref.startswith("SAMPLE-"))


def _refuse(words: str, status: int):
    return notice("Wallet pass", words, "Open the booking and press the button again.", status=status, noindex=True)


def _serve(request, session, vendor: str, token: str):
    got = wp.unsign(token, vendor)
    if got is None:
        return _refuse("That wallet link is not valid.", 404)
    ref, family, expired = got
    if not ses.current_traveler(session):
        return RedirectResponse(ses.signin_href(request.url.path), status_code=303)
    if family != (session.get("tenant_id") or ""):
        return _refuse("That wallet link is for another family.", 404)
    if expired:
        return _refuse("That wallet link has expired.", 410)
    if not (wp.apple_configured() if vendor == "apple" else wp.google_configured()):
        return _refuse("Wallet passes are not set up yet.", 404)
    stay = load(session, ref)
    if stay is None:
        return _refuse("That stay is not on your trip any more.", 404)
    try:
        if vendor == "google":
            link = wp.google_save_url(stay, blogbutton.base_url())
        else:
            data = wp.apple_pass(stay)
    except Exception:  # noqa: BLE001 - the log line names the booking only: no key, no exception text
        log.warning("wallet pass failed: %s", ref)
        return _refuse("The pass could not be made just now.", 503)
    log.info("wallet pass: %s %s", vendor, ref)
    if vendor == "google":
        return RedirectResponse(link, status_code=303, headers=NO_STORE)
    return Response(data, media_type=wp.MIME, headers={**NO_STORE, "Content-Disposition": 'attachment; filename="gitaway-stay.pkpass"'})


def register(app):
    @app.get(wp.APPLE_PATH + "{token}")
    def apple(request, session, token: str):
        return _serve(request, session, "apple", token)

    @app.get(wp.GOOGLE_PATH + "{token}")
    def google(request, session, token: str):
        return _serve(request, session, "google", token)
