"""A block's steps (F-080), and the old Add to the trip address (F-087).

GET  /trip/block?id=a3           redirects to the canvas block (F-081); the block page itself is gitaway/pages/tripcanvas.py
POST /trip/block/step            one tap on a step: done, not done, set aside, put back

The Paste & Convert screens that lived here (GET /trip/add, POST /trip/add/convert, /questions, /save ...) are folded into the one Ask box (F-087): see
gitaway/pages/tab_ask.py, which also answers the old GET /trip/add by landing in the box, and gitaway/say.py. The draft, the questions and the saving are
still gitaway/canvas.py. Every write is gated by gitaway.access (editors).
"""

from starlette.responses import RedirectResponse

from gitaway import canvas, phone, session as ses
from gitaway.pages.trip import trip_url


def _guard(session):
    return phone.guard(session, "/trip")


def register(app):
    # ---- a block's parts and steps ---------------------------------------------------------------------------------------

    @app.get("/trip/block")
    def block_page(request, session, id: str = ""):
        if (r := _guard(session)):
            return r
        view = canvas.block(session, id[:8])
        if view is None:
            return RedirectResponse(trip_url(), status_code=303)
        return RedirectResponse(f"/trip/canvas?block={view['act'].id}" + (f"&trip={ses.open_trip_id()}" if ses.open_trip_id() else ""), status_code=303)   # F-081: the block lives in the canvas now

    @app.post("/trip/block/step")
    async def step(request, session):
        if (r := _guard(session)):
            return r
        form = await request.form()
        act = (form.get("act") or "")[:8]
        do = form.get("do") or ""
        sid = (form.get("step") or "")[:40]
        try:
            if do in ("done", "undone"):
                canvas.set_done(session, sid, do == "done")
            elif do in ("aside", "back"):
                canvas.set_aside(session, sid, do == "aside")
        except canvas.CanvasError:
            pass       # a step someone else just removed: show the block as it is now
        return RedirectResponse(f"/trip/canvas?block={act}" + (f"&trip={ses.open_trip_id()}" if ses.open_trip_id() else ""), status_code=303)
