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
    assert r.status_code == 200 and r.json() == {"text": SECRET_WORDS, "language": "", "english": ""}
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


def test_a_piece_over_the_speech_services_limit_is_refused_plainly(ari, on):
    fake = on()
    r = post(ari, voice("mp4"), secs="45")
    assert r.status_code == 413 and "30 seconds at a time" in r.text and fake.sent == []
    assert post(ari, voice("mp4"), secs="29").status_code == 200


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


# ---- the provider is one setting; a language hint is optional ----------------------------------------------------------------------

def test_a_language_hint_is_sent_only_when_given(on):
    fake = on()
    ai.transcribe("fam1", voice("mp4"))
    assert b'name="language"' not in fake.sent[0]["body"]               # no hint: the service detects it (Hindi mixed with English as spoken)
    ai.transcribe("fam1", voice("mp4"), language="hi")
    assert b'name="language"\r\n\r\nhi\r\n' in fake.sent[1]["body"]


def test_the_route_passes_a_valid_hint_and_ignores_a_bad_one(ari, on):
    fake = on()
    assert post(ari, voice("mp4"), lang="hi").status_code == 200
    assert post(ari, voice("mp4"), lang="hi; drop table").status_code == 200
    assert b'name="language"\r\n\r\nhi\r\n' in fake.sent[0]["body"] and b'name="language"' not in fake.sent[1]["body"]


def test_another_provider_is_one_setting_and_one_small_adapter(on, monkeypatch):
    fake = on(raw=json.dumps({"transcript": "namaste, lunch at 12:30"}))
    seen = {}

    def request(audio, filename, mime, language):
        seen.update(audio=audio, language=language)
        return "https://stt.example.com/v1/listen", {"Authorization": "Token k"}, audio

    monkeypatch.setitem(ai.PROVIDERS, "other", {"configured": lambda: True, "request": request, "text": lambda reply: json.loads(reply)["transcript"]})
    monkeypatch.setenv("GITAWAY_AI_TRANSCRIBE_PROVIDER", "other")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "")          # azure's own settings are not needed for it
    assert ai.configured("transcribe")
    before = len(rows())
    assert ai.transcribe("fam1", voice("webm"), language="hi") == "namaste, lunch at 12:30"
    assert seen["language"] == "hi" and fake.sent[0]["url"] == "https://stt.example.com/v1/listen" and fake.sent[0]["headers"] == {"Authorization": "Token k"}
    assert rows()[before]["ok"] == 1                                       # logged like every call


@pytest.fixture
def sarvam(on, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "sk-sarvam-test")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "")
    monkeypatch.delenv("GITAWAY_AI_TRANSCRIBE_PROVIDER", raising=False)
    monkeypatch.delenv("SARVAM_STT_MODEL", raising=False)
    return lambda **kw: on(**kw)


def test_sarvam_is_the_default_when_its_key_is_set_and_azure_is_one_setting_away(sarvam, monkeypatch):
    assert ai.transcribe_provider() == "sarvam" and ai.configured("transcribe")
    monkeypatch.setenv("GITAWAY_AI_TRANSCRIBE_PROVIDER", "azure")
    assert ai.transcribe_provider() == "azure" and not ai.configured("transcribe")        # azure still needs its own transcribe deployment
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT", "stt-test")
    assert ai.configured("transcribe")
    monkeypatch.delenv("GITAWAY_AI_TRANSCRIBE_PROVIDER")
    monkeypatch.setenv("SARVAM_API_KEY", "")
    assert ai.transcribe_provider() == "azure"


def test_sarvam_gets_the_file_the_model_the_key_header_and_detects_the_language(sarvam):
    fake = sarvam(raw=json.dumps({"transcript": "Lunch at Universal, फिर Mario Kart", "language_code": "hi-IN"}))
    before = len(rows())
    assert ai.transcribe("fam1", voice("mp4"), "voice.m4a", "audio/mp4") == "Lunch at Universal, फिर Mario Kart"
    sent = fake.sent[0]
    assert sent["url"] == "https://api.sarvam.ai/speech-to-text" and sent["headers"]["api-subscription-key"] == "sk-sarvam-test"
    body = sent["body"]
    assert voice("mp4") in body and b'name="file"; filename="voice.m4a"' in body and b"Content-Type: audio/mp4" in body
    assert b'name="model"\r\n\r\nsaarika:v2.5\r\n' in body and b'name="language_code"\r\n\r\nunknown\r\n' in body
    row = rows()[before]
    assert row["ok"] == 1 and row["deployment"] == "saarika:v2.5" and "Mario" not in json.dumps(row) and "sk-sarvam" not in json.dumps(row)


def test_a_sarvam_language_hint_becomes_its_language_code(sarvam):
    fake = sarvam(raw=json.dumps({"transcript": "ok"}))
    ai.transcribe("fam1", voice("webm"), "voice.webm", "audio/webm", language="hi")
    assert b'name="language_code"\r\n\r\nhi-IN\r\n' in fake.sent[0]["body"]


