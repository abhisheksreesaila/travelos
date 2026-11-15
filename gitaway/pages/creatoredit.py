"""The details editor, in the book's language (F-259, D-680..): where "edit the details" lands from the book, My drafts, the import's "Edit the details first", the claim link and a refused publish.

One page, `layout.page(v2="cv")` with cv2.css and cvedit.css: the trip (title, name, place, who it is good for), the cover (the post's pictures), each day (heading, note, stops with time, name,
note, link, move up and down, remove), tips, and the post it came from. It is a form over the same draft rules as ever: it posts to `creatordraft.apply` through the route in creatorimport.py
(or the captain's /admin/drafts/<id>), so there is no second write path, and its words are the creator's: nothing is filled in for them. A word can also be fixed in place in the book itself.
"""

from fasthtml.common import A, Button, Details, Div, Form, H1, H2, Img, Input, Label, Link, Option, P, Section, Select, Span, Summary, Textarea

from gitaway import community, creatorbook as cb, creatordraft as cd, hub, stoplinks
from gitaway.layout import page
from gitaway.pages import bookview

PATH = "/creators/import"
HEAD = (Link(rel="stylesheet", href="/assets/css/cv2.css"), Link(rel="stylesheet", href="/assets/css/cvedit.css"))
ico = bookview.ico


def _field(label, control, cls="", hint=""):
    return Label(Span(label, cls="ed-lab"), control, Span(hint, cls="ed-hint") if hint else "", cls=f"ed-f {cls}".strip())


def _input(name, value, limit, placeholder="", **more):
    return Input(type="text", name=name, value=value, maxlength=str(limit), placeholder=placeholder, autocomplete="off", cls="ed-in", **more)


def _chip(name, value, label, on):
    return Label(Input(type="checkbox", name=name, value=value, checked=on or None, cls="v2-sr"), Span(label, cls="ed-chip"), cls="ed-chip-l")


def _stop(i, j, count, s):
    k = f"d{i}s{j}"
    unsure = s["name"] == cd.UNNAMED
    who = s["name"] or f"stop {j + 1}"

    def op(do, label, glyph):
        return Button(ico(glyph), type="submit", name="do", value=do, formnovalidate=True, aria_label=label, cls="ed-op")
    return Div(
        bookview.kt(cb.kind_of(s["name"])),
        Div(_field("Time", _input(f"{k}_time", s["time"], 12, "9:00 AM"), "ed-time"),
            _field("Where", _input(f"{k}_name", s["name"], cd.MAX_STOP, "Where", aria_invalid="true" if unsure else None), "ed-where" + (" ci-unsure" if unsure else "")),
            _field("Your note", _input(f"{k}_note", s["note"], cd.MAX_STOP_NOTE, "A short note (optional)"), "ed-snote"),
            _field("Booking or ticket link", _input(f"{k}_link", s.get("link", ""), stoplinks.MAX, "A booking or ticket link (optional)", inputmode="url"), "ed-slink"), cls="ed-stop-fields"),
        Div(op(f"up_stop:{i}:{j}", f"Move {who} up", "l") if j else "", op(f"down_stop:{i}:{j}", f"Move {who} down", "r") if j < count - 1 else "",
            op(f"del_stop:{i}:{j}", f"Remove {who} from day {i + 1}", "x"), cls="ed-ops"), cls="ed-stop")


def _day(i, day, many):
    n = len(day["stops"])
    return Section(
        Div(Span(f"Day {i + 1}", cls="ed-day-n"), _field("Heading", _input(f"d{i}_title", day["title"], cd.MAX_DAY_TITLE, "A title for the day"), "ed-day-t"), cls="ed-day-h"),
        _field("About the day", Textarea(day["note"], name=f"d{i}_note", rows="2", maxlength=str(cd.MAX_NOTE), placeholder="What was this day like? (optional, in your own words)", cls="ed-in ed-area"), "ed-day-note"),
        *[_stop(i, j, n, s) for j, s in enumerate(day["stops"])],
        Div(Button(ico("arrow"), "Add a stop", type="submit", name="do", value=f"add_stop:{i}", formnovalidate=True, cls="tonal"),
            Button("Remove this day", type="submit", name="do", value=f"del_day:{i}", formnovalidate=True, cls="tonal") if many else "", cls="ed-row"), cls="ed-card ed-day", id=f"ed-day-{i}")


