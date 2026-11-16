"""The v2 look for the pages that were Direction A's forms and reading pages (F-272, D-810): Plan it for me, import and build a trip, the creator claim, drafts, settings and stats,
the sandbox checkout. They keep their own markup and stylesheets; `assets/css/v2pages.css` points Direction A's old token names at v2's values on a `.v2` page and gives the old
`.btn`, `.card`, form fields and headings the v2 look (Newsreader, near-opaque cards, indigo primary, press), loaded after each page's own stylesheet."""
from fasthtml.common import Link

HEAD = (Link(rel="stylesheet", href="/assets/css/v2pages.css"),)
