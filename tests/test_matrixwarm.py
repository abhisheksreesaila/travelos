"""F-229: the matrix's head start. The page's script, once it runs, POSTs /plan/matrix/warm, which queues the squares the family will look at first (the
asked square, the asked start day for every place, the asked place on every day); workers search them through liteapi's gate, so a tile asked for a moment
later joins the search in flight or reads its answer. A plain GET of the page (a crawler, a link preview) starts nothing; a family over its budget queues
nothing. The tests run the queue themselves (conftest)."""
import json
import time
from datetime import date

import pytest

from gitaway import liteapi, matrixwarm, tripmatrix as tm
from gitaway.partners import places
from tests.test_liteapi import KEY, Fake, Slow
from tests.test_tripmatrix_page import MATRIX

SD = places.resolve("San Diego")
HEAD = ["sandiego|2026-12-12", "losangeles|2026-12-12", "orangecounty|2026-12-12", "losangeles+sandiego|2026-12-12", "orangecounty+sandiego|2026-12-12",
        "sandiego|2026-12-11", "sandiego|2026-12-13", "sandiego|2026-12-10", "sandiego|2026-12-14"]
TILE = "/plan/matrix/tile?" + MATRIX.split("?")[1]
WARM = "/plan/matrix/warm?" + MATRIX.split("?")[1]


def head(lanes=None, windows=None):
    lanes = lanes or tm.lanes(SD)
    windows = windows or tm.windows(date(2026, 12, 12), date(2026, 12, 16), 2, date(2026, 9, 30))
    return [tm.key(x.key, w.key) for x, w in tm.head_start(lanes, windows)]


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setenv("LITEAPI_KEY", KEY)
    fake = Fake()
    monkeypatch.setattr(liteapi, "TRANSPORT", fake)
    return fake


def test_the_head_start_is_the_asked_square_then_its_day_for_every_place_then_its_place_on_every_day():
    assert head() == HEAD
    only = tm.windows(date(2026, 12, 12), date(2026, 12, 16), 0, date(2026, 9, 30))
    assert head(windows=only) == HEAD[:5]


def test_a_plain_get_of_the_page_starts_no_searches(real, client, monkeypatch):
    """A crawler or a link preview loads the page without its script: nothing is queued and no budget is spent."""
    monkeypatch.setattr(matrixwarm, "ASYNC", True)
    for _ in range(3):
        assert client.get(MATRIX, headers={"User-Agent": "Slackbot-LinkExpanding 1.0"}).status_code == 200
    assert matrixwarm.pending() == [] and not matrixwarm._threads and real.asked == [] and liteapi.searches_today() == 0


def test_the_script_asks_for_the_head_start_and_it_is_queued_once(real, client):
    client.get(MATRIX)
    assert matrixwarm.pending() == []
    r = client.post(WARM)
    assert r.status_code == 200 and r.json()["queued"] == len(HEAD) and real.asked == [] and matrixwarm.pending() == HEAD
    assert client.post(WARM).json()["queued"] == 0 and matrixwarm.pending() == HEAD      # asked again: queued once
    assert matrixwarm.run_pending() == len(HEAD) and real.asked
    calls = len(real.asked)
    j = client.get(TILE + "&lane=sandiego&w=2026-12-12").json()
    assert j["s"] == tm.OK and len(real.asked) == calls                          # the tile reads what the head start found
    assert '"sandiego|2026-12-12"' in client.get(MATRIX).text.split('id="mx-data">')[1]      # and the page draws it


def test_nothing_is_queued_on_the_showcase_or_for_a_family_over_its_budget(real, client, monkeypatch):
    monkeypatch.setattr(liteapi, "PER_FAMILY_A_DAY", 0)
    assert client.post(WARM).json()["queued"] == 0 and matrixwarm.pending() == []
    monkeypatch.setattr(liteapi, "PER_FAMILY_A_DAY", 150)
    assert client.post(WARM.replace("home=SFO&", "home=&")).status_code == 400          # a search the page could not draw starts nothing
    monkeypatch.setenv("GITAWAY_SHOWCASE", "1")
    assert client.post(WARM).json()["queued"] == 0
    assert matrixwarm.pending() == [] and real.asked == []


def test_the_queue_is_bounded(real, monkeypatch):
    monkeypatch.setattr(matrixwarm, "_Q", matrixwarm.queue.Queue(3))
    lanes, windows = tm.lanes(SD), tm.windows(date(2026, 12, 12), date(2026, 12, 16), 2, date(2026, 9, 30))
    assert matrixwarm.warm([(x, w, i) for i, (x, w) in enumerate(tm.head_start(lanes, windows))], home="SFO") == 3 and len(matrixwarm.pending()) == 3


def test_the_page_never_waits_and_a_tile_joins_the_search_in_flight(real, client, monkeypatch):
    slow = Slow(0.6)
    monkeypatch.setattr(liteapi, "TRANSPORT", slow)
    monkeypatch.setattr(matrixwarm, "ASYNC", True)
    t0 = time.monotonic()
    assert client.get(MATRIX).status_code == 200 and client.post(WARM).status_code == 200
    assert time.monotonic() - t0 < 0.5
    time.sleep(0.1)                                                              # the asked square's searches are on their way
    j = client.get(TILE + "&lane=sandiego&w=2026-12-12").json()
    assert j["s"] == tm.OK
    deadline = time.monotonic() + 20
    while matrixwarm._Q.unfinished_tasks and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not matrixwarm._Q.unfinished_tasks and slow.most <= liteapi.AT_ONCE
    # 9 squares: 9 flight searches and 10 distinct stay searches (the two combos share San Diego's second half), each asked once, the tile's included
    assert slow.calls == 19, slow.calls


def test_the_tile_and_the_head_start_ask_with_the_squares_rank(real, client, monkeypatch):
    """The asked square is rank 0, its day and its place next (the head start's order), then the page's own order: the gate serves them in that order."""
    from gitaway import gridsource
    seen = []
    real_square = gridsource.SQUARE
    monkeypatch.setattr(gridsource, "SQUARE", lambda lane, w, rank=0, **kw: seen.append((tm.key(lane.key, w.key), rank, kw["peek"])) or real_square(lane, w, **kw))
    client.post(WARM)
    matrixwarm.run_pending()
    asked = [(k, r) for k, r, peek in seen if not peek]
    assert asked == [(k, i) for i, k in enumerate(HEAD)]
    seen.clear()
    client.get(TILE + "&lane=orangecounty%2Bsandiego&w=2026-12-14")
    s = [(k, r) for k, r, peek in seen if not peek]
    lanes, windows = tm.lanes(SD), tm.windows(date(2026, 12, 12), date(2026, 12, 16), 2, date(2026, 9, 30))
    assert s == [("orangecounty+sandiego|2026-12-14", tm.rank(lanes, windows)["orangecounty+sandiego|2026-12-14"])] and s[0][1] >= len(HEAD)
