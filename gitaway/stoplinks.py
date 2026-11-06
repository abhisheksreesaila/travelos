"""A stop can carry one link of the creator's own (F-196). The creator's brief says GitAway never takes their links away; their trips are mostly booking and ticket links.

A link is kept only when it goes to a site on ALLOWED (booking, ticket and affiliate sites) or to the creator's own blog (`own_domain`). Nothing else ever reaches a public page: not a
shortener, not a stranger's site, not an address with a name or an email in it. Links are never fetched by GitAway; they are drawn rel="sponsored noopener" (gitaway/itinerary_view.py).

    clean(url, own)         the address when it is allowed, else ""
    keep(url, post, own)    `clean`, and only when the address is written in the post (what the model returns is checked against the text it read)
    own_domain(kind, url)   the creator's own blog's domain ("" for a video, a pasted text or a shared host such as medium.com: those are not their site)
    without_addresses(text) the post's words with its web addresses taken out (a stop's name must be in the words, not in a link)
    host_of(url)            the name to show on the link ("booking.com")
"""

import re
from urllib.parse import urlsplit

ALLOWED = ("booking.com", "viator.com", "getyourguide.com", "amazon.com", "amzn.to", "getawaytoday.com", "stay22.com", "expedia.com", "tripadvisor.com", "klook.com")
MAX = 400
# Sites that are not one creator's own: a blog's address here (medium.com/@maya/post) must not make every link on the host "their own", and a video's or an Instagram post's address is not
# their site. A blog on its own corner of such a host (maya.blogspot.com) is still its own: only the bare host is refused.
NOT_OWN = ("medium.com", "substack.com", "wordpress.com", "blogspot.com", "blogger.com", "wixsite.com", "tumblr.com", "github.io", "notion.site", "ghost.io", "weebly.com",
           "youtube.com", "youtu.be", "instagram.com", "facebook.com", "tiktok.com")
_END = r"""(?=$|[\s)\]>"'<]|[.,;:!?]+(?:$|[\s)\]>"'<]))"""      # an address ends at the end of the text, a space, a closing bracket or quote, or punctuation that closes a sentence
LIST_TEXT = ", ".join(ALLOWED[:-1]) + " or " + ALLOWED[-1]


def _host(url) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def own_domain(kind, url) -> str:
    """The domain of a blog post's own site, without "www." ("" when the source is not a blog: a video's or a post's address is YouTube's or Instagram's, not theirs)."""
    host = _host(url) if kind == "blog" else ""
    host = host[4:] if host.startswith("www.") else host
    return "" if host in NOT_OWN else host


def clean(url, own="") -> str:
    """The address, trimmed, when it is an http(s) link to a listed site (or its subdomain) or to `own`; else "". No name or email in it ("@"), no port but the default, ASCII only, no spaces."""
    if not isinstance(url, str):
        return ""
    url = url.strip()
    if not url or len(url) > MAX or any(c.isspace() or ord(c) < 32 or ord(c) > 126 for c in url) or "@" in url:
        return ""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host or port not in (None, 80, 443):
        return ""
    return url if any(host == d or host.endswith("." + d) for d in (*ALLOWED, *([own] if own else []))) else ""


def keep(url, post, own="") -> str:
    """`clean(url)` when the post's text has that exact address in it (the whole address, not the front of a longer one), else "": a model cannot give a stop a link the creator never wrote."""
    link = clean(url, own)
    return link if link and re.search(re.escape(link) + _END, str(post or "")) else ""


def without_addresses(text) -> str:
    """The post's words with every web address taken out ([text](address) keeps its text), so a stop's name is matched against what the creator wrote, not against a URL slug."""
    return re.sub(r"https?://[^\s)\]>\"'<]+", " ", str(text or ""))


def host_of(url) -> str:
    host = _host(url)
    return host[4:] if host.startswith("www.") else host
