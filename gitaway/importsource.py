"""What GitAway can honestly read from what a creator pastes (F-183): a blog post, a YouTube video, an Instagram post, or their own text.

    gather(url, text)   -> Material (the words to draft from, the post's pictures, where it came from) or SourceError with a sentence fit to show

  blog       the page is fetched safely (gitaway.safefetch), the article's text is pulled out with trafilatura, its pictures are collected from the page (the `<article>`'s
             images, the share image); only pictures the page itself names, offered to the creator, never fetched until they pick one
  YouTube    the public oEmbed answer (title, channel, thumbnail) and the watch page's description and chapters; no transcript (the creator may paste it)
  Instagram  Meta does not let anyone read a post without business approval: the creator pastes the caption; the link is kept as the source card
  text       always works; it is also added to any of the above (a transcript for YouTube, notes for a blog)

Everything read here is untrusted data: it is HTML or text from a stranger's server. It is only ever shown escaped, or handed to the model inside <post> tags as data (gitaway.creatordraft).
"""

import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urljoin, urlsplit

from gitaway import robots, safefetch
from gitaway.itineraries import safe_href

MAX_TEXT_CHARS = 100_000        # about 30,000 tokens; a longer post is cut with a notice, never silently
MAX_PASTE = 120_000             # the most the paste box takes; the same cut applies
MAX_IMAGES = 12
MAX_LINK = 500
MIN_PASTED_POST = 200          # pasted text this long stands in for a page its site turns AI away from (F-194)
YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
INSTAGRAM = {"instagram.com", "www.instagram.com"}
_STAMP = re.compile(r"^\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?\s*[-–—:.)]?\s*(.{2,120})$")
_SKIP_IMG = re.compile(r"(sprite|pixel|tracking|spacer|logo|avatar|icon|emoji|gravatar|1x1|blank)", re.I)


class SourceError(ValueError):
    """Something the creator can fix by pasting differently; the text is fit to show."""


class Refused(SourceError):
    """The site's robots.txt turned the page away (or could not be checked): the page is not read. A creator who pasted the post's text as well is drafted from that."""


@dataclass
class Material:
    kind: str                   # "blog", "youtube", "instagram" or "text"
    text: str                   # the words to draft from (cut to MAX_TEXT_CHARS)
    url: str = ""               # the post's address (kept as the source card's link), "" for plain text
    title: str = ""
    by: str = ""                # the author or channel, as the post says it
    thumb: str = ""
    images: list = field(default_factory=list)     # picture addresses the post names, offered as picks (http or https)
    notices: list = field(default_factory=list)    # things the creator should be told (cut text, a transcript would help)


def platform(url) -> str:
    """"youtube", "instagram" or "blog" for a web address, from its host; SourceError for an address that is not http(s)."""
    link = clean_link(url)
    host = (urlsplit(link).hostname or "").lower()
    return "youtube" if host in YOUTUBE else "instagram" if host in INSTAGRAM else "blog"


def clean_link(raw) -> str:
    """The address when it is a plain http(s) link, else SourceError. (The safe fetch checks the rest again, on every hop.)"""
    url = raw.strip() if isinstance(raw, str) else ""
    if not url:
        return ""
    if len(url) > MAX_LINK or not safe_href(url):
        raise SourceError("That link doesn't look right. Copy it straight from your browser's address bar or the share button.")
    if urlsplit(url).scheme not in ("http", "https"):
        raise SourceError("Paste a web link that starts with https://.")
    return url


def _cut(text, notices):
    text = text.replace("\x00", "")
    if len(text) > MAX_TEXT_CHARS:
        notices.append(f"Your post is long, so GitAway read only the first {MAX_TEXT_CHARS:,} characters (about 30,000 tokens). Anything after that is not in the draft.")
        text = text[:MAX_TEXT_CHARS]
    return text


# ---- HTML helpers ------------------------------------------------------------------------------------------------------------

class _Pictures(HTMLParser):
    """Picture addresses and the page's own title/description from the HTML itself: the share image, and the images inside <article> or <main> (else the whole body)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.title, self._in_title = {}, "", False
        self.depth = {"article": 0, "main": 0}
        self.inside, self.outside = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.depth:
            self.depth[tag] += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or (a.get("srcset") or "").split(",")[0].split(" ")[0]
            small = any(str(a.get(k) or "").isdigit() and int(a[k]) < 200 for k in ("width", "height"))
            if src and not small and not src.startswith("data:"):
                (self.inside if any(self.depth.values()) else self.outside).append(src)

    def handle_endtag(self, tag):
        if tag in self.depth:
            self.depth[tag] = max(0, self.depth[tag] - 1)
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _pictures(page, base):
    p = _Pictures()
    try:
        p.feed(page)
    except Exception:  # noqa: BLE001 - a page the parser chokes on just offers no pictures
        pass
    found = ([p.meta["og:image"]] if p.meta.get("og:image") else []) + (p.inside or p.outside)
    out = []
    for src in found:
        url = urljoin(base, html.unescape(src).strip())
        if safe_href(url) and urlsplit(url).scheme in ("http", "https") and not url.lower().split("?")[0].endswith((".svg", ".gif", ".ico")) and not _SKIP_IMG.search(urlsplit(url).path) and url not in out:
            out.append(url)
    return out[:MAX_IMAGES], p


# ---- the sources -------------------------------------------------------------------------------------------------------------

def _blog(url, notices, asked=True) -> Material:
    if (why := robots.check(url, asked)):      # the site's own file decides whether an AI tool may read this page (F-194)
        raise Refused(why)
    try:
        got = safefetch.fetch(url, "html", asked=asked)
    except safefetch.FetchError as e:
        raise SourceError(f"{e} You can paste the text of your post instead.") from None
    page = got.text()
    try:
        import trafilatura
        body = trafilatura.extract(page, url=got.url, include_comments=False, include_tables=False, favor_precision=True) or ""
        meta = trafilatura.extract_metadata(page, default_url=got.url)
    except Exception:  # noqa: BLE001 - the extractor failing on a strange page is the same as finding no article
        body, meta = "", None
    images, p = _pictures(page, got.url)
    if len(body.strip()) < 200:
        raise SourceError("GitAway could not find the article's text on that page. Paste the text of your post instead.")
    title = (getattr(meta, "title", "") or p.meta.get("og:title") or p.title or "").strip()
    return Material("blog", _cut(body.strip(), notices), got.url, title[:200], (getattr(meta, "author", "") or getattr(meta, "sitename", "") or "").strip()[:100], images[0] if images else "", images)


def _video_id(url) -> str:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() == "youtu.be":
        return parts.path.strip("/").split("/")[0]
    q = parse_qs(parts.query)
    if q.get("v"):
        return q["v"][0]
    m = re.match(r"/(?:shorts|embed|live|v)/([\w-]{6,20})", parts.path)
    return m.group(1) if m else ""


def _chapters(description):
    """Lines of a description that start with a time ("0:00 Intro", "12:30 - Pier"): the creator's own chapters."""
    out = []
    for line in description.splitlines():
        m = _STAMP.match(line)
        if m:
            out.append(f"{m.group(1)} {m.group(2).strip()}")
    return out if len(out) >= 2 else []


