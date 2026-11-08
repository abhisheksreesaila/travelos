"""F-183: the probe script and the real Anthropic SDK path, against a local fake of the Messages API (ANTHROPIC_BASE_URL), in a subprocess with its own throwaway data folder.
This is the one test that runs the real `anthropic` client: it proves the request GitAway really sends (model, structured output, effort, no prefill, the key header) and that a real
SDK response (usage, stop reason, content blocks) is read correctly. Nothing leaves this machine."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests.creator_import_support import ANSWER

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "probe_creator_import.py"
TEXT = "Day 1 we went to Santa Monica Pier at 10:00 AM and then the Third Street Promenade. Day 2 Venice Canals at 9am. Tips: park at the pier lot before 9, bring layers."


@pytest.fixture
def api():
    """A fake Messages API: records each request; `reply` is (status, body dict) answered next."""
    seen, reply = [], {"status": 200, "body": None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers.get("content-length") or 0)
            seen.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(self.rfile.read(size))})
            body = json.dumps(reply["body"]).encode()
            self.send_response(reply["status"])
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    reply["body"] = message(json.dumps(ANSWER))
    yield server, seen, reply
    server.shutdown()
    server.server_close()


def message(text, stop="end_turn", tin=6000, tout=1500):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-5-5", "stop_reason": stop, "stop_sequence": None,
            "content": [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "text", "text": text}], "usage": {"input_tokens": tin, "output_tokens": tout}}


def probe(server, *args, key="sk-ant-fake-key-123"):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GITAWAY_", "ANTHROPIC_"))}
    env.update({"ANTHROPIC_API_KEY": key, "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}"})
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=120, cwd=str(SCRIPT.parent.parent))


def test_the_probe_prints_the_draft_the_tokens_and_the_cost_without_the_key(api):
    server, seen, _ = api
    r = probe(server, "--text", TEXT)
    assert r.returncode == 0, r.stdout + r.stderr
    start = r.stdout.index("{")
    draft = json.loads(r.stdout[start:r.stdout.rindex("}") + 1])
    assert draft["title"] == "Three easy days in Santa Monica" and draft["place"] == "la"      # "Santa Monica, California" is la
    assert [s["name"] for d in draft["days"] for s in d["stops"]] == ["Santa Monica Pier", "Third Street Promenade", "Venice Canals", "Unnamed stop"]
    assert "model claude-haiku-5-5 · 6,000 tokens in · 1,500 tokens out" in r.stdout and "about $0.00135 for this draft" in r.stdout
    assert "sk-ant-fake-key-123" not in r.stdout + r.stderr


def test_the_real_sdk_sends_the_request_the_app_means_to(api):
    server, seen, _ = api
    probe(server, "--text", TEXT)
    (req,) = seen
    body = req["body"]
    assert req["path"] == "/v1/messages" and "sk-ant-fake-key-123" in " ".join(req["headers"].values())      # the SDK sends the key in the header it chooses (Authorization here)
    assert req["headers"]["anthropic-version"]
    assert body["model"] == "claude-haiku-5-5" and body["max_tokens"] == 8000
    assert body["output_config"]["effort"] == "low" and body["output_config"]["format"]["type"] == "json_schema" and body["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert [m["role"] for m in body["messages"]] == ["user"] and body["messages"][0]["content"].startswith('<post kind="text">\n' + TEXT[:40])      # no assistant turn: no prefill
    assert "untrusted data" in body["system"]
    assert not {"temperature", "top_p", "top_k", "thinking", "tools", "stream"} & set(body)


def test_a_refusal_through_the_real_sdk_is_read_before_the_content_and_exits_3(api):
    server, seen, reply = api
    reply["body"] = message('{"title": "half', stop="refusal", tin=900, tout=0)
    r = probe(server, "--text", TEXT)
    assert r.returncode == 3
    assert "The model did not give a draft: The assistant could not draft from that. Try pasting the text of your post instead. (logged as refusal, 900 tokens in, 0 out)" in r.stdout


def test_an_api_error_is_a_fixed_sentence_never_the_services_words(api):
    server, seen, reply = api
    reply.update(status=401, body={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key SECRET-DETAIL"}})
    r = probe(server, "--text", TEXT)
    assert r.returncode == 3 and "logged as http_401" in r.stdout and "SECRET-DETAIL" not in r.stdout + r.stderr


def test_without_a_key_it_says_so_and_exits_1(api):
    server, _, _ = api
    r = probe(server, "--text", TEXT, key="")
    assert r.returncode == 1 and r.stdout.strip() == "ANTHROPIC_API_KEY must be set (it is never printed)."


def test_instagram_without_a_caption_exits_2_before_any_call(api):
    server, seen, _ = api
    r = probe(server, "https://www.instagram.com/reel/Cxyz123/")
    assert r.returncode == 2 and "Instagram does not let GitAway read posts" in r.stdout and seen == []
