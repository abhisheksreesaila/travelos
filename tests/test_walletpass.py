"""F-288: the stay as an Apple pass and a Google save link (gitaway/walletpass.py), with throwaway keys made here: a CA standing in for Apple's WWDR, a pass certificate it signs, and a
Google service account key. Checks the .pkpass zip, its manifest hashes, that the signature verifies, the JWT's claims and signature, the signed download token, and the hidden buttons."""
import base64
import datetime as dt
import hashlib
import json
import subprocess
import zipfile
from io import BytesIO

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from gitaway import walletpass as wp

PEM = serialization.Encoding.PEM
NOPE = serialization.NoEncryption()


def _name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(subject, issuer, pub, signing_key, ca=False):
    now = dt.datetime.now(dt.timezone.utc)
    b = x509.CertificateBuilder().subject_name(_name(subject)).issuer_name(_name(issuer)).public_key(pub).serial_number(x509.random_serial_number())
    b = b.not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30)).add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    return b.sign(signing_key, hashes.SHA256())


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


@pytest.fixture(scope="module")
def keys():
    ca_key, leaf_key, sa_key = (rsa.generate_private_key(65537, 2048) for _ in range(3))
    ca = _cert("Test WWDR", "Test WWDR", ca_key.public_key(), ca_key, ca=True)
    leaf = _cert("Pass Type ID: pass.test.gitaway", "Test WWDR", leaf_key.public_key(), ca_key)
    return dict(ca=ca, leaf=leaf, leaf_key=leaf_key, sa_key=sa_key,
                sa_json=json.dumps({"client_email": "wallet@test-project.iam.gserviceaccount.com", "private_key": sa_key.private_bytes(PEM, serialization.PrivateFormat.PKCS8, NOPE).decode()}))


