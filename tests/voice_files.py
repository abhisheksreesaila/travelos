"""Tiny stand-ins for recorded audio, recognised by their first bytes (gitaway/voicenotes.py does not decode audio)."""


def voice(kind="webm", size=2000) -> bytes:
    head = {"webm": b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01", "mp4": b"\x00\x00\x00\x1cftypM4A \x00\x00\x00\x00M4A mp42isom", "ogg": b"OggS\x00\x02\x00\x00\x00\x00"}[kind]
    return head + b"\x00" * max(0, size - len(head))
