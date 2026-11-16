"""The two writes the planning page's "Together" drawer makes (F-254; they were the old Family tab's and the old plan chat's): a message in the trip's thread and a message on one plan.

POST /trip/family/message   the trip's chat (fields text, trip, cid)
POST /trip/talk/message     a plan's chat or one part's (fields act, part, text, trip, cid)

The drawer (assets/js/v2plan.js) sends `X-Fragment: 1` and reads the thread again itself, so a good write answers 204; a refusal is a plain sentence with its status. Both are on
gitaway.access.OPEN_POSTS: talking changes no plan, so a viewer may do it. The rules and the storage are gitaway/familythread.py and gitaway/plantalk.py.
"""

from starlette.responses import PlainTextResponse, RedirectResponse, Response

from gitaway import familythread, plantalk, session as ses

STALE = "This trip changed. Reload the page."


def _answer(request, error=None, status=400):
    if request.headers.get("x-fragment") == "1":
        return PlainTextResponse(error, status_code=status) if error else Response(status_code=204)
    return RedirectResponse("/trip/plan", status_code=303)


def register(app):
    @app.post("/trip/family/message")
    def message(request, session, text: str = "", trip: str = "", cid: str = ""):
        if not ses.current_traveler(session):
            return Response("Sign in first.", status_code=401)
        try:
            familythread.post_message(session, text, trip=trip or None, cid=cid)
        except familythread.StaleTrip:
            return _answer(request, STALE, 409)
        except familythread.ThreadError as e:
            return _answer(request, str(e))
        return _answer(request)

    @app.post("/trip/talk/message")
    def plan_message(request, session, act: str = "", part: str = "", text: str = "", trip: str = "", cid: str = ""):
        if not ses.current_traveler(session):
            return Response("Sign in first.", status_code=401)
        try:
            plantalk.post_message(session, act, part, text, trip=trip or None, cid=cid)
        except familythread.StaleTrip:
            return _answer(request, plantalk.STALE, 409)
        except familythread.ThreadError as e:
            return _answer(request, str(e), getattr(e, "status", 400))
        return _answer(request)
