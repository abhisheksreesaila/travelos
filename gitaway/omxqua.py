"""The omxqua Travel "Coast" look (autopilot M5, decisions D-50, D-60 to D-66): which pages wear it, and how.

`before` runs for every request. For the paths in SKINS it puts `oq-root oq-light oq-family-travel` on <html> (the language's root; the tokens are `--oq-*`, assets/css/omxqua.css) and
adds the Coast stylesheets after the page's own, so the old screens keep their markup and take the new surfaces, type and colour. Every other page is untouched.
The language is omxqua v0.1.6 (~/Projects/omxqua), with GitAway orange as the accent (D-60); the rules for it on this site are in design-system/DESIGN-SYSTEM.md "Coast".
"""

from fasthtml.common import Link

ROOT = "oq-root oq-light oq-family-travel"
# (path prefix, the stylesheets that go after omxqua.css). /plan/quote is JSON and never reads them.
SKINS = (("/plan", ("plan_coast.css",)), ("/creators", ("creators_coast.css",)), ("/sandbox", ()), ("/partners", ()))


def skin_for(path: str):
    """The Coast stylesheets for a path, or None when the page keeps its own look. A prefix matches whole path parts (/plans is not /plan)."""
    for prefix, sheets in SKINS:
        if path == prefix or path.startswith(prefix + "/"):
            return sheets
    return None


def before(req):
    sheets = skin_for(req.url.path)
    if sheets is None:
        return None
    req.htmlkw["cls"] = ROOT
    req.hdrs = [*req.hdrs, *[Link(rel="stylesheet", href=f"/assets/css/{name}") for name in ("omxqua.css", *sheets)]]
    return None
