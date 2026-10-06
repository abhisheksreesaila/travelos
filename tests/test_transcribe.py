"""F-102: the Ask mic where speech recognition is missing (iPhone Home Screen app). `ai.transcribe` (job "transcribe", logged like every call, no audio or words kept)
and POST /trip/ask/transcribe (editors only, size and type checked, never stored). A fake transport stands in for Azure; nothing reaches the network."""

import json

import pytest

from gitaway import ai, voicenotes
from tests.test_members import addr, browser, invite
from tests.test_signin import sign_in
from tests.voice_files import voice

SECRET_WORDS = "move Bhoomija's ride to 12:30"


class Speech:
    """An `ai.TRANSPORT` that answers a transcription like Azure does and remembers what it was sent."""

    def __init__(self, status=200, text=SECRET_WORDS, failure=None, raw=None):
        self.status, self.text, self.failure, self.raw, self.sent = status, text, failure, raw, []

    def __call__(self, url, headers, body, timeout):
        self.sent.append({"url": url, "headers": headers, "body": body, "timeout": timeout})
        if self.failure:
            raise self.failure
        return self.status, self.raw if self.raw is not None else json.dumps({"text": self.text})


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-main")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "stt-test")
    monkeypatch.delenv("GITAWAY_AI_DEPLOYMENT_TRANSCRIBE", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_TRANSCRIBE_API_VERSION", raising=False)

    def use(**kw):
        fake = Speech(**kw)
        monkeypatch.setattr(ai, "TRANSPORT", fake)
        return fake
    return use


def rows():
    return [r for r in ai.usage_rows() if r["job"] == "transcribe"]


# ---- ai.transcribe ---------------------------------------------------------------------------------------------------------------

def test_a_recording_goes_to_the_transcription_deployment_and_the_words_come_back(on):
    fake = on()
    assert ai.transcribe("fam1", voice("mp4"), "voice.m4a", "audio/mp4") == SECRET_WORDS
    sent = fake.sent[0]
    assert sent["url"] == "https://example.openai.azure.com/openai/deployments/stt-test/audio/transcriptions?api-version=2024-06-01"
    assert sent["headers"]["api-key"] == "test-key-123" and sent["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    body = sent["body"]
    assert voice("mp4") in body and b'name="file"; filename="voice.m4a"' in body and b'name="model"' in body and b"stt-test" in body and b'name="response_format"' in body


def test_the_endpoint_may_carry_the_v1_tail_and_the_api_version_is_a_setting(on, monkeypatch):
    fake = on()
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/openai/v1")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_API_VERSION", "2025-03-01-preview")
    ai.transcribe("fam1", voice("webm"), "voice.webm", "audio/webm")
    assert fake.sent[0]["url"] == "https://example.openai.azure.com/openai/deployments/stt-test/audio/transcriptions?api-version=2025-03-01-preview"


def test_the_job_has_its_own_deployment_setting_and_never_borrows_the_chat_one(on, monkeypatch):
    on()
    assert ai.deployment("transcribe") == "stt-test" and ai.deployment("convert") == "gpt-main"
    monkeypatch.setenv("GITAWAY_AI_DEPLOYMENT_TRANSCRIBE", "stt-other")
    assert ai.deployment("transcribe") == "stt-other"
    monkeypatch.delenv("GITAWAY_AI_DEPLOYMENT_TRANSCRIBE")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "")
    assert not ai.configured("transcribe") and ai.configured("convert")      # the chat deployment is set, the job is still off
    with pytest.raises(ai.AIError) as e:
        ai.transcribe("fam1", voice("mp4"))
    assert e.value.code == "off"


def test_the_call_is_logged_without_the_audio_or_the_words(on):
    on()
    before = len(rows())
    ai.transcribe("fam1", voice("mp4"))
    row = rows()[before]
    assert row["ok"] == 1 and row["family"] == "fam1" and row["deployment"] == "stt-test" and row["error"] == ""
    assert SECRET_WORDS not in json.dumps(row) and "Bhoomija" not in json.dumps(row)


@pytest.mark.parametrize("fake_kw, code, said", [
    ({"status": 500, "raw": "Bhoomija exploded"}, "http_500", ai.FAILED),
    ({"failure": TimeoutError("slow")}, "timeout", ai.SLOW),
    ({"failure": OSError("down")}, "network", ai.FAILED),
    ({"raw": "<html>"}, "bad_reply", ai.FAILED),
    ({"text": "  "}, "empty", ai.NOT_HEARD),
], ids=["500", "timeout", "network", "html", "empty"])
def test_a_failed_call_says_so_plainly_and_is_logged_by_kind(on, fake_kw, code, said):
    on(**fake_kw)
    before = len(rows())
    with pytest.raises(ai.AIError) as e:
        ai.transcribe("fam1", voice("mp4"))
    assert str(e.value) == said and e.value.code == code
    row = rows()[before]
    assert row["ok"] == 0 and row["error"] == code and "Bhoomija" not in json.dumps(row)


# ---- the route -------------------------------------------------------------------------------------------------------------------

def post(client, data=None, name="voice.m4a", mime="audio/mp4", **fields):
    files = {"audio": (name, data, mime)} if data is not None else None
    return client.post("/trip/ask/transcribe", files=files, data={"secs": "5", **fields}, follow_redirects=False)


@pytest.fixture
def ari(client):
    sign_in(client)
    return client


def test_a_recording_comes_back_as_text_and_nothing_is_kept(ari, on):
    fake = on()
    r = post(ari, voice("mp4"))
    assert r.status_code == 200 and r.json() == {"text": SECRET_WORDS}
    assert len(fake.sent) == 1
    assert not voicenotes.root().exists() or not any(voicenotes.root().rglob("*.*"))       # the audio was only ever in memory


def test_without_the_deployment_setting_it_says_to_use_the_keyboard_microphone(ari, on, monkeypatch):
    fake = on()
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "")
    r = post(ari, voice("mp4"))
    assert r.status_code == 503 and r.text == "Voice typing isn't set up yet — tap the microphone on your keyboard to dictate."
    assert fake.sent == []


@pytest.mark.parametrize("data, status", [(b"", 400), (b"not audio at all, just text " * 20, 415), (None, 400)], ids=["empty", "text", "no file"])
def test_empty_non_audio_and_missing_uploads_are_refused_before_the_service(ari, on, data, status):
    fake = on()
    assert post(ari, data).status_code == status
    assert fake.sent == []


def test_too_big_and_too_long_are_refused(ari, on):
    fake = on()
    big = post(ari, voice("mp4", voicenotes.MAX_BYTES + 5000))
    assert big.status_code == 413 and "too large" in big.text
    long = post(ari, voice("mp4"), secs="400")
    assert long.status_code == 413
    assert fake.sent == []


def test_a_service_failure_answers_with_a_plain_sentence(ari, on):
    on(failure=TimeoutError("slow"))
    r = post(ari, voice("mp4"))
    assert r.status_code == 503 and r.text == ai.SLOW


def test_signed_out_gets_a_401(client, on):
    on()
    assert post(client, voice("mp4")).status_code == 401


def test_a_viewer_is_refused_and_an_editor_is_not(client, on):
    fake = on()
    sign_in(client)
    ed_mail, vi_mail = addr("ed"), addr("vi")
    invite(client, ed_mail, "editor"), invite(client, vi_mail, "viewer")
    ed, vi = browser(client), browser(client)
    sign_in(ed, ed_mail), sign_in(vi, vi_mail)
    assert post(vi, voice("mp4")).status_code == 403
    assert fake.sent == []
    assert post(ed, voice("mp4")).status_code == 200
