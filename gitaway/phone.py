"""The guard every trip screen starts with (F-067, kept by F-254 after the phone tabs retired): a redirect when the traveler is not signed in or has no trip yet, else None."""

from urllib.parse import quote

from starlette.responses import RedirectResponse

from gitaway import session as ses, showcase


def guard(session, path):
    if not ses.current_traveler(session):
        return RedirectResponse(f"/signin?next={quote(path, safe='')}", status_code=303)
    if not ses.booking(session):
        return RedirectResponse(showcase.planning_path(), status_code=303)
    return None
