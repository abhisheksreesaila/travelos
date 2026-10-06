"""The one door to the AI service (F-079): every call to Azure OpenAI goes through `call_json`, and every call is logged.

    call_json(job, family, system, user, schema)   one chat completion that must answer as JSON matching `schema`; the parsed dict, or AIError
    configured(job=None)                           True when a key, an endpoint and a deployment are set for the job
    usage_rows(), report(), format_report(r)       the log, and the counts the captain reviews after the trip (`pixi run ai-report`)

Jobs are the reasons the app calls the model (JOBS below; docs/ai-usage.md says what each one replaces). Settings, all environment variables:

    AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT      the default for every job
    GITAWAY_AI_DEPLOYMENT_<JOB>                                                 another model for one job, e.g. GITAWAY_AI_DEPLOYMENT_CONVERT
    GITAWAY_AI_ENDPOINT_<JOB>, GITAWAY_AI_KEY_<JOB>                            another provider for one job (any OpenAI-compatible v1 endpoint)

    AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT (or GITAWAY_AI_DEPLOYMENT_TRANSCRIBE)    the speech-to-text deployment for job "transcribe" (`transcribe()` below); it never
                                                                                falls back to the chat deployment. AZURE_OPENAI_TRANSCRIBE_API_VERSION sets
                                                                                the API version (default 2024-06-01).

(<JOB> is the job's name in capitals, "-" as "_": AROUND_YOU.) Switching a job's model or provider is a setting, never a code change.

Privacy. The log is a table in the HOST database (`ga_ai_usage`): when, job, family id, deployment, tokens in and out, milliseconds, ok or the
kind of error ("timeout", "http_429", "bad_json"). It never holds a prompt, an answer, a name or the key, and nothing here prints them; a failure
is told to the person in a fixed sentence, never with the service's own text.

Tests never reach the network: `TRANSPORT` (a function (url, headers, body bytes, timeout) -> (status, text)) replaces the real HTTP call.
"""

import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from fh_saas.db_host import HostDatabase
from sqlalchemy import text

from gitaway import hostdb

# job -> (seconds before giving up, what it is for). docs/ai-usage.md lists each one with what it replaces.
JOBS = {
    "convert": (60, "turn pasted messages into park days, parts and steps"),
    "speak": (20, "turn a spoken change into a proposal"),
    "ask": (20, "answer a question about the trip, with search"),
    "around-you": (20, "recommendations near where the family is"),
    "ocr": (30, "read a boarding pass or a booking from a photo"),
    "transcribe": (45, "turn a recorded voice (Ask, where the phone has no speech recognition) into text"),
}
DEFAULT_TIMEOUT = 20
TRANSPORT = None   # tests: a function (url, headers, body, timeout) -> (status, text), used instead of the network

NOT_ON = "The assistant is not switched on for this site yet."
SLOW = "The assistant took too long. Nothing was lost; try again in a moment."
FAILED = "The assistant could not do that just now. Nothing was lost; try again in a moment."
BUSY = "The assistant is busy with another request. Try again in a moment."
MAX_AT_ONCE = 3     # calls to the service in flight at once, across every family
_global = threading.BoundedSemaphore(MAX_AT_ONCE)
_in_flight = set()   # (job, family) pairs with a call under way: one at a time per family and job
_guard = threading.Lock()


class AIError(Exception):
    """A failed call; the text is fit to show a person. `code` is what the log keeps ("timeout", "http_500", "bad_json", "off")."""

    def __init__(self, message, code="error"):
        super().__init__(message)
        self.code = code


# ---- settings -----------------------------------------------------------------------------------------------------------

def _suffix(job) -> str:
    return (job or "").upper().replace("-", "_")


def _setting(job, per_job, general) -> str:
    return (os.environ.get(f"{per_job}_{_suffix(job)}") or os.environ.get(general) or "").strip()


TRANSCRIBE_API_VERSION = "2024-06-01"