def test_a_recording_the_service_refuses_gets_a_plain_message(sarvam):
    sarvam(status=400, raw='{"error": {"message": "unsupported format Bhoomija"}}')
    before = len(rows())
    with pytest.raises(ai.AIError) as e:
        ai.transcribe("fam1", voice("webm"), "voice.webm", "audio/webm")
    assert str(e.value) == ai.UNREADABLE and "Bhoomija" not in str(e.value) and e.value.code == "http_400"
    assert rows()[before]["error"] == "http_400"


# ---- said in Hindi (or another language): kept as said, with an English version for the planner -----------------------------------------------------------------

HINDI = "दोपहर 12:30 पर लंच"
ENGLISH = "Lunch at 12:30"


class Router:
    """Sarvam's two endpoints (shaped like the documented responses) and the chat model, behind one `ai.TRANSPORT`."""

    def __init__(self, language="hi-IN", translate_status=200, said=None):
        from tests import canvas_samples as samples
        from tests.test_speak import answer, op
        self.language, self.translate_status, self.said = language, translate_status, said
        self.chat = samples.FakeAzure(answer(op("add_plan", title="Lunch", start="12:30", end="13:30")))
        self.urls = []

    def __call__(self, url, headers, body, timeout):
        self.urls.append(url)
        if url.endswith("/speech-to-text-translate"):
            return self.translate_status, json.dumps({"request_id": "r2", "transcript": ENGLISH, "language_code": self.language, "diarized_transcript": None, "language_probability": 0.95})
        if url.endswith("/speech-to-text"):
            said = self.said or (HINDI if self.language != "en-IN" else ENGLISH)
            self.detected = b'name="language_code"\r\n\r\nunknown\r\n' in body        # no language was named: Sarvam is asked to detect it
            return 200, json.dumps({"request_id": "r1", "transcript": said, "language_code": self.language, "diarized_transcript": None, "language_probability": 0.97})
        return self.chat(url, headers, body, timeout)


