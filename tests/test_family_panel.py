"""F-143: the Family chats in the desktop panel, through HTTP. The list of chats (the whole trip first, then each plan's and part's, with unread counts), the open chat below with its
message bar, People and invites, the day drawn with `?panel=family`, the live poll that reads what it shows, and a thread address opened in the browser. Whether the clicks, the
live updates and the layout work is checked in a real browser: tests_browser/test_family_panel.py."""
import re
from html import unescape

from gitaway import familychats as fc
from tests.test_canvas import azure  # noqa: F401 - fixtures
from tests.test_family_chats import chats, say  # noqa: F401 - fixtures
from tests.test_thread import crew  # noqa: F401 - fixture


def text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def rows(html):
    return re.findall(r'<a\b[^>]*class="cz-fam-th[^"]*"[^>]*>.*?</a>', html, re.S)


def dock(page):
    return re.search(r'<aside\b[^>]*id="cz-dock".*?</aside>', page, re.S).group(0)


def family_tab(page):
    return re.search(r'<a\b[^>]*data-tab="family"[^>]*>.*?</a>', dock(page), re.S).group(0)


def test_the_panel_lists_the_chats_with_unread_counts_and_opens_the_whole_trip_below(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "Are we bringing the scooter?")
    say(ed, "Churros after", act=stroll)
    r = crew[0].get("/trip/family/panel?thread=trip&day=1")
    assert r.status_code == 200
    found = rows(r.text)
    assert text(found[0]).startswith("Whole trip Ed: Are we bringing the scooter?") and "is-on" in found[0]
    assert text(found[1]) == "Venice Canals stroll Ed: Churros after 1 unread"
    assert 'data-pane="family"' in r.text and 'data-key="trip"' in r.text
    assert "People and invites" in text(r.text) and 'href="/family"' in r.text
    thread = r.text.split('id="ft-thread"')[1].split('id="ft-empty"')[0]
    assert "Are we bringing the scooter?" in thread and "Churros after" not in thread      # the plan's message is in its own chat
    assert 'id="ft-compose"' in r.text and 'action="/trip/family/message"' in r.text and 'name="scope" value="trip"' in r.text
    assert r.headers["x-family-unread"] == "1"                                  # the whole trip was read by opening it; the stroll's one is left


def test_a_plan_chat_opens_with_its_title_and_posts_to_the_plan(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "Churros after", act=stroll)
    html = crew[0].get(f"/trip/family/panel?thread={stroll}&day=1").text
    assert "Venice Canals stroll" in text(html) and f'data-key="{stroll}"' in html and "Churros after" in html
    assert 'action="/trip/talk/message"' in html and f'name="act" value="{stroll}"' in html and 'name="scope"' not in html
    assert f"/trip/talk/items?act={stroll}&amp;read=1" in html
    assert fc.unread_total(ari) == 1                                            # (F-177: a GET writes nothing; the script's /seen marks what the pane shows)
    assert crew[0].post("/trip/family/seen", data={"key": stroll, "upto": str(fc.newest(ari))}).status_code == 204
    assert fc.unread_total(ari) == 0


def test_a_part_chat_opens_with_its_part_named(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "Eggslut line is short", act=park, part=lunch)
    html = crew[0].get(f"/trip/family/panel?thread={park}:{lunch}&day=1").text
    assert "Lunch" in text(html) and "Eggslut line is short" in html and f'name="part" value="{lunch}"' in html


def test_a_chat_that_is_not_there_falls_back_to_the_whole_trip(crew, chats):
    for bad in ("a999", "../x", "a1:p999", "x" * 200):
        assert 'data-key="trip"' in crew[0].get(f"/trip/family/panel?thread={bad}&day=1").text, bad


def test_the_day_with_panel_family_draws_the_chats_open_and_the_tab_selected(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "hello all"), say(ed, "Churros after", act=stroll)
    page = crew[0].get(f"/trip/canvas?day=1&panel=family&thread={stroll}").text
    d = dock(page)
    assert 'data-mode="family"' in d and f'data-key="{stroll}"' in d and "Churros after" in d
    assert 'aria-selected="true"' in family_tab(page) and "is-on" in family_tab(page)
    assert text(family_tab(page)) == "Family 1 unread"                          # "hello all" is still unread; the stroll's chat was just read
    assert 'data-pane="idle"' in d                                              # Up next stays in the page (the Plan tab shows it again)
    assert 'data-family-url="/trip/canvas?day=1&amp;panel=family&amp;thread=THREAD' in d
    assert "is-ringed" not in page


def test_the_day_without_the_param_keeps_the_family_tab_with_its_count(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "hello all"), say(ed, "hi again")
    page = crew[0].get("/trip/canvas?day=1").text
    assert 'data-mode="idle"' in dock(page) and 'class="cz-dock-body cz-fam"' not in dock(page)
    assert text(family_tab(page)) == "Family 2 unread" and 'href="/trip/canvas?day=1&amp;panel=family' in family_tab(page)


def test_no_count_on_the_tab_when_everything_is_read(crew, chats):
    page = crew[0].get("/trip/canvas?day=1").text
    assert text(family_tab(page)) == "Family" and "cz-dock-un" not in dock(page)