def deployment(job=None) -> str:
    if job == "transcribe":     # speech-to-text is its own deployment: the chat deployment cannot do it
        if transcribe_provider() == "sarvam":
            return _sarvam_model()      # the log's "deployment" column holds the model
        return _setting(job, "GITAWAY_AI_DEPLOYMENT", "AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT")
    return _setting(job, "GITAWAY_AI_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT")


def _key(job) -> str:
    return _setting(job, "GITAWAY_AI_KEY", "AZURE_OPENAI_API_KEY")


def _endpoint(job) -> str:
    return _setting(job, "GITAWAY_AI_ENDPOINT", "AZURE_OPENAI_ENDPOINT")


def configured(job=None) -> bool:
    if job == "transcribe":
        adapter = PROVIDERS.get(transcribe_provider())
        return bool(adapter and adapter["configured"]())
    return bool(_key(job) and _endpoint(job) and deployment(job))


def _url(job) -> str:
    base = _endpoint(job).rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if not base.endswith("/openai/v1"):
        base = base[: -len("/openai")] if base.endswith("/openai") else base
        base += "/openai/v1"
    return base + "/chat/completions"


# ---- the call -----------------------------------------------------------------------------------------------------------

def _http(url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _post(job, payload, deadline):
    left = deadline - time.monotonic()
    if left <= 0.5:
        raise TimeoutError("the call's time is used up")
    send = TRANSPORT or _http
    return send(_url(job), {"api-key": _key(job), "Content-Type": "application/json"}, json.dumps(payload).encode(), left)


def _refused_schema(status, body) -> bool:
    return status in (400, 422) and any(w in (body or "").lower() for w in ("json_schema", "response_format", "structured"))


def call_json(job, family, system, user, schema, *, name="result", timeout=None) -> dict:
    """Ask the model for JSON that matches `schema` and return it parsed. `family` is the family's id (for the log only). Raises AIError with a
    sentence fit to show; the call is logged either way. A model that refuses a strict schema is asked again for plain JSON."""
    if not configured(job):
        _log(job, family, deployment(job), 0, 0, 0, False, "off")
        raise AIError(NOT_ON, "off")
    timeout = timeout or JOBS.get(job, (DEFAULT_TIMEOUT,))[0]
    me = (job, family or "")
    with _guard:
        taken = me not in _in_flight and _global.acquire(blocking=False)
        if taken:
            _in_flight.add(me)
    if not taken:
        _log(job, family, deployment(job), 0, 0, 0, False, "busy")
        raise AIError(BUSY, "busy")
    try:
        return _call(job, family, system, user, schema, name, timeout)
    finally:
        with _guard:
            _in_flight.discard(me)
            _global.release()


def _call(job, family, system, user, schema, name, timeout) -> dict:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    start, tin, tout, code = time.monotonic(), 0, 0, "error"
    deadline = start + timeout     # one deadline for the call and the plain-JSON retry together
    try:
        for fmt in ({"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}, {"type": "json_object"}):
            payload = {"model": deployment(job), "messages": messages, "response_format": fmt}
            status, body = _post(job, payload, deadline)
            if fmt["type"] == "json_schema" and _refused_schema(status, body):
                continue
            break
        if not 200 <= status < 300:
            code = f"http_{status}"
            raise AIError(FAILED, code)
        try:
            data = json.loads(body)
            usage = data.get("usage") or {}
            tin, tout = int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            code = "bad_reply"
            raise AIError(FAILED, code)
        try:
            answer = json.loads(content)
        except (ValueError, TypeError):
            code = "bad_json"
            raise AIError(FAILED, code)
        if not isinstance(answer, dict):
            code = "bad_json"
            raise AIError(FAILED, code)
    except AIError as e:
        _log(job, family, deployment(job), tin, tout, _ms(start), False, e.code)
        raise
    except (TimeoutError, socket.timeout):
        _log(job, family, deployment(job), 0, 0, _ms(start), False, "timeout")
        raise AIError(SLOW, "timeout")
    except (OSError, urllib.error.URLError) as e:
        why = "timeout" if isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout)) else "network"
        _log(job, family, deployment(job), 0, 0, _ms(start), False, why)
        raise AIError(SLOW if why == "timeout" else FAILED, why)
    except Exception:  # noqa: BLE001 - whatever else goes wrong is logged by kind only; the person gets the fixed sentence
        _log(job, family, deployment(job), tin, tout, _ms(start), False, "error")
        raise AIError(FAILED, "error")
    _log(job, family, deployment(job), tin, tout, _ms(start), True, "")
    return answer


UNREADABLE = "The voice service could not read that recording. Tap the microphone on your keyboard to dictate, or type it."
NOT_HEARD ="Nothing could be heard in that recording. Try again, a little closer to the microphone, or type it."


def transcribe_provider() -> str:
    """Which speech-to-text provider job "transcribe" uses: GITAWAY_AI_TRANSCRIBE_PROVIDER (sarvam or azure); else sarvam when SARVAM_API_KEY is set, else azure."""
    chosen = (os.environ.get("GITAWAY_AI_TRANSCRIBE_PROVIDER") or "").strip().lower()
    return chosen or ("sarvam" if (os.environ.get("SARVAM_API_KEY") or "").strip() else "azure")


SARVAM_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"
SARVAM_MODEL = "saarika:v2.5"
SARVAM_LANGUAGES = {"hi": "hi-IN", "en": "en-IN", "bn": "bn-IN", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "od": "od-IN", "pa": "pa-IN", "ta": "ta-IN", "te": "te-IN"}


def _sarvam_model() -> str:
    return (os.environ.get("SARVAM_STT_MODEL") or "").strip() or SARVAM_MODEL


def _sarvam_configured() -> bool:
    return bool((os.environ.get("SARVAM_API_KEY") or "").strip())


def _sarvam_request(audio, filename, mime, language) -> tuple:
    """Sarvam AI speech-to-text: multipart `file`, `model`, `language_code` ("unknown" detects it, so Hindi and English mixed come back as spoken), the key in
    `api-subscription-key`; the answer is JSON with `transcript`."""
    code = "unknown" if not language else SARVAM_LANGUAGES.get(language.lower(), language)
    ctype, body = _multipart({"model": _sarvam_model(), "language_code": code}, filename, mime, audio)
    return SARVAM_URL, {"api-subscription-key": os.environ["SARVAM_API_KEY"].strip(), "Content-Type": ctype}, body


def _sarvam_text(reply) -> str:
    return str(json.loads(reply)["transcript"]).strip()


def _sarvam_language(reply) -> str:
    return str(json.loads(reply).get("language_code") or "")


def _sarvam_english_request(audio, filename, mime) -> tuple:
    """Sarvam's speech-to-English translation (the saaras model; any Indian language, or a mix, in; English text out; the language is detected):
    POST /speech-to-text-translate, multipart `file` and `model`, the same key header; the answer has `transcript` (the English) and `language_code` (the one detected)."""
    model = (os.environ.get("SARVAM_TRANSLATE_MODEL") or "").strip() or "saaras:v2.5"
    ctype, body = _multipart({"model": model}, filename, mime, audio)
    return SARVAM_TRANSLATE_URL, {"api-subscription-key": os.environ["SARVAM_API_KEY"].strip(), "Content-Type": ctype}, body


def _azure_configured() -> bool:
    job = "transcribe"
    return bool(_key(job) and _endpoint(job) and deployment(job))


def _azure_request(audio, filename, mime, language) -> tuple:
    """(url, headers, body) of an Azure OpenAI audio transcription. No `language` means the model detects it (Hindi mixed with English comes back as spoken)."""
    job = "transcribe"
    base = _endpoint(job).rstrip("/")
    for tail in ("/openai/v1", "/openai"):
        if base.endswith(tail):
            base = base[: -len(tail)]
    version = os.environ.get("AZURE_OPENAI_TRANSCRIBE_API_VERSION", "").strip() or TRANSCRIBE_API_VERSION
    url = f"{base}/openai/deployments/{deployment(job)}/audio/transcriptions?api-version={version}"
    fields = {"model": deployment(job), "response_format": "json"}
    if language:
        fields["language"] = language
    ctype, body = _multipart(fields, filename, mime, audio)
    return url, {"api-key": _key(job), "Content-Type": ctype}, body


def _json_text(reply) -> str:
    return str(json.loads(reply)["text"]).strip()


# One adapter per provider. To add one (docs/ai-usage.md): "configured" says whether its settings are all there; "request" builds (url, headers, body) for one
# recording and an optional language hint (a code like "hi", or None to auto-detect); "text" reads the words out of the response body (raise ValueError, KeyError
# or TypeError when the shape is wrong). The call, the log, the time limit and the fixed failure sentences stay here, the same for every provider.
PROVIDERS = {"azure": {"configured": _azure_configured, "request": _azure_request, "text": _json_text},
             "sarvam": {"configured": _sarvam_configured, "request": _sarvam_request, "text": _sarvam_text, "language": _sarvam_language, "english_request": _sarvam_english_request}}


def _multipart(fields, filename, mime, data) -> tuple:
    """(content type, body) of a multipart form: the text `fields` and one `file`."""
    boundary = "gitaway" + secrets.token_hex(12)
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(parts)


class Words(str):
    """What was said, as text; `.language` is the language the service detected ("hi-IN"), or "" when it did not say."""
    language = ""


def transcribe(family, audio: bytes, filename="voice.m4a", mime="audio/mp4", *, language=None, english=False, timeout=None) -> "Words":
    """Job "transcribe": turn a recording into text through the speech-to-text deployment. `family` is the family's id (for the log only). Returns the words
    (never empty); `language` is an optional hint ("hi"; None detects it, so Hindi mixed with English comes back as spoken); the provider is one setting
    (GITAWAY_AI_TRANSCRIBE_PROVIDER, default "azure"; PROVIDERS holds one small adapter each); raises AIError with a sentence fit to show. The audio and the words are never kept or logged: the log row holds the job, the deployment,
    the time and ok or the kind of error, like every call."""
    job = "transcribe"
    if not configured(job):
        _log(job, family, deployment(job), 0, 0, 0, False, "off")
        raise AIError(NOT_ON, "off")
    timeout = timeout or JOBS[job][0]
    me = (job, family or "")
    with _guard:
        taken = me not in _in_flight and _global.acquire(blocking=False)
        if taken:
            _in_flight.add(me)
    if not taken:
        _log(job, family, deployment(job), 0, 0, 0, False, "busy")
        raise AIError(BUSY, "busy")
    start, code = time.monotonic(), "error"
    try:
        try:
            adapter = PROVIDERS[transcribe_provider()]
            if english and "english_request" not in adapter:
                code = "no_translate"
                raise AIError(FAILED, code)
            url, headers, body = adapter["english_request"](audio, filename, mime) if english else adapter["request"](audio, filename, mime, language or None)
            send = TRANSPORT or _http
            status, reply = send(url, headers, body, timeout)
            if not 200 <= status < 300:
                code = f"http_{status}"
                raise AIError(UNREADABLE if status in (400, 415, 422) else FAILED, code)
            try:
                words = Words(adapter["text"](reply))
                words.language = (adapter["language"](reply) if "language" in adapter else "") or ""
            except (ValueError, KeyError, TypeError):
                code = "bad_reply"
                raise AIError(FAILED, code)
            if not words:
                code = "empty"
                raise AIError(NOT_HEARD, code)
        except AIError as e:
            _log(job, family, deployment(job), 0, 0, _ms(start), False, e.code)
            raise
        except (TimeoutError, socket.timeout):
            _log(job, family, deployment(job), 0, 0, _ms(start), False, "timeout")
            raise AIError(SLOW, "timeout")
        except (OSError, urllib.error.URLError) as e:
            why = "timeout" if isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout)) else "network"
            _log(job, family, deployment(job), 0, 0, _ms(start), False, why)
            raise AIError(SLOW if why == "timeout" else FAILED, why)
        except Exception:  # noqa: BLE001 - logged by kind only
            _log(job, family, deployment(job), 0, 0, _ms(start), False, "error")
            raise AIError(FAILED, "error")
    finally:
        with _guard:
            _in_flight.discard(me)
            _global.release()
    _log(job, family, deployment(job), 0, 0, _ms(start), True, "")
    return words


