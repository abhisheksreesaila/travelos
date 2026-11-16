"""Friendly placeholders for screens that later tickets build, so no nav link is a dead end."""

from fasthtml.common import A, H1, P

from gitaway.layout import notice

# path -> (nav path it lights up, title, promise, ticket that replaces it)
PLACEHOLDERS = {
}


def soon(title, promise, current=""):
    return notice(title, H1(title), P(promise), A("Back to the start", href="/", cls="btn btn-primary"), current=current)


def _route(app, path, current, title, promise):
    @app.get(path)
    def placeholder():
        return soon(title, promise, current)


def register(app):
    for path, (current, title, promise, _ticket) in PLACEHOLDERS.items():
        _route(app, path, current, title, promise)