def test_a_plan_in_the_address_wins_over_the_panel_param(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    d = dock(crew[0].get(f"/trip/canvas?day=1&panel=family&plan={park}").text)
    assert 'data-mode="plan"' in d and 'data-pane="family"' not in d


def test_the_list_asks_again_for_the_rows_and_leaves_the_open_chat_without_a_count(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "one"), say(ed, "two", act=stroll)
    r = crew[0].get(f"/trip/family/list?open={stroll}&day=1")
    assert r.status_code == 200 and r.headers["x-family-unread"] == "1"          # the whole trip's; the open chat is polled and read by its own poll
    found = rows(r.text)
    assert text(found[0]).endswith("1 unread") and "is-on" in found[1] and 'aria-current="true"' in found[1] and "unread" not in text(found[1])
    assert fc.unread_total(ari) == 2                                            # asking for the rows reads nothing


def test_the_live_poll_with_read_marks_what_it_returns_as_read(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "one"), say(ed, "two", act=stroll)
    plain = crew[0].get("/trip/family/thread?since=0&scope=trip")
    assert "one" in plain.text and "two" not in plain.text and fc.unread_total(ari) == 2
    crew[0].get("/trip/family/thread?since=0&scope=trip&read=1")
    assert fc.unread_total(ari) == 1
    crew[0].get(f"/trip/talk/items?act={stroll}&since=0&read=1")
    assert fc.unread_total(ari) == 0


def test_the_phone_poll_without_scope_still_returns_everything(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "one"), say(ed, "two", act=stroll)
    html = crew[0].get("/trip/family/thread?since=0").text
    assert "one" in html and "two" in html and "on Venice Canals stroll" in html
    assert fc.unread_total(ari) == 2                                            # (and asking reads nothing)


def test_a_message_sent_from_the_whole_trip_chat_answers_with_whole_trip_items_only(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "on the stroll", act=stroll)
    r = crew[0].post("/trip/family/message", data={"text": "everyone", "scope": "trip", "since": "0"}, headers={"X-Fragment": "1"})
    assert r.status_code == 200 and "everyone" in r.text and "on the stroll" not in r.text


def test_opening_the_thread_address_in_a_browser_goes_to_the_family_page_never_a_bare_fragment(crew):
    for headers in ({"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}, {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}):
        r = crew[0].get("/trip/family/thread", headers=headers, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/trip/family", headers
    ok = crew[0].get("/trip/family/thread?since=0", headers={"Accept": "text/html", "Sec-Fetch-Mode": "cors"})
    assert ok.status_code == 200 and "<html" not in ok.text                     # the page's own polling is still the fragment


def test_the_family_page_hands_a_laptop_on_to_the_day_and_marks_a_phone_read(crew):
    html = crew[0].get("/trip/family").text
    script = re.search(r"<script>\(function\(\)\{if\(window\.matchMedia\('\(min-width: 1020px\) and \(not \(display-mode: standalone\)\)'\)\.matches\).*?</script>", html, re.S).group(0)
    assert 'location.replace("/trip/canvas?day=' in script and "panel=family" in script and "/trip/family/seen" in script
    assert "location.replace" not in crew[0].get("/trip/family?view=photos").text         # Photos stay on their page
    at = html.index("location.replace")      # FastHTML keeps a script in the body, so it is the first thing in it: nothing is drawn, and no photo is fetched, before it
    assert html.index("<body") < at < html.index('id="main"') and at < html.index("ga-topbar")

def test_the_phones_own_polls_mark_what_they_show_as_read(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    assert 'data-poll-url="/trip/family/thread?read=1"' in crew[0].get("/trip/family").text
    say(ed, "one"), say(ed, "two", act=stroll)
    crew[0].get("/trip/family/thread?since=0&read=1")                          # the Family tab shows every chat
    assert fc.unread_total(ari) == 0
    say(ed, "three", act=stroll)
    assert f"/trip/talk/items?act={stroll}&amp;read=1" in crew[0].get(f"/trip/talk?act={stroll}").text


def test_the_day_drawn_with_the_chats_in_the_address_reads_nothing_until_the_script_starts_them(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "hello all")
    page = crew[0].get("/trip/canvas?day=1&panel=family").text
    assert fc.unread_total(ari) == 1                                            # (a screen with no panel was never shown them)
    assert "cz-dock-un" not in page                                             # the tab leaves the open chat out of its count
    assert crew[0].post("/trip/family/seen", data={"key": "trip", "upto": str(fc.newest(ari))}).status_code == 204
    assert fc.unread_total(ari) == 0


def test_seen_marks_everything_or_one_chat_read_and_is_for_every_role(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "one"), say(ed, "two", act=stroll)
    assert crew[0].post("/trip/family/seen", data={"key": stroll}).status_code == 204
    assert fc.unread_total(ari) == 1
    assert crew[0].post("/trip/family/seen", data={"key": "*"}).status_code == 204
    assert fc.unread_total(ari) == 0
    assert vi.post("/trip/family/seen", data={"key": "*"}).status_code == 204      # a viewer's own mark


def test_a_viewer_reads_and_writes_in_the_panel_chats(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "hello")
    html = vi.get("/trip/family/panel?thread=trip&day=1").text
    assert "hello" in html and 'id="ft-compose"' in html
    assert vi.post("/trip/family/message", data={"text": "from a viewer", "scope": "trip"}, headers={"X-Fragment": "1"}).status_code == 200
    assert vi.get("/trip/family/list?open=trip").status_code == 200


def test_the_phone_chat_page_marks_its_chat_read(crew, chats):
    ari, ed, vi, park, lunch, stroll = chats
    say(ed, "Churros after", act=stroll)
    assert fc.unread_total(ari) == 1
    assert crew[0].get(f"/trip/talk?act={stroll}").status_code == 200
    assert fc.unread_total(ari) == 0