def _ms(start) -> int:
    return int((time.monotonic() - start) * 1000)


# ---- the log (host database) --------------------------------------------------------------------------------------------

_READY = False


def _conn():
    """The host database's connection with the usage table made. Call only inside `hostdb.locked()`."""
    global _READY
    conn = HostDatabase.from_env().db.conn
    conn.rollback()
    if not _READY:
        conn.execute(text("""CREATE TABLE IF NOT EXISTS ga_ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, day TEXT NOT NULL, job TEXT NOT NULL, family TEXT NOT NULL DEFAULT '',
            deployment TEXT NOT NULL DEFAULT '', tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0,
            ms INTEGER NOT NULL DEFAULT 0, ok INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '')"""))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ga_ai_usage_job ON ga_ai_usage (job, day)"))
        conn.commit()
        _READY = True
    return conn


def forget_table():
    """Make the next use re-check that the usage table exists (tests that swap the host database)."""
    global _READY
    with hostdb.locked():
        _READY = False


def _log(job, family, dep, tin, tout, ms, ok, error):
    """Write one usage row. Never raises: a log that cannot be written must not break the call it describes."""
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with hostdb.locked():
            conn = _conn()
            conn.execute(text("INSERT INTO ga_ai_usage (at, day, job, family, deployment, tokens_in, tokens_out, ms, ok, error) VALUES (:at, :day, :job, :family, :dep, :ti, :to, :ms, :ok, :err)"),
                         {"at": at, "day": at[:10], "job": job, "family": family or "", "dep": dep, "ti": int(tin), "to": int(tout), "ms": int(ms), "ok": 1 if ok else 0, "err": error or ""})
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


