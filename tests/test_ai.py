"""F-079: every AI call goes through gitaway/ai.py and is logged without its content; the report; one setting switches a job's model.
A fake transport stands in for Azure: nothing here talks to the network."""

import json

import pytest

from gitaway import ai

SECRET_PROMPT = "Pregnancy safe rides and Hrishi's phone 555-0100"
SECRET_ANSWER = "Bhoomija sits out the roughest ride"


def reply(content=None, tin=120, tout=45):
    body = {"choices": [{"message": {"content": json.dumps(content if content is not None else {"answer": SECRET_ANSWER})}}], "usage": {"prompt_tokens": tin, "completion_tokens": tout}}
    return 200, json.dumps(body)


class Fake:
    def __init__(self, *answers):
        self.answers, self.sent = list(answers), []

    def __call__(self, url, headers, body, timeout):
        self.sent.append({"url": url, "headers": headers, "body": json.loads(body), "timeout": timeout})
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, BaseException):
            raise a
        return a


@pytest.fixture(autouse=True)
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-main")
    for k in ("GITAWAY_AI_DEPLOYMENT_CONVERT", "GITAWAY_AI_ENDPOINT_CONVERT", "GITAWAY_AI_KEY_CONVERT"):
        monkeypatch.delenv(k, raising=False)


def use(monkeypatch, *answers):
    fake = Fake(*(answers or [reply()]))
    monkeypatch.setattr(ai, "TRANSPORT", fake)
    return fake


SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"], "additionalProperties": False}


def call(job="convert", family="fam1", **kw):
    return ai.call_json(job, family, "Be brief.", SECRET_PROMPT, SCHEMA, **kw)


def test_not_configured_without_keys(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "")
    assert not ai.configured()
    with pytest.raises(ai.AIError) as e:
        call()
    assert "not switched on" in str(e.value)


def test_a_call_posts_to_the_v1_chat_endpoint_and_returns_the_parsed_json(monkeypatch):
    fake = use(monkeypatch)
    assert call() == {"answer": SECRET_ANSWER}
    [sent] = fake.sent
    assert sent["url"] == "https://example.openai.azure.com/openai/v1/chat/completions"
    assert sent["headers"]["api-key"] == "test-key-123"
    assert sent["body"]["model"] == "gpt-main"
    assert sent["body"]["response_format"]["type"] == "json_schema"
    assert [m["role"] for m in sent["body"]["messages"]] == ["system", "user"]


def test_endpoint_forms_are_accepted(monkeypatch):
    for given in ("https://x.openai.azure.com", "https://x.openai.azure.com/openai/v1", "https://x.openai.azure.com/openai/v1/"):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", given)
        fake = use(monkeypatch)
        call()
        assert fake.sent[0]["url"] == "https://x.openai.azure.com/openai/v1/chat/completions"


def test_json_object_is_the_fallback_when_the_schema_is_refused(monkeypatch):
    fake = use(monkeypatch, (400, '{"error": "response_format json_schema is not supported"}'), reply())
    assert call() == {"answer": SECRET_ANSWER}
    assert [s["body"]["response_format"]["type"] for s in fake.sent] == ["json_schema", "json_object"]
    [row] = ai.usage_rows()
    assert row["ok"] == 1 and row["tokens_in"] == 120


def test_the_log_has_when_job_family_deployment_tokens_time_and_result_and_no_content(monkeypatch):
    use(monkeypatch, reply(tin=200, tout=80))
    call("convert", "fam-42")
    [row] = ai.usage_rows()
    assert row["job"] == "convert" and row["family"] == "fam-42" and row["deployment"] == "gpt-main"
    assert (row["tokens_in"], row["tokens_out"], row["ok"], row["error"]) == (200, 80, 1, "")
    assert row["ms"] >= 0 and row["at"].startswith("20") and row["day"] == row["at"][:10]
    blob = json.dumps(row)
    for secret in (SECRET_PROMPT, SECRET_ANSWER, "Hrishi", "555", "test-key-123", "Be brief"):
        assert secret not in blob


def test_a_timeout_is_a_friendly_error_and_is_logged(monkeypatch):
    use(monkeypatch, TimeoutError("timed out"))
    with pytest.raises(ai.AIError) as e:
        call()
    assert "took too long" in str(e.value) and "timed out" not in str(e.value)
    [row] = ai.usage_rows()
    assert row["ok"] == 0 and row["error"] == "timeout" and row["tokens_in"] == 0


@pytest.mark.parametrize("answer,code", [((500, "boom"), "http_500"), ((429, "slow down"), "http_429"), ((200, "not json"), "bad_reply"),
                                           ((200, json.dumps({"choices": [{"message": {"content": "not json at all"}}]})), "bad_json")])
def test_failures_are_friendly_and_logged_by_kind(monkeypatch, answer, code):
    use(monkeypatch, answer)
    with pytest.raises(ai.AIError) as e:
        call()
    assert "boom" not in str(e.value) and "slow down" not in str(e.value) and "not json" not in str(e.value)
    assert ai.usage_rows()[0]["error"] == code


def test_the_convert_timeout_is_longer_than_the_others(monkeypatch):
    fake = use(monkeypatch, reply(), reply())
    call("convert")
    call("ask")
    assert fake.sent[0]["timeout"] == 60 and fake.sent[1]["timeout"] < 45


def test_one_setting_switches_the_model_for_one_job(monkeypatch):
    fake = use(monkeypatch, reply(), reply())
    monkeypatch.setenv("GITAWAY_AI_DEPLOYMENT_CONVERT", "gpt-cheap")
    call("convert")
    call("ask")
    assert [s["body"]["model"] for s in fake.sent] == ["gpt-cheap", "gpt-main"]
    assert {r["job"]: r["deployment"] for r in ai.usage_rows()} == {"convert": "gpt-cheap", "ask": "gpt-main"}


def test_a_job_can_use_another_provider_endpoint_and_key(monkeypatch):
    fake = use(monkeypatch)
    monkeypatch.setenv("GITAWAY_AI_ENDPOINT_CONVERT", "https://other.example.com/openai/v1")
    monkeypatch.setenv("GITAWAY_AI_KEY_CONVERT", "other-key")
    call("convert")
    assert fake.sent[0]["url"] == "https://other.example.com/openai/v1/chat/completions" and fake.sent[0]["headers"]["api-key"] == "other-key"


def test_the_report_counts_time_and_tokens_per_job_and_per_day(monkeypatch):
    use(monkeypatch, reply(tin=100, tout=10), reply(tin=300, tout=30), (500, "x"))
    call("convert")
    call("convert")
    with pytest.raises(ai.AIError):
        call("ask")
    r = ai.report()
    by_job = {j["job"]: j for j in r["by_job"]}
    assert by_job["convert"]["calls"] == 2 and by_job["convert"]["tokens_in"] == 400 and by_job["convert"]["tokens_out"] == 40 and by_job["convert"]["errors"] == 0
    assert by_job["ask"]["calls"] == 1 and by_job["ask"]["errors"] == 1
    assert len(r["by_day"]) == 1 and r["by_day"][0]["calls"] == 3
    text = ai.format_report(r)
    assert "convert" in text and "ask" in text and "400" in text
    assert SECRET_PROMPT not in text


def test_the_report_script_reads_the_log_from_the_data_folder(monkeypatch, capsys):
    import os
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ai_report
    use(monkeypatch, reply(tin=11, tout=7))
    call("convert")
    assert ai_report.main(["--data-dir", os.getcwd()]) == 0
    out = capsys.readouterr().out
    assert "Per job" in out and "convert" in out and "Per day" in out and SECRET_PROMPT not in out
