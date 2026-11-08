"""F-194 (5): before GitAway reads a post for a draft (the captain's pre-draft, a creator's paste, a queued blog post) it reads the site's robots.txt. A site that asks Anthropic's or OpenAI's
crawlers (anthropic-ai, ClaudeBot, Claude-Web, GPTBot), GitAwayBot, or every robot to stay away from that page is not read: the person is told to paste the text instead. A pre-draft's
fetch does not say "its author asked us to read it", because the author did not."""

from html import unescape

import pytest

from gitaway import ai, importsource, robots, safefetch
from tests.creator_import_support import Model, Web, page
from tests.test_creator_claim import browser, claim_link, draft, rows, setup  # noqa: F401 - fixtures and helpers of the claim tests
from tests.test_signin import sign_in

POST = "https://blog.example.com/santa-monica-with-kids"
ROBOTS = "https://blog.example.com/robots.txt"
TEXT = {"content-type": "text/plain; charset=utf-8"}
ASKS_NOT = "This site's robots.txt asks AI tools not to read this page, so GitAway did not draft from it. Paste the text of the post instead."
CANNOT_CHECK = "GitAway could not check this site's robots.txt just now, so it did not read the page. Try again in a minute, or paste the text of the post instead."


def serve(monkeypatch, body, status=200, headers=None):
    w = Web({ROBOTS: (status, headers or TEXT, body.encode() if isinstance(body, str) else body), POST: page()})
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    return w


@pytest.mark.parametrize("rules, ok", [
    ("", True),
    ("User-agent: *\nDisallow: /wp-admin/\n", True),
    ("User-agent: *\nDisallow:\n", True),
    ("User-agent: Googlebot\nDisallow: /\n", True),                                     # only Google is turned away
    ("User-agent: ClaudeBot\nDisallow: /\n", False),
    ("User-agent: anthropic-ai\nDisallow: /\n", False),
    ("User-agent: Claude-Web\nDisallow: /\n", False),
    ("User-agent: GPTBot\nDisallow: /\n", False),
    ("User-agent: GitAwayBot\nDisallow: /\n", False),                                   # our own name too
    ("User-agent: *\nDisallow: /\n", False),                                            # every robot
    ("user-agent: claudebot\ndisallow: /\n", False),                                    # any case
    ("User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n", False),                # a group with two names
    ("# no AI please\nUser-agent: ClaudeBot # the Anthropic crawler\nDisallow: /santa-monica\n", False),
    ("User-agent: ClaudeBot\nDisallow: /*\n", False),                                   # a wildcard
    ("User-agent: ClaudeBot\nDisallow: /*-with-kids$\n", False),                        # a wildcard and an end anchor
    ("User-agent: ClaudeBot\nDisallow: /*-with-adults$\n", True),
    ("User-agent: ClaudeBot\nDisallow: /other/\n", True),                               # a different path
    ("User-agent: *\nDisallow: /\nAllow: /santa-monica\n", True),                       # the longer rule wins
    ("User-agent: *\nDisallow: /\nUser-agent: ClaudeBot\nAllow: /\n", False),           # GPTBot, anthropic-ai... still fall under "*"
])
def test_a_page_is_read_only_when_no_group_that_names_us_turns_it_away(monkeypatch, rules, ok):
    serve(monkeypatch, rules)
    assert robots.check(POST) == ("" if ok else ASKS_NOT)


def test_a_site_with_no_robots_txt_may_be_read_and_so_may_one_that_refuses_robots_to_look(monkeypatch):
    for status in (404, 410, 401, 403, 429):
        serve(monkeypatch, "User-agent: *\nDisallow: /\n", status)
        assert robots.check(POST) == "", status


def test_a_robots_txt_that_is_not_text_is_no_robots_txt(monkeypatch):
    serve(monkeypatch, '{"error": "nope"}', headers={"content-type": "application/json"})
    assert robots.check(POST) == ""


def test_a_site_whose_robots_txt_cannot_be_read_right_now_is_not_read(monkeypatch):
    serve(monkeypatch, "oops", 503)
    assert robots.check(POST) == CANNOT_CHECK

    def down(url, ip, timeout, kind):
        raise TimeoutError("slow")
    monkeypatch.setattr(safefetch, "TRANSPORT", down)
    assert robots.check(POST) == CANNOT_CHECK


def test_the_file_asked_for_is_the_sites_own_at_its_root_and_one_request_is_made(monkeypatch):
    w = serve(monkeypatch, "")
    robots.check("https://blog.example.com/a/b/c?x=1")
    assert w.robots == [ROBOTS] and w.calls == []


# ---- through the paste page and the captain's page --------------------------------------------------------------------------------

def test_a_creators_paste_of_a_site_that_turns_ai_away_is_not_drafted_and_says_to_paste_the_text(client, monkeypatch):
    model = Model()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", model)
    w = serve(monkeypatch, "User-agent: ClaudeBot\nDisallow: /\n")
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)
    assert r.status_code == 422 and ASKS_NOT in unescape(r.text)
    assert w.calls == [] and model.requests == []                               # the post was never fetched, the model never asked


