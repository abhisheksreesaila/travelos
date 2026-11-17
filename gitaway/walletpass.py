"""The stay in Apple and Google Wallet (F-288, D-931..D-935, docs/research/wallet-passes.md): pure builders, no routes (those are gitaway/pages/walletpass.py).

    Stay                          what a pass says: hotel, address, check in and out, guests, the code, where the hotel is, the booking page
    apple_pass(stay)              the bytes of a signed `.pkpass` (pass.json, icon, manifest of SHA-1s, a detached PKCS #7 signature with the Pass Type ID certificate and Apple's WWDR one)
    google_save_url(stay, origin) "Save to Google Wallet": https://pay.google.com/gp/v/save/<RS256 JWT of a generic class and object>
    sign / unsign                 the download token: HMAC over (vendor, booking, family, expiry), so an address is made only by this server for one booking of one family
    buttons(booking, family)      the two buttons for a page (or "" while neither vendor's credentials are set); Today (F-287) calls this too

Credentials come from the environment by name only (docs/setup.md): APPLE_PASS_TYPE_ID, APPLE_TEAM_ID, APPLE_PASS_CERT_PEM_B64, APPLE_PASS_KEY_PEM_B64, APPLE_PASS_KEY_PASSWORD (optional),
APPLE_WWDR_PEM_B64; GOOGLE_WALLET_ISSUER_ID, GOOGLE_WALLET_SA_JSON_B64. A pass holds only what the booking page already shows to its family. Never log more than the booking id.
"""

import base64
import functools
import hashlib
import hmac
import io
import json
import logging
import os
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs7
from fasthtml.common import A, Div

log = logging.getLogger(__name__)

PAGE_TTL = 3600                 # a button on a page is good for an hour (the page is drawn fresh each visit)
MAIL_TTL = 14 * 24 * 3600       # a link in the confirmation email, for two weeks (it signs in first, then downloads)
APPLE_PATH, GOOGLE_PATH = "/wallet/apple/", "/wallet/google/"
MIME = "application/vnd.apple.pkpass"
SAVE = "https://pay.google.com/gp/v/save/"
CLASS_SUFFIX = "gitaway_stay"
NAVY, SKY = (12, 24, 48), (220, 235, 249)
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]+")
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_DAYS = "Mon Tue Wed Thu Fri Sat Sun".split()


@dataclass(frozen=True)
class Stay:
    uid: str                    # opaque, unique per family and booking (`uid_of`): the pass's serial number and Google's object id
    booking_id: str
    hotel: str
    check_in: datetime          # naive, the hotel's local time
    check_out: datetime
    tz: str                     # the trip's IANA zone, for relevantDate
    code: str = ""              # the hotel's confirmation code (the QR holds exactly this)
    address: str = ""
    guests: str = ""
    lat: float | None = None
    lng: float | None = None
    url: str = ""               # the booking page, absolute
    sample: bool = False


def uid_of(family: str, booking_id: str) -> str:
    return "s" + hashlib.sha256(f"gitaway-wallet|{family}|{booking_id}".encode()).hexdigest()[:24]


def clean(v, limit: int = 120) -> str:
    """Text from a booking as one plain line (no control characters), cut to `limit`."""
    return " ".join(_CONTROL.sub(" ", str(v or "")).split())[:limit]


def _day(d: datetime) -> str:
    return f"{_DAYS[d.weekday()]}, {_MONTHS[d.month - 1]} {d.day}"


def _clock(d: datetime) -> str:
    return f"{d.hour % 12 or 12}:{d.minute:02d} {'AM' if d.hour < 12 else 'PM'}"


def _when(d: datetime) -> str:
    return f"{_day(d)} · {_clock(d)}"


def _aware(d: datetime, tz: str):
    try:
        return d.replace(tzinfo=ZoneInfo(tz))
    except Exception:  # noqa: BLE001 - an unknown zone: no relevantDate rather than a wrong one
        return None


def _b64env(name: str) -> bytes | None:
    try:
        raw = base64.b64decode(os.getenv(name, "").strip(), validate=True)
    except Exception:  # noqa: BLE001
        return None
    return raw or None


# ---- credentials -----------------------------------------------------------------------------------------------------------

def apple_configured() -> bool:
    return bool(os.getenv("APPLE_PASS_TYPE_ID") and os.getenv("APPLE_TEAM_ID") and _b64env("APPLE_PASS_CERT_PEM_B64") and _b64env("APPLE_PASS_KEY_PEM_B64") and _b64env("APPLE_WWDR_PEM_B64"))


def google_configured() -> bool:
    return bool(os.getenv("GOOGLE_WALLET_ISSUER_ID") and _b64env("GOOGLE_WALLET_SA_JSON_B64"))


# ---- Apple ------------------------------------------------------------------------------------------------------------------

