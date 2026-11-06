"""F-196 items 1 and 2: creator drafting never falls back to Azure, and background drafts never take the family's AI slots."""

import threading

import pytest

from gitaway import ai, creatordraft as cd, draftjobs as dj, importsource, safefetch
from tests.creator_import_support import Model, Web, page

KEY = "sk-ant-not-a-real-key-0000"
POST = "https://blog.example.com/santa-monica-with-kids"


@pytest.fixture
def azure(monkeypatch):
    """Production as it is on Railway today: Azure settings present, no Anthropic key."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-not-a-real-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-6.1-sol")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sent = []
    monkeypatch.setattr(ai, "TRANSPORT", lambda url, headers, body, timeout: sent.append(url) or (200, "{}"))
    return sent


# ---- item 1: no silent Azure ------------------------------------------------------------------------------------------------------------

def test_creator_import_with_azure_set_and_no_anthropic_key_is_off_and_sends_nothing(azure):
    assert ai.provider("creator-import") == "anthropic"
    assert ai.configured("creator-import") is False
    with pytest.raises(ai.AIError) as e:
        ai.call_json("creator-import", "fam", "s", "u", cd.SCHEMA)
    assert e.value.code == "off" and azure == []


def test_in_production_with_only_azure_set_drafting_says_it_is_not_switched_on(azure, client, monkeypatch):
    from tests.test_signin import sign_in
    monkeypatch.setenv("GITAWAY_SHOWCASE", "0")
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: page()}))
    sign_in(client)
    assert cd.mode() == "manual"
    r = client.post("/creators/import", data={"do": "draft", "link": POST}, follow_redirects=False)
    assert r.status_code == 422 and "Drafting from a link is not switched on yet." in r.text.replace("&#x27;", "'") and azure == []


def test_the_other_jobs_still_use_azure_when_it_is_set(azure):
    for job in ("convert", "speak", "ask", "around-you", "ocr"):
        assert ai.provider(job) == "azure" and ai.configured(job) is True, job


def test_an_explicit_provider_setting_still_wins(monkeypatch):
    monkeypatch.setenv("GITAWAY_AI_PROVIDER_CREATOR_IMPORT", "azure")
    assert ai.provider("creator-import") == "azure"


# ---- item 2: background drafts have their own slots --------------------------------------------------------------------------------------

@pytest.fixture
def model(monkeypatch):
    m = Model()
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)

    def hold_or_answer(kwargs, timeout):
        if kwargs["system"] == "hold":      # a call that stays in flight until the test lets go
            entered.release()
            gate.wait(10)
        return m(kwargs, timeout)
    gate, entered = threading.Event(), threading.Semaphore(0)
    monkeypatch.setattr(ai, "ANTHROPIC_TRANSPORT", hold_or_answer)
    m.gate, m.entered = gate, entered
    yield m
    gate.set()


@pytest.fixture
def family_ai(monkeypatch):
    """The family's AI (Azure) answering `{"ok": true}`, holding the calls whose family starts with "hold"."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    gate, entered = threading.Event(), threading.Semaphore(0)

    def answer(url, headers, body, timeout):
        if b"hold" in body:
            entered.release()
            gate.wait(10)
        return 200, '{"choices":[{"message":{"content":"{\\"ok\\": true}"}}],"usage":{"prompt_tokens":1,"completion_tokens":1}}'
    monkeypatch.setattr(ai, "TRANSPORT", answer)
    yield SimpleNamespace(gate=gate, entered=entered)
    gate.set()


from types import SimpleNamespace


def in_flight(job, n, system, entered):
    """`n` calls of `job`, each for another family, left in flight; their threads."""
    threads = [threading.Thread(target=lambda i=i: _swallow(lambda: ai.call_json(job, f"fam{i}", system, "u", {"type": "object"}))) for i in range(n)]
    for t in threads:
        t.start()
        assert entered.acquire(timeout=5)
    return threads


def _swallow(fn):
    try:
        fn()
    except ai.AIError:
        pass


def test_three_creator_drafts_in_flight_leave_every_family_slot_free(model, family_ai):
    threads = in_flight("creator-import", 3, "hold", model.entered)
    with pytest.raises(ai.AIError) as e:      # the creators' own pool is full
        ai.call_json("creator-import", "fam9", "s", "u", cd.SCHEMA)
    assert e.value.code == "busy"
    for job in ("ask", "speak", "convert"):    # the family's calls all go through
        assert ai.call_json(job, f"family-{job}", "s", "u", {"type": "object"}) == {"ok": True}
    model.gate.set()
    for t in threads:
        t.join(5)


def test_three_family_calls_in_flight_do_not_stop_a_creator_draft(model, family_ai):
    threads = in_flight("ask", 3, "hold", family_ai.entered)
    with pytest.raises(ai.AIError) as e:
        ai.call_json("convert", "family-d", "s", "u", {"type": "object"})
    assert e.value.code == "busy"
    assert ai.call_json("creator-import", "fam9", "s", "u", cd.SCHEMA)["title"] == "Three easy days in Santa Monica"
    family_ai.gate.set()
    for t in threads:
        t.join(5)


def test_plan_for_me_has_a_hook_on_the_background_pool():
    assert {"creator-import", "plan-for-me"} <= ai.BACKGROUND_JOBS


@pytest.fixture
def jobs():
    dj.stop()
    cd.clear()
    dj.clear()
    yield dj
    dj.stop()
    cd.clear()
    dj.clear()


def test_a_busy_line_puts_the_post_back_in_the_queue_and_the_creator_loses_nothing(model, jobs, monkeypatch):
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: page()}))
    jobs.enqueue("p1", "Maya", [(POST, "A title")])
    left = jobs.remaining("p1")
    threads = in_flight("creator-import", 3, "hold", model.entered)      # the creators' pool is full
    assert jobs.run_one() is False                                       # the worker found the line busy and tried nothing
    (row,) = jobs.listing("p1")
    assert (row["kind"], row["status"], row["error"]) == ("job", "drafting", "") and jobs.remaining("p1") == left
    model.gate.set()
    for t in threads:
        t.join(5)
    assert jobs.run_one() is True
    (row,) = jobs.listing("p1")
    assert (row["kind"], row["status"]) == ("draft", "ready") and jobs.remaining("p1") == left


def test_a_real_failure_still_fails_the_post(model, jobs, monkeypatch):
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: page()}))
    model.stop, model.answer = "refusal", "x"
    jobs.enqueue("p1", "Maya", [(POST, "A title")])
    assert jobs.run_one() is True
    (row,) = jobs.listing("p1")
    assert row["status"] == "failed"


def test_a_worker_that_finds_the_line_busy_waits_instead_of_spinning(model, jobs, monkeypatch):
    import time
    monkeypatch.setattr(safefetch, "TRANSPORT", Web({POST: page()}))
    jobs.enqueue("p1", "Maya", [(POST, "A title")])
    threads = in_flight("creator-import", 3, "hold", model.entered)
    tries, real = [], jobs.claim
    monkeypatch.setattr(jobs, "claim", lambda: tries.append(1) or real())
    jobs.start(poll=0.3)
    time.sleep(0.7)
    jobs.stop()
    assert 2 <= len(tries) <= 8              # a hot loop would make thousands
    model.gate.set()
    for t in threads:
        t.join(5)