def _watch_description(page) -> str:
    """The description from the watch page: the player's own JSON ("shortDescription") when present, else the share description."""
    m = re.search(r'"shortDescription":"((?:[^"\\]|\\.){0,8000})"', page)
    if m:
        try:
            return json.loads(f'"{m.group(1)}"')
        except ValueError:
            pass
    _, p = _pictures(page, "")
    return p.meta.get("og:description") or p.meta.get("description") or ""


def _youtube(url, notices, asked=True) -> Material:
    vid = _video_id(url)
    if not re.fullmatch(r"[\w-]{6,20}", vid or ""):
        raise SourceError("That YouTube link goes to a page, not to one video. Paste the link to the video itself.")
    watch = f"https://www.youtube.com/watch?v={vid}"
    if (why := robots.check(watch, asked)):
        raise Refused(why)
    title = by = thumb = description = ""
    try:
        data = json.loads(safefetch.fetch("https://www.youtube.com/oembed?format=json&url=" + quote(watch, safe=""), "json", asked=asked).text())
        title, by, thumb = str(data.get("title") or ""), str(data.get("author_name") or ""), str(data.get("thumbnail_url") or "")
    except (safefetch.FetchError, ValueError, AttributeError):
        pass
    try:
        description = _watch_description(safefetch.fetch(watch, "html", asked=asked).text())
    except safefetch.FetchError:
        pass
    if not title and not description:
        raise SourceError("GitAway could not read that video. Paste its transcript or description instead.")
    chapters = _chapters(description)
    lines = [f"Video title: {title}", f"Channel: {by}", f"Description:\n{description.strip()}"]
    if chapters:
        lines.append("Chapters:\n" + "\n".join(chapters))
    notices.append("GitAway drafted this from the video's title, description and chapters. Paste the transcript next time for a better draft.")
    thumb = thumb if safe_href(thumb) and urlsplit(thumb).scheme in ("http", "https") else ""
    return Material("youtube", "\n".join(lines), watch, title[:200], by[:100], thumb, [thumb] if thumb else [])


def offline(url="", text="") -> Material:
    """The pasted text (and the link, kept only as the source card), with nothing fetched: for "Write it myself" and for a copy where drafting is not switched on."""
    link, notices = clean_link(url), []
    return Material(platform(link) if link else "text", _cut((text or "").strip()[:MAX_PASTE], notices), link, notices=notices)


def gather(url="", text="", asked=True) -> Material:
    """The material to draft from. `url` is the post's address (or ""), `text` what the creator pasted (or ""). `asked`: the author asked for this read; False for the captain's pre-draft,
    whose fetches say they did not (F-194). Raises SourceError with a sentence fit to show."""
    link = clean_link(url)
    text = (text or "").strip()[:MAX_PASTE]
    if not link and not text:
        raise SourceError("Paste the link to your post, or the text of it.")
    notices = []
    kind = platform(link) if link else "text"
    if kind == "instagram":
        if len(text) < 20:
            raise SourceError("Instagram does not let GitAway read posts. Paste the caption (or the text of your post) as well, and we will keep the link as your source.")
        return Material("instagram", _cut(text, notices), link, "", "", "", [], notices)
    if kind == "text":
        return Material("text", _cut(text, notices), "", "", "", "", [], notices)
    try:
        got = _blog(link, notices, asked) if kind == "blog" else _youtube(link, notices, asked)
    except Refused:
        if len(text) < MIN_PASTED_POST:     # nothing pasted to draft from: say to paste it
            raise
        return Material(kind, _cut(text, notices), link, "", "", "", [], notices)    # the pasted text is the post; the link stays as its source card, as for Instagram
    if text:     # a transcript or notes the creator added: the draft reads them after the page
        if kind == "youtube":
            notices[:] = [n for n in notices if "transcript" not in n]
        got.text = _cut(f"{got.text}\n\n{'Transcript pasted by the creator' if kind == 'youtube' else 'Notes pasted by the creator'}:\n{text}", notices)
    got.notices = list(dict.fromkeys(notices))
    return got
