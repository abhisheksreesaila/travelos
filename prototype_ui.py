"""Shared HTML shell for the isolated TravelOS visual prototype."""

from __future__ import annotations

import re
from html import escape
from urllib.parse import urlencode, urlsplit, urlunsplit


_ACTIVE_PAGES = {"home", "discover", "creators", "signin", "workspace", "plans"}
_VARIANTS = {"A", "B", "C"}
_ASSET_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_NAV_ITEMS = (
    ("discover", "Discover", "/discover"),
    ("plans", "Trip plans", "/plans/granada-after-dark"),
    ("creators", "Creator studio", "/creators"),
    ("workspace", "My trips", "/workspace"),
)


def _variant_url(path: str, variant: str) -> str:
    parts = urlsplit(path)
    query = dict(part.split("=", 1) for part in parts.query.split("&") if "=" in part)
    query["variant"] = variant
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _asset_tag(filename: str, kind: str) -> str:
    suffix = ".css" if kind == "style" else ".js"
    if (
        not _ASSET_NAME.fullmatch(filename)
        or filename in {".", ".."}
        or not filename.startswith("prototype_")
        or not filename.endswith(suffix)
    ):
        raise ValueError(f"Invalid prototype {kind} asset filename: {filename!r}")
    path = escape(filename, quote=True)
    if kind == "style":
        return f'<link rel="stylesheet" href="/assets/{path}">'
    return f'<script type="module" src="/assets/{path}"></script>'


def _brand_mark() -> str:
    return """<svg class="p-brand-mark" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="19" fill="#FFD257"/>
      <path d="M8 24.5 30.5 8 22 32l-4-10-10-3Z" fill="#F0643D"/>
      <path d="m18 22 12.5-14-8 24-4-10Z" fill="#7357D8"/>
      <circle cx="20" cy="20" r="2.2" fill="#fffdf7"/>
    </svg>"""


def render_prototype(
    title,
    content,
    active,
    variant,
    page_styles=(),
    page_scripts=(),
) -> str:
    """Render a complete, standalone prototype document around trusted page HTML.

    ``content`` is pre-rendered HTML. Optional page assets are filenames within
    ``/assets``; the common prototype stylesheet and script always load first.
    """
    current_variant = variant if variant in _VARIANTS else "A"
    current_page = active if active in _ACTIVE_PAGES else "home"
    page_class = "prototype-shell" + (" is-creator-page" if current_page == "creators" else "")

    def nav_link(key: str, label: str, path: str) -> str:
        active_class = " is-active" if current_page == key else ""
        current_attr = ' aria-current="page"' if current_page == key else ""
        href = escape(_variant_url(path, current_variant), quote=True)
        return (
            f'<a class="p-nav-link{active_class}" href="{href}" '
            f'data-variant-route="{escape(path, quote=True)}"{current_attr}>'
            f'{escape(label)}</a>'
        )

    nav = "".join(nav_link(*item) for item in _NAV_ITEMS)
    sign_in_url = _variant_url("/signin", current_variant)
    sign_in_current = ' aria-current="page"' if current_page == "signin" else ""
    sign_in = (
        f'<a class="p-button p-button-ghost p-header-account" href="{escape(sign_in_url, quote=True)}" '
        f'data-variant-route="/signin"{sign_in_current}>Sign in</a>'
    )
    layout_switcher = ""
    if current_page == "creators":
        options = (
            ("A", "Source desk"),
            ("B", "Transcript review"),
            ("C", "Itinerary board"),
        )
        def variant_link(key: str, label: str) -> str:
            selected_class = " is-selected" if current_variant == key else ""
            current_attr = ' aria-current="page"' if current_variant == key else ""
            href = escape(_variant_url("/creators", key), quote=True)
            return (
                f'<a class="p-layout-link{selected_class}" href="{href}" '
                f'data-creator-variant="{key}"{current_attr}>'
                f'<span class="p-layout-key">{key}</span><span>{label}</span></a>'
            )

        links = "".join(variant_link(*item) for item in options)
        layout_switcher = f"""<nav class="p-variant-bar p-container" aria-label="Compare creator layouts">
          <div class="p-variant-caption"><strong>Creator layout</strong>
            <span data-variant-live aria-live="polite">Variant {current_variant}</span>
            <span class="p-sr-only" data-variant-announcement aria-live="polite"></span>
          </div>
          <div class="p-variant-options">
            <button class="p-variant-arrow" type="button" data-variant-step="-1" aria-label="Previous creator layout">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 5-7 7 7 7"/></svg>
            </button>
            {links}
            <button class="p-variant-arrow" type="button" data-variant-step="1" aria-label="Next creator layout">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 5 7 7-7 7"/></svg>
            </button>
          </div>
          <span class="p-variant-hint">Use ← → to compare</span>
        </nav>"""
    compare_link = ""
    if current_page != "creators":
        creators_url = escape(_variant_url("/creators", current_variant), quote=True)
        compare_link = f"""<footer class="p-prototype-footer p-container">
          <a href="{creators_url}" data-variant-route="/creators">Compare creator layouts <span aria-hidden="true">→</span></a>
        </footer>"""

    extra_styles = "".join(_asset_tag(filename, "style") for filename in page_styles)
    extra_scripts = "".join(_asset_tag(filename, "script") for filename in page_scripts)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#F5F2E8">
  <meta name="description" content="A colorful, local-only TravelOS prototype.">
  <title>{escape(str(title))} · TravelOS</title>
  <link rel="stylesheet" href="/assets/prototype.css">
  {extra_styles}
</head>
<body class="{page_class}" data-prototype-page="{current_page}" data-creator-variant="{current_variant}">
  <a class="p-skip-link" href="#main">Skip to content</a>
  <header class="p-header">
    <div class="p-container p-header-inner">
      <a class="p-brand" href="{escape(_variant_url("/", current_variant), quote=True)}" data-variant-route="/" aria-label="TravelOS home">
        {_brand_mark()}<span>Travel<span class="p-brand-os">OS</span></span>
      </a>
      <nav class="p-nav" aria-label="Primary navigation">{nav}</nav>
      <div class="p-header-actions">
        {sign_in}
      </div>
    </div>
  </header>
  <aside class="p-demo-banner" aria-label="Prototype limitations">
    <span class="p-demo-dot" aria-hidden="true"></span>
    <span><strong>Local demo</strong> · Simulated only—no live fetching, transcription, weather, or booking. Progress resets on reload.</span>
  </aside>
  {content}
  {compare_link}
  {layout_switcher}
  <script type="module" src="/assets/prototype.js"></script>
  {extra_scripts}
</body>
</html>"""
