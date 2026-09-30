"""Landing page. F-013 replaces this placeholder with the split-hero cover page."""

from fasthtml.common import A, Div, H1, P, Section

from gitaway.layout import page


def register(app):
    @app.get("/")
    def home():
        return page(
            "",
            Section(
                Div(
                    H1("Fork a getaway."),
                    P("Plan, book and share a trip with everything you need on one screen."),
                    Div(A("Plan a trip", href="/plan", cls="btn btn-primary"),
                        A("Get inspired", href="/discover", cls="btn"), cls="ga-actions"),
                ),
                cls="ga-soon ga-wrap",
            ),
        )
