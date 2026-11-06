"""A creator pastes their blog's address and GitAway lists the trip-like posts on it (F-190). No AI here: the list is read from the site's own sitemap or feed and ranked by words.

    discover(address)   up to SHOWN `Post`s (url, title, date), best trip-like first; ScanError with a sentence fit to show
    sample(address)     the same shape from fixtures, for the local showcase (nothing is fetched)

Every address is untrusted, so: every fetch goes through gitaway/safefetch.py (public addresses only, size and time limits); the XML is read with defusedxml and refused if it has a
DOCTYPE at all (no entity expansion, no external entities: a sitemap never needs one); only addresses on the creator's own site are kept (`same_site`); a sitemap index is followed one
level (its children may not be indexes), at most MAX_URLS addresses are read, and the whole scan has a time budget.
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

from defusedxml import ElementTree as ET

from gitaway import importsource, safefetch

log = logging.getLogger("gitaway.blogscan")

SHOWN = 50                 # posts offered to tick
MAX_URLS = 2000            # addresses read from a sitemap
MAX_CHILDREN = 8           # child sitemaps read from an index
BUDGET = 30.0              # seconds for the whole scan
NONE_FOUND = "GitAway could not find a list of posts on that website. Paste the link to one post instead, or its text."
BAD_ADDRESS = "Paste your blog's address, like https://yourblog.com."

_NOT_A_PAGE = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".xml", ".css", ".js", ".mp4", ".mp3", ".zip", ".ico")
_NO_SEGMENT = {"about", "about-me", "about-us", "contact", "contact-us", "privacy", "privacy-policy", "terms", "terms-of-service", "terms-and-conditions", "disclosure", "disclaimer", "shop", "store",
               "cart", "checkout", "login", "subscribe", "press", "media-kit", "work-with-me", "advertise", "sitemap", "search", "resources", "category", "categories", "tag", "tags", "author",
               "page", "wp-content", "wp-json", "feed", "comments", "my-account"}
_STRONG = re.compile(r"\b(itinerar(?:y|ies)|trips?|days|guides?|vacations?|weekends?|things to do|what to do|with (?:kids|toddlers|babies|children|teens)|famil(?:y|ies))\b")
_DAYS = re.compile(r"\b\d+ days?\b")
PLACES = ("los angeles", "santa monica", "disneyland", "disney world", "san diego", "san francisco", "hawaii", "honolulu", "maui", "oahu", "kauai", "new york", "nyc", "tahoe", "yosemite", "orlando",
          "florida", "california", "paris", "london", "tokyo", "rome", "japan", "italy", "europe", "grand canyon", "las vegas", "seattle", "chicago", "boston", "washington", "national park")


class ScanError(ValueError):
    """A scan that found nothing; the text is fit to show a person."""


@dataclass(frozen=True)
class Post:
    url: str
    title: str
    date: str     # "2025-06-03" or ""


# ---- reading --------------------------------------------------------------------------------------------------------------------

def same_site(url, host) -> bool:
    """Is `url` an http(s) address on `host` (or its www. twin), with no user name, and no look-alike such as host.evil.example?"""
    try:
        parts = urlsplit(url)
        found = (parts.hostname or "").lower()
        bad = "@" in parts.netloc or parts.scheme not in ("http", "https")
    except ValueError:
        return False
    strip = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    return bool(found) and not bad and strip(found) == strip(host.lower())


def _get(url, kind):
    try:
        return safefetch.fetch(url, kind)
    except safefetch.FetchError as e:
        log.info("scan fetch failed code=%s", e.code)
        return None


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _parse(body):
    """The XML's root element, or None for anything unreadable or with a DOCTYPE (so no entity can be defined)."""
    try:
        return ET.fromstring(body, forbid_dtd=True)
    except (ET.ParseError, ValueError, RecursionError):      # DefusedXmlException is a ValueError
        return None


