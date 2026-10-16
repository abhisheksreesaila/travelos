"""F-177: the Family panel opens at once. The server reads the trip's messages once per request, a GET writes nothing (/trip/family/seen does), the panel draws the newest 30 messages
and a button asks for earlier ones (`before=`). The prefetch, the instant show and the timing are checked in a real browser: tests_browser/test_family_fast.py."""
import re
from html import unescape

from gitaway import familychats as fc
from tests.test_canvas import azure  # noqa: F401 - fixtures
from tests.test_family_chats import chats, say  # noqa: F401 - fixtures
from tests.test_thread import crew  # noqa: F401 - fixture


def test_a_panel_get_writes_nothing_and_reads_the_trip_once(crew, chats, monkeypatch):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "hello all"), say(ed, "Churros after", act=stroll)
    reads, plans = [], []
    real_read, real_acts = fc._read, fc.cal.activities
    monkeypatch.setattr(fc, "_read", lambda fam: reads.append(1) or real_read(fam))
    monkeypatch.setattr(fc.cal, "activities", lambda s, *a, **k: plans.append(1) or real_acts(s, *a, **k))
    r = crew[0].get("/trip/family/panel?thread=trip&day=1")
    assert r.status_code == 200 and "hello all" in r.text
    assert len(reads) == 1                                                      # one pass over the trip's messages for the rows, the count and the pane
    assert len(plans) <= 2                                                      # (the plan list: the chats' titles and kinds, and the pane's own heading)
    assert r.headers["x-family-unread"] == "1"                                  # (the stroll's; the open chat is not counted)
    monkeypatch.undo()
    assert fc.unread_total(ari) == 2                                            # nothing was marked read
    assert crew[0].get("/trip/family/list?open=trip&day=1").headers["x-family-unread"] == "1"


def test_the_panel_draws_the_newest_thirty_with_earlier_ones_on_request(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    for i in range(1, 46):
        say(ed, f"m{i:02d}")
    html = crew[0].get("/trip/family/panel?thread=trip&day=1").text
    thread = html.split('id="ft-thread"')[1].split('id="ft-empty"')[0]
    shown = re.findall(r"m\d\d", thread)
    assert shown[0] == "m16" and shown[-1] == "m45" and len(shown) == 30
    button = re.search(r'<button\b[^>]*id="ft-older"[^>]*>', html).group(0)
    url = unescape(re.search(r'data-older="([^"]+)"', button).group(1))
    first = re.search(r'data-n="(\d+)"', thread).group(1)
    r = crew[0].get(f"{url}&before={first}", headers={"Accept": "text/html"})
    got = re.findall(r"m\d\d", r.text)
    assert got[0] == "m01" and got[-1] == "m15" and len(got) == 15
    assert r.headers["x-thread-more"] == "0"
    r = crew[0].get(f"{url}&before={first}&limit=10", headers={"Accept": "text/html"})
    assert re.findall(r"m\d\d", r.text)[0] == "m06" and r.headers["x-thread-more"] == "1"


def test_a_short_chat_has_no_earlier_button(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "hello all")
    assert 'id="ft-older"' not in crew[0].get("/trip/family/panel?thread=trip&day=1").text


def test_a_plan_chat_pages_back_too(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    for i in range(1, 41):
        say(ed, f"c{i:02d}", act=stroll)
    html = crew[0].get(f"/trip/family/panel?thread={stroll}&day=1").text
    thread = html.split('id="ft-thread"')[1].split('id="ft-empty"')[0]
    assert re.findall(r"c\d\d", thread)[0] == "c11" and len(re.findall(r"c\d\d", thread)) == 30
    url = unescape(re.search(r'data-older="([^"]+)"', html).group(1))
    first = re.search(r'data-n="(\d+)"', thread).group(1)
    r = crew[0].get(f"{url}&before={first}", headers={"Accept": "text/html"})
    assert re.findall(r"c\d\d", r.text)[0] == "c01" and len(re.findall(r"c\d\d", r.text)) == 10 and r.headers["x-thread-more"] == "0"
