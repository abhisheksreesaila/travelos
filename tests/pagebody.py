"""A page without its top bar. The v2 bar (v2.py) names no trip and holds no switch form, so a test that asks "is this trip's name on this page?" reads the page as it is;
the function stays as the one place to change if a bar ever carries one again (F-139's did)."""


def without_bar(html):
    return html