def _text(el, name) -> str:
    for child in el:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _date(raw) -> str:
    raw = (raw or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def read_sitemaps(base, host=None, started=None):
    """[(url, lastmod)] on the creator's site from /sitemap.xml: a plain list, or an index whose children are read (one level, never an index inside an index). At most MAX_URLS."""
    host, started = host or urlsplit(base).hostname, started or time.monotonic()
    out = []

    def take(root):
        for el in root:
            if _local(el.tag) == "url" and (loc := _text(el, "loc")) and same_site(loc, host) and len(out) < MAX_URLS:
                out.append((loc, _date(_text(el, "lastmod"))))

    first = _get(f"{base}/sitemap.xml", "xml")
    root = _parse(first.body) if first else None
    if root is None:
        return out
    if _local(root.tag) == "urlset":
        take(root)
    elif _local(root.tag) == "sitemapindex":
        kids = [loc for el in root if _local(el.tag) == "sitemap" and same_site(loc := _text(el, "loc"), host)]
        kids.sort(key=lambda u: "post" not in u.lower())        # the posts' sitemap before pages, categories and authors
        for kid in kids[:MAX_CHILDREN]:
            if len(out) >= MAX_URLS or time.monotonic() - started > BUDGET:
                break
            got = _get(kid, "xml")
            sub = _parse(got.body) if got else None
            if sub is not None and _local(sub.tag) == "urlset":
                take(sub)
    return out


class _Alternates(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.feeds = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "alternate" in (a.get("rel") or "").lower().split() and (a.get("type") or "").lower() in ("application/rss+xml", "application/atom+xml") and a.get("href"):
            self.feeds.append(a["href"])


def _feed_urls(base):
    home = _get(base + "/", "html")
    found = []
    if home:
        p = _Alternates()
        try:
            p.feed(home.text())
        except Exception:  # noqa: BLE001 - a page the parser chokes on has no feed we can find
            pass
        found = [urljoin(home.url, h.strip()) for h in p.feeds[:3]]
    return [*found, base + "/feed"]


def read_feed(base, host=None, started=None):
    """[(url, title, date)] from the feed the home page points to (else /feed): RSS items or Atom entries on the creator's site. At most MAX_URLS."""
    host, started = host or urlsplit(base).hostname, started or time.monotonic()
    for feed in _feed_urls(base):
        if time.monotonic() - started > BUDGET:
            break
        got = _get(feed, "xml")
        root = _parse(got.body) if got else None
        if root is None:
            continue
        out = []
        for el in root.iter():
            if _local(el.tag) not in ("item", "entry") or len(out) >= MAX_URLS:
                continue
            link = _text(el, "link")
            if not link:      # Atom: <link rel="alternate" href="...">
                links = [c for c in el if _local(c.tag) == "link" and c.get("rel", "alternate") == "alternate" and c.get("href")]
                link = links[0].get("href").strip() if links else ""
            if link and same_site(link, host):
                out.append((link, _text(el, "title"), _date(_text(el, "pubDate") or _text(el, "published") or _text(el, "updated"))))
        if out:
            return out
    return []


# ---- ranking --------------------------------------------------------------------------------------------------------------------

def title_from_url(url) -> str:
    """A readable title from the last part of an address: ".../three-days-in-san-diego/" -> "Three days in san diego"."""
    path = unquote(urlsplit(url).path)
    last = next((s for s in reversed(path.split("/")) if s), urlsplit(url).hostname or "")
    last = re.sub(r"\.(html?|php|aspx?)$", "", last, flags=re.I)
    words = re.sub(r"[-_+\s]+", " ", last).strip()
    return (words[:1].upper() + words[1:])[:120]


def score(url, title="") -> int:
    """How trip-like a post looks, from the words of its address and title: below 0 for a page that is not a post, 0 for a post with nothing trip-like, up from there."""
    parts = urlsplit(url)
    path = unquote(parts.path).lower()
    segments = [s for s in path.split("/") if s]
    if not segments or path.endswith(_NOT_A_PAGE) or any(s in _NO_SEGMENT for s in segments):
        return -1
    text = re.sub(r"[^a-z0-9]+", " ", f"{' '.join(segments[-2:])} {title}".lower()).strip()
    points = 3 * len(set(m.group(1) for m in _STRONG.finditer(text))) + 2 * sum(1 for p in PLACES if re.search(rf"\b{p}\b", text)) + (2 if _DAYS.search(text) else 0)
    return points


def _rank(entries):
    """Posts from (url, title, date) entries: the same address once, pages that are not posts dropped, most trip-like first, newer first among equals, SHOWN of them."""
    seen, posts = set(), []
    for url, title, date in entries:
        url = url.split("#")[0].strip()
        if url in seen or score(url, title) < 0:
            continue
        seen.add(url)
        posts.append(Post(url, title or title_from_url(url), date))
    posts.sort(key=lambda p: p.date, reverse=True)
    posts.sort(key=lambda p: -score(p.url, p.title))
    return posts[:SHOWN]


def discover(address) -> list:
    """The posts to offer for a blog's address, best first. Raises ScanError with a sentence fit to show."""
    try:
        link = importsource.clean_link(address)
    except importsource.SourceError as e:
        raise ScanError(str(e)) from None
    if not link:
        raise ScanError(BAD_ADDRESS)
    parts = urlsplit(link)
    base, host, started = f"{parts.scheme}://{parts.hostname}", parts.hostname, time.monotonic()
    posts = _rank((u, "", d) for u, d in read_sitemaps(base, host, started)) or _rank(read_feed(base, host, started))
    if not posts:
        raise ScanError(NONE_FOUND)
    return posts


def sample(address) -> list:
    """Fixtures for the local showcase: a made-up blog's posts at the address typed. Nothing is fetched."""
    try:
        link = importsource.clean_link(address)
    except importsource.SourceError as e:
        raise ScanError(str(e)) from None
    if not link:
        raise ScanError(BAD_ADDRESS)
    host = urlsplit(link).hostname
    rows = [("three-days-in-san-diego-with-kids", "2025-06-03"), ("disneyland-itinerary-for-toddlers", "2025-08-20"), ("a-weekend-in-lake-tahoe", "2025-04-12"),
            ("things-to-do-in-honolulu-with-kids", "2025-03-01"), ("new-york-city-with-teens-4-day-itinerary", "2025-01-18"), ("our-favourite-pancakes", "2024-11-02")]
    return _rank((f"https://{host}/{slug}", "", date) for slug, date in rows)
