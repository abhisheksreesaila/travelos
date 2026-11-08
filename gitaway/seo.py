"""What a search engine may index and a link preview may show (F-196). Plain functions; the routes are gitaway/pages/crawlers.py and the tags are `layout.seo_meta`.

    imported(slug)         is this published trip a copy of a creator's post (made through the import, then published by the creator)? Those pages carry `robots noindex`:
                           GitAway tells Google not to index its copy, so the creator's own post keeps its ranking. A family's own published trip (the founder's) is not a copy and stays indexable.
    indexable_trips()      [(slug, last change)] of the live trips a search engine may list: everything published and not taken down, except the copies
    sitemap_xml(), robots_txt()   the two files, on the site's public address (GITAWAY_PUBLIC_URL)

robots.txt does not keep crawlers out of /trips/: a page that is disallowed cannot be read, so a crawler would never see its noindex.
"""

from xml.sax.saxutils import escape

from sqlalchemy import text

from gitaway import blogbutton, community, creatordraft

STATIC = ("/", "/for-creators", "/privacy", "/terms")      # the pages that exist in both modes and say nothing private
DISALLOW = ("/admin", "/claim/", "/go/", "/creators/import", "/report")      # the captain's page, a claim link, the partner redirect, a creator's private drafts, the report form


def imported(slug) -> bool:
    with creatordraft._db() as db:
        return db.conn.execute(text("SELECT 1 FROM creator_drafts WHERE slug = :s"), {"s": str(slug)}).fetchone() is not None


def indexable_trips() -> list:
    with creatordraft._db() as db:
        copies = {r[0] for r in db.conn.execute(text("SELECT slug FROM creator_drafts"))}
    return [(r["slug"], r["updated_at"][:10]) for r in community.rows(kind="scrapbook") if r["slug"] not in copies]


def sitemap_xml() -> str:
    base = blogbutton.base_url()
    pages = [(base + path, "") for path in STATIC] + [(f"{base}/trips/{slug}", day) for slug, day in indexable_trips()]
    items = "".join(f"<url><loc>{escape(url)}</loc>" + (f"<lastmod>{day}</lastmod>" if day else "") + "</url>\n" for url, day in pages)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}</urlset>\n'


def robots_txt() -> str:
    return "\n".join(["User-agent: *", *(f"Disallow: {path}" for path in DISALLOW), f"Sitemap: {blogbutton.base_url()}/sitemap.xml", ""])
