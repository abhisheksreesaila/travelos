"""F-191: the "Plan this trip on GitAway" button a creator pastes into their blog.

Pure functions, no framework: the badge SVG (a stable public URL, no script, no tracking), the absolute link a reader taps, and the two things the creator copies (an HTML snippet and
a plain link). The link is built on GITAWAY_PUBLIC_URL, never on the request's Host, and carries `via=<handle>` (F-184). The screens are gitaway/pages/blogbutton.py.
"""

from html import escape
from urllib.parse import quote

from gitaway import passkeys
from gitaway.icons import PATHS

DEFAULT_BASE = "https://gitaway.me"
LIGHT, DARK = "/badge/plan-this-trip.svg", "/badge/plan-this-trip-dark.svg"
ALT = "Plan this trip on GitAway"
SIZE = (248, 56)
# (background, edge, text) of the two variants; the mark is always the GitAway orange with its ink fork.
_COLOURS = {False: ("#fffdf9", "#e7e0d4", "#1d1a16"), True: ("#1e1a2e", "#3a3450", "#fffdf9")}
_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def base_url() -> str:
    """The site's public address (no trailing slash): GITAWAY_PUBLIC_URL when it is a plain https address, else gitaway.me."""
    host = passkeys.public_host()
    return f"https://{host}" if host else DEFAULT_BASE


def trip_link(slug, handle) -> str:
    return f"{base_url()}/trips/{quote(str(slug), safe='')}?via={quote(str(handle), safe='')}"


def badge_svg(dark=False) -> str:
    bg, edge, ink = _COLOURS[dark]
    w, h = SIZE
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{ALT}"><title>{ALT}</title>'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{bg}" stroke="{edge}"/>'
            f'<rect x="10" y="10" width="36" height="36" rx="10" fill="#FF7352"/>'
            f'<g transform="translate(18 18) scale(0.8333)" fill="none" stroke="#1E1A2E" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">{PATHS["fork"]}</g>'
            f'<text x="58" y="25" font-family="{_FONT}" font-size="12" fill="{ink}" opacity="0.72">Plan this trip on</text>'
            f'<text x="58" y="43" font-family="{_FONT}" font-size="17" font-weight="800" fill="{ink}">GitAway</text></svg>')


def html_snippet(slug, handle) -> str:
    """The HTML a creator pastes: one link around one picture (light, and dark for readers whose browser asks for it). Everything in it is escaped."""
    def q(s):
        return escape(s, quote=True)
    w, h = SIZE
    return (f'<a href="{q(trip_link(slug, handle))}" target="_blank" rel="noopener">'
            f'<picture><source media="(prefers-color-scheme: dark)" srcset="{q(base_url() + DARK)}">'
            f'<img src="{q(base_url() + LIGHT)}" alt="{ALT}" width="{w}" height="{h}"></picture></a>')


def text_link(slug, handle) -> str:
    """The plain link, for a post that only takes text."""
    return trip_link(slug, handle)
