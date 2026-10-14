"""A page without the signed-in top bar (F-139): the bar names the open trip and its dates and holds a switch form per trip on every page,
so a test that asks "is this trip's name on this page?" or "is its id absent?" reads the page body only."""

import re


def without_bar(html):
    return re.sub(r'<header[^>]*class="ga-topbar".*?</header>', "", html, flags=re.S)