def _tile(d, n, url):
    copy = d["copies"].get(str(n))
    src = f"{PATH}/{d['id']}/photo/{copy}-thumb.jpg" if copy else url
    return Div(Label(Input(type="checkbox", name="pick", value=str(n), checked=n in d["picks"] or None, cls="v2-sr pb-pick"),
                     Img(src=src, alt=f"Picture {n + 1} from your post", loading="lazy", referrerpolicy="no-referrer"), Span(ico("check"), cls="ed-tick", aria_hidden="true"), cls="ed-photo pb-photo"),
               Label(Input(type="radio", name="cover", value=str(n), checked=str(n) == d["cover"] or None, cls="v2-sr pb-cover"), Span(ico("see"), "Cover", cls="ed-cover pb-cover-b"), title="Use as the cover photo"), cls="ed-tile pb-tile")


def _source(d):
    s = d.get("source") or {}
    if not s.get("url"):
        return ""
    return Div(Span("Your post", cls="ed-lab"), A(s.get("title") or s["url"], href=s["url"], rel="noopener noreferrer", target="_blank", cls="ed-src"),
               Span(s.get("by") or "", cls="ed-hint") if s.get("by") else "", cls="ed-card ed-source", id="ci-source")


def editor_page(d, error="", just=False, captain=False):
    """The editor. `captain`: the captain reviewing a pre-draft nobody has claimed (F-194): it posts to /admin/drafts/<id>, shows no pictures to pick and nothing to preview, publish or delete."""
    base = f"/admin/drafts/{d['id']}" if captain else f"{PATH}/{d['id']}"
    place = Select(*[Option(label, value=k, selected=k == d["place"] or None) for k, label in [*cd.PLACES.items(), ("other", "Somewhere else")]], name="place", id="ci-place", cls="ed-in")
    unsure = sum(1 for day in d["days"] for s in day["stops"] if s["name"] == cd.UNNAMED)
    status = Span(ico("check"), "Published", cls="tag live") if d["live"] else Span("Draft: nobody can see this yet", cls="tag")
    top = Div(Div(status, A(ico("l"), "Back to the guide", href=f"{base}/guide", cls="tonal", id="ed-book") if not captain else "", cls="ed-top-row"),
              H1("Check this pre-draft" if captain else "The details of your guide", cls="disp"),
              P("Nothing is public. Fix what the model got wrong, then send the claim link." if captain else "Everything the guide says, in one place. Nothing is public until you publish it from the guide; "
                "fix a word right in the guide any time too.", cls="ed-lede"),
              *[P(n, role="note", cls="ed-note", id=f"ci-notice-{i}") for i, n in enumerate(d["notices"])],
              P(f"{unsure} stop{'s' if unsure != 1 else ''} GitAway was not sure of {'are' if unsure != 1 else 'is'} marked \"{cd.UNNAMED}\". Name {'them' if unsure != 1 else 'it'} or take {'them' if unsure != 1 else 'it'} out.",
                role="note", cls="ed-note ci-unsure-note", id="ci-unsure") if unsure else "", cls="ed-top")
    waiting = d["live"] and community.review_state(d["slug"]) == "pending"      # F-194: published, but in no list until the captain says yes
    done = Div(Span(ico("check"), "It's live", cls="tag live"),
               P("It is published but unlisted: only people with its link can see it until the captain approves it. Publish again to update it." if waiting else "Anyone can read it and fork it now. Publish again to update it."),
               Div(A(ico("share"), "View your trip page", href=f"/trips/{d['slug']}", cls="go", id="pb-view"), *([] if waiting else [A("See it in Guides", href="/guides", cls="tonal")]), cls="ed-row"),
               cls="ed-card ed-live pb-live", role="status") if d["live"] and just else ""
    paste = Details(Summary("Your pasted text"), P(d["text"], cls="ed-pasted ci-pasted"), cls="ed-card ci-details", id="ci-pasted") if d.get("text") else ""
    tips = (d["tips"] + [""] * 3)[:max(3, min(len(d["tips"]) + 1, cd.MAX_TIPS))]
    pics = Section(H2("The cover", cls="ed-h"), P(f"Optional. Tap up to {cd.MAX_PICKS} of your post's pictures to put in the guide, and the star for the cover. They are copied from your own post and stripped of where they were taken; "
                                                   "without one the guide has a drawing, labelled as one.", cls="ed-hint"),
                   Div(*[_tile(d, n, u) for n, u in enumerate(d["images"])], cls="ed-grid"), cls="ed-card ci-pics", id="ci-pics") if d["images"] else ""
    form = Form(
        Button("Save", type="submit", name="do", value="save", cls="v2-sr", tabindex="-1", aria_hidden="true"),     # Enter in a field saves; it never removes a stop
        Section(H2("The trip", cls="ed-h"),
                Div(_field("Title", Input(type="text", id="ci-title", name="title", value=d["title"], maxlength=str(cd.MAX_TITLE), autocomplete="off", cls="ed-in")),
                    _field("Their name on it" if captain else "Your name on it", Input(type="text", id="ci-name", name="name", value=d["name"], maxlength=str(cd.MAX_NAME), autocomplete="name", cls="ed-in")),
                    _field("Where was it?", place), _field("Name the place", Input(type="text", id="ci-place-name", name="place_name", value=d["place_name"], maxlength=str(cd.MAX_PLACE), placeholder="Name the place", autocomplete="off", cls="ed-in")),
                    cls="ed-grid2"),
                Div(Span("Who is it good for?", cls="ed-lab"), Div(*[_chip("stickers", k, label, k in d["stickers"]) for k, (label, _t, _i) in hub.TAGS.items()], cls="ed-chips"), cls="ed-f"), cls="ed-card"),
        "" if captain else pics,
        *[_day(i, day, len(d["days"]) > 1) for i, day in enumerate(d["days"])],
        Button(ico("arrow"), "Add a day", type="submit", name="do", value="add_day", formnovalidate=True, cls="tonal", id="ci-add-day") if len(d["days"]) < cd.MAX_DAYS else "",
        Section(H2("A few tips", cls="ed-h"), *[Input(type="text", name="tip", value=t, maxlength=str(cd.MAX_TIP), placeholder="One thing you'd tell a friend going", autocomplete="off", aria_label=f"Tip {i + 1}", cls="ed-in")
                                              for i, t in enumerate(tips)], cls="ed-card pb-tips"),
        Div(P(error, role="alert", cls="v2-error", id="pb-error") if error else "",
            *([Button("Save draft", type="submit", name="do", value="save", cls="go", id="pb-save"), A("Back to the admin page", href="/admin#cc-section", cls="tonal", id="pb-back-admin")] if captain else
              [Button("Save and open the guide", type="submit", name="do", value="book", cls="go", id="ed-save-book"), Button("Save draft", type="submit", name="do", value="save", cls="tonal", id="pb-save"),
               Button("Preview the public page", type="submit", name="do", value="preview", cls="tonal", id="pb-preview")]), cls="ed-bar v2-glass"),
        action=base, method="post", id="ci-edit", cls="ed-form")

    def confirm(summary, sid, text, do, yes, yid):
        return Details(Summary(ico("x"), Span(summary), cls="ed-sum", id=sid),
                       Form(P(text), Input(type="hidden", name="do", value=do), Button(yes, type="submit", id=yid, cls="tonal"), action=f"{PATH}/{d['id']}", method="post", cls="ed-confirm-form"), cls="ed-confirm")
    unpub = confirm("Unpublish", "pb-unpublish", "This takes the page off GitAway for everyone. Your draft stays here, so you can publish again; its pictures are deleted and picked again then.", "unpublish", "Yes, take it down", "pb-unpublish-yes") if d["live"] else ""
    delete = confirm("Delete this draft", "ci-delete", "This deletes the draft, its pictures and, if it is live, the public page. It cannot be undone.", "delete", "Yes, delete it", "ci-delete-yes")
    body = Div(top, done, _source(d), paste, form, *([] if captain else [unpub, delete]), cls="ed ci-edit")
    return page("Check this pre-draft" if captain else "The details of your guide", body, current="/guides", head=HEAD, v2="cv is-results", noindex=True)