@functools.cache
def _icon(px: int) -> bytes:
    """The pass's icon (Wallet will not open a pass without one): the navy square with two light ridges, drawn here so no file has to ship."""
    from PIL import Image, ImageDraw
    s = px * 4
    im = Image.new("RGB", (s, s), NAVY)
    d = ImageDraw.Draw(im)
    d.polygon([(0, s), (s * .38, s * .36), (s * .74, s)], fill=(70, 98, 150))
    d.polygon([(s * .3, s), (s * .7, s * .22), (s, s)], fill=SKY)
    out = io.BytesIO()
    im.resize((px, px), Image.LANCZOS).save(out, "PNG")
    return out.getvalue()


def pass_json(stay: Stay, type_id: str, team_id: str) -> dict:
    tag = "SAMPLE" if stay.sample else ""
    fields = [{"key": "checkin", "label": "CHECK IN", "value": _when(stay.check_in)}, {"key": "checkout", "label": "CHECK OUT", "value": _when(stay.check_out)}]
    aux = [{"key": "guests", "label": "GUESTS", "value": clean(stay.guests, 80)}] if stay.guests else []
    if stay.code:
        aux.append({"key": "code", "label": "CONFIRMATION", "value": clean(stay.code, 60)})
    back = [{"key": "address", "label": "Address", "value": clean(stay.address, 200)}] if stay.address else []
    back += [{"key": "booking", "label": "Booking id", "value": clean(stay.booking_id, 60)}]
    if stay.url:
        back.append({"key": "link", "label": "Open the booking", "value": stay.url})
    back.append({"key": "note", "label": "About this pass", "value": ("Sample stay: not a real booking. " if stay.sample else "") + "Made by GitAway from your booking. It is a snapshot: change or cancel the stay on its booking page."})
    out = {"formatVersion": 1, "passTypeIdentifier": type_id, "teamIdentifier": team_id, "serialNumber": stay.uid, "organizationName": "GitAway",
           "description": ("Sample stay at " if stay.sample else "Stay at ") + clean(stay.hotel, 80), "logoText": "GitAway",
           "backgroundColor": "rgb(12, 24, 48)", "foregroundColor": "rgb(255, 255, 255)", "labelColor": "rgb(190, 205, 230)",
           "generic": {"headerFields": [{"key": "tag", "label": "STAY", "value": tag}] if tag else [], "primaryFields": [{"key": "hotel", "label": "HOTEL", "value": clean(stay.hotel, 80)}],
                       "secondaryFields": fields, "auxiliaryFields": aux, "backFields": back}}
    if stay.code:
        out["barcodes"] = [{"format": "PKBarcodeFormatQR", "message": clean(stay.code, 60), "messageEncoding": "iso-8859-1", "altText": clean(stay.code, 60)}]
    when = _aware(stay.check_in, stay.tz)
    if when:
        out["relevantDate"] = when.isoformat(timespec="seconds")
    if stay.lat is not None and stay.lng is not None:
        out["locations"] = [{"latitude": stay.lat, "longitude": stay.lng, "relevantText": "Your stay: " + clean(stay.hotel, 60)}]
    return out


def _apple_creds():
    key = serialization.load_pem_private_key(_b64env("APPLE_PASS_KEY_PEM_B64"), (os.getenv("APPLE_PASS_KEY_PASSWORD") or "").encode() or None)
    return x509.load_pem_x509_certificate(_b64env("APPLE_PASS_CERT_PEM_B64")), key, x509.load_pem_x509_certificate(_b64env("APPLE_WWDR_PEM_B64"))