def test_pasting_the_text_of_that_post_still_works(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", Model())
    w = serve(monkeypatch, "User-agent: ClaudeBot\nDisallow: /\n")
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "text": "We spent three days in Santa Monica. " * 8}, follow_redirects=False)
    assert r.status_code == 303 and w.robots == [] and w.calls == []


def test_a_link_and_the_text_on_a_site_that_turns_ai_away_drafts_from_the_text_and_keeps_the_link(client, monkeypatch):
    model = Model()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-0000")
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", model)
    w = serve(monkeypatch, "User-agent: ClaudeBot\nDisallow: /\n")
    sign_in(client)
    r = client.post("/creators/import", data={"do": "draft", "link": POST, "text": "We spent three days in Santa Monica. " * 8}, follow_redirects=False)
    assert r.status_code == 303 and w.calls == []                               # the page itself was never fetched
    assert len(model.requests) == 1 and "We spent three days in Santa Monica." in str(model.requests[0])
    m = importsource.gather(POST, "We spent three days in Santa Monica. " * 8)
    assert (m.kind, m.url, m.by) == ("blog", POST, "") and m.text.startswith("We spent three days")


def test_a_link_and_a_few_words_on_such_a_site_still_says_to_paste_the_post(monkeypatch):
    serve(monkeypatch, "User-agent: ClaudeBot\nDisallow: /\n")
    with pytest.raises(importsource.SourceError) as e:
        importsource.gather(POST, "Great trip!")
    assert str(e.value) == ASKS_NOT


def test_a_link_that_redirects_to_another_host_is_checked_against_that_hosts_robots_txt(monkeypatch):
    other = "https://elsewhere.example.org/santa-monica-with-kids"
    w = Web({ROBOTS: (404, {"content-type": "text/html"}, b"no"), POST: (301, {"location": other}, b""), other: page(),
             "https://elsewhere.example.org/robots.txt": (200, TEXT, b"User-agent: GPTBot\nDisallow: /\n")})
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    with pytest.raises(importsource.Refused) as e:
        importsource.gather(POST, "")
    assert str(e.value) == ASKS_NOT


def test_a_redirect_to_a_host_that_allows_us_is_read(monkeypatch):
    other = "https://elsewhere.example.org/santa-monica-with-kids"
    w = Web({ROBOTS: (404, {"content-type": "text/html"}, b"no"), POST: (301, {"location": other}, b""), other: page()})
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    assert importsource.gather(POST, "").url == other


def test_the_captains_pre_draft_of_such_a_post_makes_no_draft_and_says_why(client, setup, monkeypatch):
    serve(monkeypatch, "User-agent: GPTBot\nDisallow: /\n")
    c = browser("cap@example.com")
    r = c.post("/admin/draft", data={"link": POST, "name": "Maya Chen"})
    assert r.status_code == 200 and ASKS_NOT in unescape(r.text)
    assert rows() == [] and setup.requests == []


def test_a_site_that_allows_us_is_drafted_as_before(client, setup, monkeypatch):
    serve(monkeypatch, "User-agent: *\nDisallow: /wp-admin/\n")
    assert claim_link(draft(browser("cap@example.com")).text).startswith("/claim/") and len(rows()) == 1


def test_the_robots_check_reads_the_post_a_video_is_watched_on_too(monkeypatch):
    w = Web({"https://www.youtube.com/robots.txt": (200, TEXT, b"User-agent: *\nDisallow: /watch\n")})
    monkeypatch.setattr(safefetch, "TRANSPORT", w)
    with pytest.raises(importsource.SourceError) as e:
        importsource.gather("https://youtu.be/abcdefghijk", "")
    assert str(e.value) == ASKS_NOT and w.calls == []


# ---- who is asking ---------------------------------------------------------------------------------------------------------------

class Net:
    """The real fetch path with a recording stand-in for the socket (`safefetch._http`): each request's address and User-Agent, and a page for it."""

    def __init__(self):
        self.seen = []

    def __call__(self, url, ip, timeout, kind, ua=None):
        self.seen.append((url, ua))
        if url.endswith("/robots.txt"):
            return 404, {"content-type": "text/html"}, b""
        return page()


@pytest.fixture
def net(monkeypatch):
    n = Net()
    monkeypatch.setattr(safefetch, "TRANSPORT", None)
    monkeypatch.setattr(safefetch, "_http", n)
    return n


def test_a_creators_own_paste_says_the_author_asked(net):
    importsource.gather(POST, "")
    assert net.seen == [(ROBOTS, safefetch.USER_AGENT), (POST, safefetch.USER_AGENT)]
    assert "its author asked us to read" in safefetch.USER_AGENT