def usage_rows() -> list:
    """Every logged call, oldest first."""
    with hostdb.locked():
        conn = _conn()
        return [dict(r) for r in conn.execute(text("SELECT * FROM ga_ai_usage ORDER BY id")).mappings()]


# ---- the report ---------------------------------------------------------------------------------------------------------

def _sum(rows, key) -> list:
    out = {}
    for r in rows:
        g = out.setdefault(r[key], {key: r[key], "calls": 0, "errors": 0, "ms": 0, "tokens_in": 0, "tokens_out": 0})
        g["calls"] += 1
        g["errors"] += 0 if r["ok"] else 1
        g["ms"] += r["ms"]
        g["tokens_in"] += r["tokens_in"]
        g["tokens_out"] += r["tokens_out"]
    for g in out.values():
        g["avg_ms"] = g["ms"] // g["calls"]
    return sorted(out.values(), key=lambda g: g[key])


def report(rows=None) -> dict:
    """Counts, time and tokens per job and per day, from `rows` (or the log)."""
    rows = usage_rows() if rows is None else rows
    return {"by_job": _sum(rows, "job"), "by_day": _sum(rows, "day"), "by_day_job": _sum([{**r, "k": f"{r['day']} {r['job']}"} for r in rows], "k")}


def format_report(r) -> str:
    def table(title, key, label, items):
        lines = [title, f"  {label:<22}{'calls':>7}{'errors':>8}{'avg s':>8}{'total s':>9}{'tokens in':>11}{'tokens out':>12}"]
        for g in items:
            lines.append(f"  {g[key]:<22}{g['calls']:>7}{g['errors']:>8}{g['avg_ms'] / 1000:>8.1f}{g['ms'] / 1000:>9.1f}{g['tokens_in']:>11}{g['tokens_out']:>12}")
        return "\n".join(lines)
    if not r["by_job"]:
        return "No AI calls logged yet."
    return "\n\n".join([table("Per job", "job", "job", r["by_job"]), table("Per day", "day", "day", r["by_day"]), table("Per day and job", "k", "day and job", r["by_day_job"])])
