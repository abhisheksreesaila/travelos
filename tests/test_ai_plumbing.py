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