def apple_pass(stay: Stay) -> bytes:
    """A signed .pkpass for `stay`. Raises when the Apple credentials are missing or unreadable (the route turns that into a plain notice)."""
    cert, key, wwdr = _apple_creds()
    files = {"pass.json": json.dumps(pass_json(stay, os.environ["APPLE_PASS_TYPE_ID"], os.environ["APPLE_TEAM_ID"]), ensure_ascii=False).encode(),
             "icon.png": _icon(29), "icon@2x.png": _icon(58), "icon@3x.png": _icon(87)}
    manifest = json.dumps({name: hashlib.sha1(data).hexdigest() for name, data in files.items()}).encode()
    signature = pkcs7.PKCS7SignatureBuilder().set_data(manifest).add_signer(cert, key, hashes.SHA256()).add_certificate(wwdr).sign(
        serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in {**files, "manifest.json": manifest, "signature": signature}.items():
            z.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    return out.getvalue()


# ---- Google -----------------------------------------------------------------------------------------------------------------

def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _text(v: str) -> dict:
    return {"defaultValue": {"language": "en-US", "value": v}}


def google_object(stay: Stay, issuer: str) -> dict:
    mods = [{"id": "checkin", "header": "Check in", "body": _when(stay.check_in)}, {"id": "checkout", "header": "Check out", "body": _when(stay.check_out)}]
    if stay.guests:
        mods.append({"id": "guests", "header": "Guests", "body": clean(stay.guests, 80)})
    if stay.address:
        mods.append({"id": "address", "header": "Address", "body": clean(stay.address, 200)})
    if stay.code:
        mods.append({"id": "code", "header": "Confirmation", "body": clean(stay.code, 60)})
    obj = {"id": f"{issuer}.{stay.uid}", "classId": f"{issuer}.{CLASS_SUFFIX}", "state": "ACTIVE", "cardTitle": _text("GitAway"), "header": _text(clean(stay.hotel, 80)),
           "subheader": _text(("Sample stay" if stay.sample else "Your stay") + f" · {_day(stay.check_in)} to {_day(stay.check_out)}"), "hexBackgroundColor": "#0c1830", "textModulesData": mods}
    if stay.code:
        obj["barcode"] = {"type": "QR_CODE", "value": clean(stay.code, 60), "alternateText": clean(stay.code, 60)}
    if stay.url:
        obj["linksModuleData"] = {"uris": [{"id": "booking", "uri": stay.url, "description": "Open the booking"}]}
    start, end = _aware(stay.check_in, stay.tz), _aware(stay.check_out, stay.tz)
    if start and end:      # Google has no relevantDate for a generic pass: validTimeInterval is the time it knows (docs/research/wallet-passes.md)
        obj["validTimeInterval"] = {"start": {"date": start.isoformat(timespec="seconds")}, "end": {"date": end.isoformat(timespec="seconds")}}
    if stay.lat is not None and stay.lng is not None:
        obj["merchantLocations"] = [{"latitude": stay.lat, "longitude": stay.lng}]
    return obj


def google_save_url(stay: Stay, origin: str, now: float | None = None) -> str:
    sa = json.loads(_b64env("GOOGLE_WALLET_SA_JSON_B64"))
    issuer = os.environ["GOOGLE_WALLET_ISSUER_ID"]
    claims = {"iss": sa["client_email"], "aud": "google", "typ": "savetowallet", "iat": int(time.time() if now is None else now), "origins": [origin],
              "payload": {"genericClasses": [{"id": f"{issuer}.{CLASS_SUFFIX}"}], "genericObjects": [google_object(stay, issuer)]}}
    head = _b64u(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode()) + "." + _b64u(json.dumps(claims, separators=(",", ":"), ensure_ascii=False).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), None)
    return SAVE + head + "." + _b64u(key.sign(head.encode(), padding.PKCS1v15(), hashes.SHA256()))


# ---- the download token -----------------------------------------------------------------------------------------------------

def _mac(body: str) -> str:
    from gitaway import session as ses
    return hmac.new(ses.cache_secret(), b"gitaway-wallet|" + body.encode(), hashlib.sha256).hexdigest()[:32]


def sign(vendor: str, booking_id: str, family: str, ttl: int = PAGE_TTL, now: float | None = None) -> str:
    body = _b64u(json.dumps([vendor, booking_id, family, int((time.time() if now is None else now) + ttl)], separators=(",", ":")).encode())
    return f"{body}.{_mac(body)}"


def unsign(token: str, vendor: str, now: float | None = None):
    """(booking_id, family, expired) from a token this server made for `vendor`, or None when it is forged or for the other vendor. An expired one still says who it was for."""
    body, _, mac = str(token or "").partition(".")
    if not body or len(body) > 400 or not hmac.compare_digest(mac, _mac(body)):
        return None
    try:
        v, booking_id, family, exp = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:  # noqa: BLE001
        return None
    if v != vendor or not isinstance(booking_id, str) or not isinstance(family, str) or not isinstance(exp, int):
        return None
    return booking_id, family, (time.time() if now is None else now) > exp


# ---- the buttons ------------------------------------------------------------------------------------------------------------

def _ref(booking) -> str:
    return str(booking if isinstance(booking, str) else getattr(booking, "booking_id", None) or (booking.get("booking_id") if isinstance(booking, dict) else "") or "").strip()


def offered(ref: str) -> bool:
    """A pass is for a booking with a code of its own; a sample one only on the showcase (never a real-looking pass off it)."""
    from gitaway import showcase
    return bool(ref) and len(ref) <= 60 and (not ref.startswith("SAMPLE-") or showcase.on())


def links(booking, family: str, ttl: int = PAGE_TTL) -> list:
    """[(label, path)] for each vendor whose credentials are set."""
    ref = _ref(booking)
    if not family or not offered(ref):
        return []
    return ([("Add to Apple Wallet", APPLE_PATH + sign("apple", ref, family, ttl))] if apple_configured() else []) + \
           ([("Save to Google Wallet", GOOGLE_PATH + sign("google", ref, family, ttl))] if google_configured() else [])


def buttons(booking, family: str, ttl: int = PAGE_TTL):
    """The two buttons for `booking` (a booking id, or an object with `.booking_id`) of `family` (the tenant id), or "" while neither vendor is set up."""
    found = links(booking, family, ttl)
    return Div(*[A(label, href=path, cls="btn wp-btn", id="wp-apple" if "Apple" in label else "wp-google", rel="nofollow") for label, path in found], cls="wp-btns", id="wp-btns") if found else ""
