"""GET /robots.txt and GET /sitemap.xml (F-196): what search engines may read. Open to everyone, in both showcase modes. The rules are gitaway/seo.py."""

from starlette.responses import Response

from gitaway import seo

CACHE = {"Cache-Control": "public, max-age=3600"}


def register(app):
    @app.get("/robots.txt")
    def robots():
        return Response(seo.robots_txt(), media_type="text/plain", headers=CACHE)

    @app.get("/sitemap.xml")
    def sitemap():      # a plain def: it reads the community database off the event loop
        return Response(seo.sitemap_xml(), media_type="application/xml", headers=CACHE)
