"""Small pictures for the photo tests, generated here (no fixture files): JPEG/PNG/WebP/HEIC with the EXIF a phone writes."""

import io

from PIL import Image


def _dms(v):
    d = int(v)
    m = int((v - d) * 60)
    return (float(d), float(m), round((v - d - m / 60) * 3600, 4))


def exif(taken=None, offset=None, gps=None):
    """EXIF for `taken` ("2026:10:17 10:30:00", the camera's clock), its `offset` ("-07:00") and `gps` ((lat, lon))."""
    e = Image.Exif()
    if taken:
        ifd = e.get_ifd(0x8769)
        ifd[0x9003] = taken
        e[0x8769] = ifd
        if offset:
            ifd[0x9011] = offset
    if gps:
        g = e.get_ifd(0x8825)
        lat, lon = gps
        g[1], g[2] = "N" if lat >= 0 else "S", _dms(abs(lat))
        g[3], g[4] = "E" if lon >= 0 else "W", _dms(abs(lon))
        e[0x8825] = g
    return e


def image(kind="jpeg", size=(120, 90), color=(200, 90, 60), **meta):
    """The bytes of a small picture of the given kind, with EXIF when `taken`/`offset`/`gps` are given (not for PNG)."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    e = exif(**meta) if meta else None
    if kind == "jpeg":
        img.save(buf, "JPEG", **({"exif": e} if e else {}))
    elif kind == "png":
        img.save(buf, "PNG")
    elif kind == "webp":
        img.save(buf, "WEBP", **({"exif": e} if e else {}))
    elif kind == "heic":
        import pillow_heif
        pillow_heif.register_heif_opener()
        img.save(buf, "HEIF", **({"exif": e.tobytes()} if e else {}))
    return buf.getvalue()
