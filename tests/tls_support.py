"""A test certificate authority, a local TLS server and a dripping proxy (F-203 last fixes): the real `weather._MetTLS` is driven against them, so the
handshake, the certificate's name and the watchdog are tested without the network. Everything listens on 127.0.0.1 only."""

import datetime
import socket
import ssl
import threading
import time
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _pem_key(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def make_certs(folder: Path, name: str):
    """(CA certificate file, server certificate file, server key file): a CA of our own, and a certificate it signed for `name`."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "GitAway test CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False,
                                       key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    files = (folder / "ca.pem", folder / f"{name}.pem", folder / f"{name}.key")
    files[0].write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    files[1].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    files[2].write_bytes(_pem_key(key))
    return files


class TLSServer:
    """Answers each connection, over TLS with the given certificate, with one HTTP/1.1 200 carrying `body`, then closes. With `drip` (seconds), the
    answer goes out one byte at a time, that far apart: a quick handshake, then headers that never quite arrive."""

    def __init__(self, cert, key, body: bytes, drip=0.0):
        self.ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ctx.load_cert_chain(str(cert), str(key))
        self.body, self.drip, self.stop = body, drip, threading.Event()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self.stop.is_set():
            try:
                raw, _ = self.sock.accept()
            except OSError:
                continue
            threading.Thread(target=self._answer, args=(raw,), daemon=True).start()

    def _answer(self, raw):
        try:
            raw.settimeout(10)
            with self.ctx.wrap_socket(raw, server_side=True) as tls:
                tls.recv(65536)
                answer = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: %d\r\n\r\n" % len(self.body) + self.body
                if not self.drip:
                    tls.sendall(answer)
                for i in range(len(answer) if self.drip else 0):
                    if self.stop.is_set():
                        break
                    tls.sendall(answer[i:i + 1])
                    time.sleep(self.drip)
        except (OSError, ssl.SSLError):
            pass

    def close(self):
        self.stop.set()
        self.sock.close()


class DripProxy:
    """Relays to a local server: what the client sends goes at once, what the server sends trickles back `chunk` bytes every `gap` seconds, so the TLS
    handshake (and every header after it) drags on while no single read ever waits long."""

    def __init__(self, target_port: int, chunk=32, gap=0.05):
        self.target, self.chunk, self.gap, self.stop = target_port, chunk, gap, threading.Event()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.open = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self.stop.is_set():
            try:
                client, _ = self.sock.accept()
            except OSError:
                continue
            upstream = socket.create_connection(("127.0.0.1", self.target))
            self.open += [client, upstream]
            threading.Thread(target=self._pipe, args=(client, upstream, False), daemon=True).start()
            threading.Thread(target=self._pipe, args=(upstream, client, True), daemon=True).start()

    def _pipe(self, src, dst, slow):
        try:
            while not self.stop.is_set():
                data = src.recv(self.chunk if slow else 65536)
                if not data:
                    break
                dst.sendall(data)
                if slow:
                    time.sleep(self.gap)
        except OSError:
            pass

    def close(self):
        self.stop.set()
        for s in [self.sock, *self.open]:
            try:
                s.close()
            except OSError:
                pass