def test_a_pre_draft_for_the_captain_does_not_claim_the_author_asked(net):
    importsource.gather(POST, "", asked=False)
    assert net.seen == [(ROBOTS, safefetch.USER_AGENT_UNASKED), (POST, safefetch.USER_AGENT_UNASKED)]
    assert safefetch.USER_AGENT_UNASKED == "GitAwayBot/1.0 (+https://gitaway.me; drafts a public post for its author to look at; the author has not asked us to)"


def test_the_captains_draft_goes_out_with_the_honest_agent(client, setup, net):
    draft(browser("cap@example.com"))
    assert {ua for _url, ua in net.seen} == {safefetch.USER_AGENT_UNASKED} and len(net.seen) == 2


def test_the_real_transport_sends_the_agent_it_is_given(monkeypatch):
    import io
    import socket
    sent = []

    class Sock:
        buf = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 5\r\n\r\nhello"

        def sendall(self, data):
            sent.append(data)

        def makefile(self, mode="rb", buffering=None):
            return io.BytesIO(self.buf)

        def close(self):
            pass

        def settimeout(self, t):
            pass

    monkeypatch.setattr(socket, "create_connection", lambda addr, timeout=None, **kw: Sock())
    safefetch._http("http://blog.example.com/p", "93.184.216.34", 5, "html", ua=safefetch.USER_AGENT_UNASKED)
    assert f"User-Agent: {safefetch.USER_AGENT_UNASKED}\r\n" in b"".join(sent).decode()


# ---- a hostile robots.txt cannot freeze the server (F-194 audit) ----------------------------------------------------------------------

def test_a_rule_made_to_make_a_regex_backtrack_is_answered_at_once(monkeypatch):
    import time
    serve(monkeypatch, "User-agent: *\nDisallow: /" + "*a" * 50 + "b\n")
    started = time.perf_counter()
    assert robots.check(POST.replace("/santa-monica-with-kids", "/" + "a" * 2000)) == ""
    assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize("pattern, path, hit", [
    ("/a*b", "/axxb", True), ("/a*b", "/axxbc", True), ("/a*b$", "/axxbc", False), ("/a*b$", "/axxb", True), ("/*.pdf$", "/x/y.pdf", True), ("/*.pdf$", "/x/y.pdf?v=1", False),
    ("/a**b", "/ab", True), ("/*", "/anything", True), ("/a$", "/a", True), ("/a$", "/ab", False), ("/a/", "/a", False), ("/*a*b*c", "/xaxbxcx", True), ("/*a*b*c$", "/xaxcxb", False),
    ("/a*a$", "/a", False),         # the last "a" must come after the first
    ("/x$y", "/x$y", True),         # a "$" that is not last is just a character
])
def test_a_rule_matches_the_way_rfc_9309_says(pattern, path, hit):
    assert robots._matches(pattern, path) is hit


def test_a_file_with_more_rules_or_longer_rules_than_we_read_is_not_trusted(monkeypatch):
    serve(monkeypatch, "User-agent: *\n" + "Disallow: /x\n" * (robots.MAX_RULES + 1))
    assert robots.check(POST) == CANNOT_CHECK
    serve(monkeypatch, "User-agent: *\nDisallow: /" + "a" * robots.MAX_RULE + "\n")
    assert robots.check(POST) == CANNOT_CHECK
    serve(monkeypatch, "User-agent: *\n" + "Disallow: /x\n" * robots.MAX_RULES)
    assert robots.check(POST) == ""


def test_two_thousand_long_rules_that_cannot_match_are_answered_at_once(monkeypatch):
    import time
    n = robots.MAX_RULES
    rules = "".join(f"Disallow: /*{'a' * 900}b{'a' * (i % 90)}\n" for i in range(n))
    serve(monkeypatch, "User-agent: *\n" + rules)
    started = time.perf_counter()
    result = robots.check("https://blog.example.com/" + "a" * 2020)
    assert time.perf_counter() - started < 0.5
    assert result == CANNOT_CHECK                   # 1.8 million characters of rules: more than we read
    rules = "".join(f"Disallow: /*{'a' * 900}b{'a' * (i % 90)}\n" for i in range(robots.MAX_RULE_CHARS // 1000))      # as many as we do read
    serve(monkeypatch, "User-agent: *\n" + rules)
    started = time.perf_counter()
    assert robots.check("https://blog.example.com/" + "a" * 2020) == ""
    assert time.perf_counter() - started < 0.5


def test_a_file_whose_rules_add_up_to_more_characters_than_we_read_is_not_trusted(monkeypatch):
    rule = "Disallow: /" + "a" * (robots.MAX_RULE - 20) + "\n"
    count = robots.MAX_RULE_CHARS // len(rule) + 2
    assert count < robots.MAX_RULES
    serve(monkeypatch, "User-agent: *\n" + rule * count)
    assert robots.check(POST) == CANNOT_CHECK
    serve(monkeypatch, "User-agent: *\n" + rule * (count - 4))
    assert robots.check(POST) == ""