@pytest.fixture
def creds(keys, monkeypatch):
    monkeypatch.setenv("APPLE_PASS_TYPE_ID", "pass.test.gitaway")
    monkeypatch.setenv("APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setenv("APPLE_PASS_CERT_PEM_B64", b64(keys["leaf"].public_bytes(PEM)))
    monkeypatch.setenv("APPLE_PASS_KEY_PEM_B64", b64(keys["leaf_key"].private_bytes(PEM, serialization.PrivateFormat.PKCS8, NOPE)))
    monkeypatch.setenv("APPLE_WWDR_PEM_B64", b64(keys["ca"].public_bytes(PEM)))
    monkeypatch.setenv("GOOGLE_WALLET_ISSUER_ID", "3388000000012345678")
    monkeypatch.setenv("GOOGLE_WALLET_SA_JSON_B64", b64(keys["sa_json"].encode()))


STAY = wp.Stay(uid=wp.uid_of("fam1", "bk-1"), booking_id="bk-1", hotel="Hôtel <b>Lumière</b>", check_in=dt.datetime(2026, 12, 7, 16, 0), check_out=dt.datetime(2026, 12, 10, 11, 0),
               tz="Europe/Paris", code="HX-4821", address="12 Rue Cler, Paris", guests="2 adults, 1 kid (ages 7)", lat=48.8566, lng=2.3522, url="https://gitaway.me/trip/booking?block=x")


def test_the_pkpass_is_a_zip_with_the_stays_facts(creds):
    z = zipfile.ZipFile(BytesIO(wp.apple_pass(STAY)))
    assert sorted(z.namelist()) == ["icon.png", "icon@2x.png", "icon@3x.png", "manifest.json", "pass.json", "signature"]
    p = json.loads(z.read("pass.json"))
    assert (p["formatVersion"], p["passTypeIdentifier"], p["teamIdentifier"], p["serialNumber"]) == (1, "pass.test.gitaway", "TEAM123456", STAY.uid)
    g = p["generic"]
    assert g["primaryFields"] == [{"key": "hotel", "label": "HOTEL", "value": "Hôtel <b>Lumière</b>"}]      # text, never markup: Wallet draws it as words
    assert [(f["label"], f["value"]) for f in g["secondaryFields"]] == [("CHECK IN", "Mon, Dec 7 · 4:00 PM"), ("CHECK OUT", "Thu, Dec 10 · 11:00 AM")]
    assert [(f["label"], f["value"]) for f in g["auxiliaryFields"]] == [("GUESTS", "2 adults, 1 kid (ages 7)"), ("CONFIRMATION", "HX-4821")]
    assert {"key": "link", "label": "Open the booking", "value": "https://gitaway.me/trip/booking?block=x"} in g["backFields"]
    assert {"key": "address", "label": "Address", "value": "12 Rue Cler, Paris"} in g["backFields"]
    assert p["barcodes"] == [{"format": "PKBarcodeFormatQR", "message": "HX-4821", "messageEncoding": "iso-8859-1", "altText": "HX-4821"}]
    assert p["relevantDate"] == "2026-12-07T16:00:00+01:00"
    assert p["locations"] == [{"latitude": 48.8566, "longitude": 2.3522, "relevantText": "Your stay: Hôtel <b>Lumière</b>"}]
    assert "webServiceURL" not in p


def test_the_manifest_holds_the_sha1_of_every_file_and_the_signature_verifies(creds, keys, tmp_path):
    z = zipfile.ZipFile(BytesIO(wp.apple_pass(STAY)))
    manifest = json.loads(z.read("manifest.json"))
    assert sorted(manifest) == ["icon.png", "icon@2x.png", "icon@3x.png", "pass.json"]
    for name, digest in manifest.items():
        assert digest == hashlib.sha1(z.read(name)).hexdigest()
    (tmp_path / "ca.pem").write_bytes(keys["ca"].public_bytes(PEM))
    (tmp_path / "manifest.json").write_bytes(z.read("manifest.json"))
    (tmp_path / "signature").write_bytes(z.read("signature"))
    ok = subprocess.run(["openssl", "cms", "-verify", "-binary", "-inform", "DER", "-in", str(tmp_path / "signature"), "-content", str(tmp_path / "manifest.json"), "-CAfile", str(tmp_path / "ca.pem"),
                         "-purpose", "any", "-out", str(tmp_path / "out")], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    (tmp_path / "manifest.json").write_bytes(z.read("manifest.json").replace(b"pass.json", b"pass.jsoN"))
    bad = subprocess.run(["openssl", "cms", "-verify", "-binary", "-inform", "DER", "-in", str(tmp_path / "signature"), "-content", str(tmp_path / "manifest.json"), "-CAfile", str(tmp_path / "ca.pem"),
                          "-purpose", "any", "-out", str(tmp_path / "out")], capture_output=True, text=True)
    assert bad.returncode != 0      # a changed manifest no longer verifies


def test_a_sample_stay_says_so_on_the_pass(creds):
    from dataclasses import replace
    p = json.loads(zipfile.ZipFile(BytesIO(wp.apple_pass(replace(STAY, sample=True)))).read("pass.json"))
    assert p["description"].startswith("Sample stay at ") and p["generic"]["headerFields"] == [{"key": "tag", "label": "STAY", "value": "SAMPLE"}]


def test_a_stay_without_coordinates_or_a_code_has_no_locations_or_barcode(creds):
    from dataclasses import replace
    p = json.loads(zipfile.ZipFile(BytesIO(wp.apple_pass(replace(STAY, lat=None, lng=None, code="")))).read("pass.json"))
    assert "locations" not in p and "barcodes" not in p


def _decode(url, keys):
    assert url.startswith("https://pay.google.com/gp/v/save/")
    head, body, sig = url.removeprefix("https://pay.google.com/gp/v/save/").split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)      # noqa: E731
    keys["sa_key"].public_key().verify(base64.urlsafe_b64decode(pad(sig)), f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return json.loads(base64.urlsafe_b64decode(pad(head))), json.loads(base64.urlsafe_b64decode(pad(body)))


def test_the_google_link_is_an_rs256_jwt_of_a_generic_object(creds, keys):
    header, claims = _decode(wp.google_save_url(STAY, "https://gitaway.me", now=1_800_000_000), keys)
    assert header == {"alg": "RS256", "typ": "JWT"}
    assert (claims["iss"], claims["aud"], claims["typ"], claims["iat"], claims["origins"]) == ("wallet@test-project.iam.gserviceaccount.com", "google", "savetowallet", 1_800_000_000, ["https://gitaway.me"])
    assert claims["payload"]["genericClasses"] == [{"id": "3388000000012345678.gitaway_stay"}]
    o = claims["payload"]["genericObjects"][0]
    assert o["id"] == f"3388000000012345678.{STAY.uid}" and o["classId"] == "3388000000012345678.gitaway_stay" and o["state"] == "ACTIVE"
    assert o["header"]["defaultValue"]["value"] == "Hôtel <b>Lumière</b>"
    assert o["barcode"] == {"type": "QR_CODE", "value": "HX-4821", "alternateText": "HX-4821"}
    assert o["merchantLocations"] == [{"latitude": 48.8566, "longitude": 2.3522}]
    assert o["validTimeInterval"] == {"start": {"date": "2026-12-07T16:00:00+01:00"}, "end": {"date": "2026-12-10T11:00:00+01:00"}}
    assert o["linksModuleData"]["uris"][0]["uri"] == "https://gitaway.me/trip/booking?block=x"
    assert [(m["header"], m["body"]) for m in o["textModulesData"]][:2] == [("Check in", "Mon, Dec 7 · 4:00 PM"), ("Check out", "Thu, Dec 10 · 11:00 AM")]


def test_a_token_is_for_one_vendor_one_booking_and_one_family_and_expires():
    t = wp.sign("apple", "bk-1", "fam1", ttl=60, now=1000)
    assert wp.unsign(t, "apple", now=1030) == ("bk-1", "fam1", False)
    assert wp.unsign(t, "apple", now=1061) == ("bk-1", "fam1", True)
    assert wp.unsign(t, "google", now=1030) is None                     # the Apple link is not a Google one
    body, mac = t.split(".")
    assert wp.unsign(body + "." + "0" * 32, "apple") is None            # forged signature
    forged = base64.urlsafe_b64encode(json.dumps(["apple", "bk-2", "fam1", 99999999999]).encode()).decode().rstrip("=")
    assert wp.unsign(forged + "." + mac, "apple") is None               # another booking under the same signature
    assert wp.unsign("garbage", "apple") is None and wp.unsign("", "apple") is None


def test_buttons_are_hidden_until_a_vendors_credentials_are_set(monkeypatch):
    for name in ("APPLE_PASS_TYPE_ID", "APPLE_TEAM_ID", "APPLE_PASS_CERT_PEM_B64", "APPLE_PASS_KEY_PEM_B64", "APPLE_WWDR_PEM_B64", "GOOGLE_WALLET_ISSUER_ID", "GOOGLE_WALLET_SA_JSON_B64"):
        monkeypatch.delenv(name, raising=False)
    assert wp.buttons("bk-1", "fam1") == "" and not wp.apple_configured() and not wp.google_configured()


def test_each_button_shows_with_its_own_credentials(creds, monkeypatch):
    from fasthtml.common import to_xml
    both = to_xml(wp.buttons("bk-1", "fam1"))
    assert "Add to Apple Wallet" in both and "Save to Google Wallet" in both and 'href="/wallet/apple/' in both and 'href="/wallet/google/' in both
    monkeypatch.delenv("GOOGLE_WALLET_ISSUER_ID")
    only_apple = to_xml(wp.buttons("bk-1", "fam1"))
    assert "Add to Apple Wallet" in only_apple and "Google" not in only_apple


def test_a_sample_booking_gets_no_button_off_the_showcase(creds, monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    assert wp.buttons("SAMPLE-1A2B3C4D", "fam1") == ""
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    from fasthtml.common import to_xml
    assert "Add to Apple Wallet" in to_xml(wp.buttons("SAMPLE-1A2B3C4D", "fam1"))