@pytest.fixture
def hindi(sarvam, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-test")

    def use(**kw):
        router = Router(**kw)
        monkeypatch.setattr(ai, "TRANSPORT", router)
        return router
    return use


def test_the_translation_request_is_the_documented_one(sarvam):
    fake = sarvam(raw=json.dumps({"transcript": ENGLISH, "language_code": "hi-IN"}))
    words = ai.transcribe("fam1", voice("webm"), "voice.webm", "audio/webm", english=True)
    assert words == ENGLISH and words.language == "hi-IN"
    sent = fake.sent[0]
    assert sent["url"] == "https://api.sarvam.ai/speech-to-text-translate" and sent["headers"]["api-subscription-key"] == "sk-sarvam-test"
    assert b'name="model"\r\n\r\nsaaras:v2.5\r\n' in sent["body"] and b"language_code" not in sent["body"] and b'name="file"; filename="voice.webm"' in sent["body"]


def test_a_hindi_recording_comes_back_as_said_with_its_english(ari, hindi):
    router = hindi()
    r = post(ari, voice("mp4"))
    assert r.status_code == 200 and r.json() == {"text": HINDI, "language": "hi-IN", "english": ENGLISH}
    assert [u.rsplit("/", 1)[1] for u in router.urls] == ["speech-to-text", "speech-to-text-translate"]


TAMIL = "மதியம் 12:30 மணிக்கு மதிய உணவு"


def test_a_tamil_recording_is_detected_kept_as_said_and_reaches_the_planner_in_english(client, hindi):
    """F-104: the captain dictated Tamil. The recording goes to Sarvam (saarika:v2.5, language_code=unknown detects ta-IN), the words come back as said and the
    speech-to-text-translate step gives the English the planner reads."""
    from tests.test_calendar import book
    book(client)
    router = hindi(language="ta-IN", said=TAMIL)
    said = post(client, voice("mp4")).json()
    assert said == {"text": TAMIL, "language": "ta-IN", "english": ENGLISH}
    assert router.detected and [u.rsplit("/", 1)[1] for u in router.urls] == ["speech-to-text", "speech-to-text-translate"]
    heard = json.dumps([[said["text"], said["english"]]], ensure_ascii=False)
    r = client.post("/trip/ask/propose", data={"day": "1", "text": TAMIL, "heard": heard})
    asked = json.dumps(router.chat.sent[0], ensure_ascii=False)
    assert ENGLISH in asked and TAMIL not in asked                          # an English plan from Tamil speech
    assert 'id="ak-prop"' in r.text and "Lunch" in r.text


def test_english_speech_needs_no_translation_and_a_failed_translation_is_not_fatal(ari, hindi):
    router = hindi(language="en-IN")
    assert post(ari, voice("mp4")).json() == {"text": ENGLISH, "language": "en-IN", "english": ""}
    assert len(router.urls) == 1
    hindi(translate_status=500)
    assert post(ari, voice("mp4")).json() == {"text": HINDI, "language": "hi-IN", "english": ""}


def test_what_was_said_in_hindi_reaches_the_planner_in_english_and_the_box_keeps_hindi(client, hindi):
    from tests.test_calendar import book
    from tests.test_say import fields
    book(client)
    router = hindi()
    said = post(client, voice("mp4")).json()
    heard = json.dumps([[said["text"], said["english"]]], ensure_ascii=False)
    typed = "Please add " + HINDI
    r = client.post("/trip/ask/propose", data={"day": "1", "text": typed, "heard": heard})
    asked = json.dumps(router.chat.sent[0], ensure_ascii=False)
    assert "Please add Lunch at 12:30" in asked and HINDI not in asked      # the planner read English
    assert 'id="ak-prop"' in r.text and "Lunch" in r.text                   # an English title in the preview
    kept = fields(r.text, "ak-change-form")
    assert kept["text"] == typed and json.loads(kept["heard"]) == [[HINDI, ENGLISH]]      # "Change it": the box has what was said, and the English stays with it
    back = client.post("/trip/ask/edit", data=kept)
    assert fields(back.text, "ak-form")["text"] == typed and json.loads(fields(back.text, "ak-form")["heard"]) == [[HINDI, ENGLISH]]
    assert 'id="ak-understood"' in back.text


def test_a_changed_dictation_is_sent_as_written(client, hindi):
    from tests.test_calendar import book
    book(client)
    router = hindi()
    client.post("/trip/ask/propose", data={"day": "1", "text": "दोपहर 1 बजे लंच", "heard": json.dumps([[HINDI, ENGLISH]], ensure_ascii=False)})
    assert "दोपहर 1 बजे लंच" in json.dumps(router.chat.sent[0], ensure_ascii=False)


def test_the_planners_instructions_ask_for_english_titles():
    from gitaway import canvas, speak
    assert "in English" in speak.SYSTEM and "in English" in canvas.SYSTEM


def test_an_unknown_provider_is_off(on, monkeypatch):
    on()
    monkeypatch.setenv("GITAWAY_AI_TRANSCRIBE_PROVIDER", "nobody")
    assert not ai.configured("transcribe")
    with pytest.raises(ai.AIError) as e:
        ai.transcribe("fam1", voice("mp4"))
    assert e.value.code == "off"


# ---- review fixes ------------------------------------------------------------------------------------------------------------------

def test_the_english_swap_cannot_blow_up_memory(client):
    from gitaway import say
    from gitaway.pages import tab_ask
    big = "x" * 20000
    text = "a" * 2000 + " " + "ab " * 700
    out = tab_ask._for_the_planner(text, [["a", big]] * 20)         # one-letter passages are skipped
    assert out == text
    out = tab_ask._for_the_planner("abc " * 2000, [["abc", big]] * 20)
    assert len(out) <= say.LIMIT + 1                                  # stops as soon as it is over the limit
    out = tab_ask._for_the_planner("abc abc abc", [["abc", "XYZ"]])
    assert out == "XYZ abc abc"                                       # one swap per dictated passage


def test_a_piece_waits_for_a_busy_line_instead_of_leaving_a_gap(on):
    import threading
    import time
    on()
    ai._in_flight.add(("transcribe", "famwait"))
    threading.Timer(0.4, lambda: ai._in_flight.discard(("transcribe", "famwait"))).start()
    assert ai.transcribe("famwait", voice("mp4"), wait=3) == SECRET_WORDS
    ai._in_flight.add(("transcribe", "famwait"))
    try:
        t0 = time.monotonic()
        with pytest.raises(ai.AIError) as e:
            ai.transcribe("famwait", voice("mp4"), wait=0.3)
        assert e.value.code == "busy" and time.monotonic() - t0 >= 0.3
    finally:
        ai._in_flight.discard(("transcribe", "famwait"))


def test_a_family_is_limited_in_pieces_per_window_and_it_says_so(sarvam, monkeypatch):
    sarvam(raw=json.dumps({"transcript": "hi", "language_code": "en-IN"}))
    monkeypatch.setattr(ai, "TRANSCRIBE_CAP", (2, 600))
    ai.transcribe("famcap", voice("mp4"))
    ai.transcribe("famcap", voice("mp4"), english=True)               # a translation is not another piece
    ai.transcribe("famcap", voice("mp4"))
    with pytest.raises(ai.AIError) as e:
        ai.transcribe("famcap", voice("mp4"))
    assert e.value.code == "limit" and "resting for a few minutes" in str(e.value)
    ai.transcribe("another-family", voice("mp4"))                     # per family


def test_the_recording_limit_message_says_recordings(ari, on):
    on()
    r = post(ari, voice("mp4"), secs="400")
    assert r.status_code == 413 and r.text == "Recordings can be up to 3 minutes."
