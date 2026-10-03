"""A small software authenticator for passkey tests (F-074): makes the JSON a browser's navigator.credentials.create/get would send.

It signs with a P-256 key it makes itself, so the tests run the real verification in py_webauthn. Test material only.
"""

import hashlib
import json
import os

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from webauthn import base64url_to_bytes
from webauthn.helpers import bytes_to_base64url

UP, UV, AT = 0x01, 0x04, 0x40


class SoftKey:
    def __init__(self, user_verified=True):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0
        self.user_verified = user_verified
        self.user_handle = b""

    @property
    def id(self):
        return bytes_to_base64url(self.credential_id)

    def _cose_key(self):
        n = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})

    def _flags(self, extra=0):
        return UP | (UV if self.user_verified else 0) | extra

    def create(self, options, origin, rp_id=None, challenge=None):
        """The registration response for `options` (the JSON the server sent), as the browser would post it."""
        opts = json.loads(options) if isinstance(options, str) else options
        rp_id = rp_id or opts["rp"]["id"]
        self.user_handle = base64url_to_bytes(opts["user"]["id"])
        client = json.dumps({"type": "webauthn.create", "challenge": challenge or opts["challenge"], "origin": origin, "crossOrigin": False}).encode()
        data = hashlib.sha256(rp_id.encode()).digest() + bytes([self._flags(AT)]) + self.sign_count.to_bytes(4, "big") + bytes(16) \
            + len(self.credential_id).to_bytes(2, "big") + self.credential_id + self._cose_key()
        att = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": data})
        return {"id": self.id, "rawId": self.id, "type": "public-key", "authenticatorAttachment": "platform", "clientExtensionResults": {},
                "response": {"clientDataJSON": bytes_to_base64url(client), "attestationObject": bytes_to_base64url(att), "transports": ["internal"]}}

    def get(self, options, origin, rp_id=None, challenge=None, count=None):
        """The authentication response for `options`; the counter goes up by one unless `count` is given."""
        opts = json.loads(options) if isinstance(options, str) else options
        rp_id = rp_id or opts["rpId"]
        self.sign_count = self.sign_count + 1 if count is None else count
        client = json.dumps({"type": "webauthn.get", "challenge": challenge or opts["challenge"], "origin": origin, "crossOrigin": False}).encode()
        auth = hashlib.sha256(rp_id.encode()).digest() + bytes([self._flags()]) + self.sign_count.to_bytes(4, "big")
        sig = self.key.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": self.id, "rawId": self.id, "type": "public-key", "authenticatorAttachment": "platform", "clientExtensionResults": {},
                "response": {"clientDataJSON": bytes_to_base64url(client), "authenticatorData": bytes_to_base64url(auth),
                             "signature": bytes_to_base64url(sig), "userHandle": bytes_to_base64url(self.user_handle)}}
