"""The one door to the AI service (F-079): every call to Azure OpenAI goes through `call_json`, and every call is logged.

    call_json(job, family, system, user, schema)   one chat completion that must answer as JSON matching `schema`; the parsed dict, or AIError
    configured(job=None)                           True when a key, an endpoint and a deployment are set for the job
    usage_rows(), report(), format_report(r)       the log, and the counts the captain reviews after the trip (`pixi run ai-report`)

Jobs are the reasons the app calls the model (JOBS below; docs/ai-usage.md says what each one replaces). Settings, all environment variables:

    AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT      the default for every job
    GITAWAY_AI_DEPLOYMENT_<JOB>                                                 another model for one job, e.g. GITAWAY_AI_DEPLOYMENT_CONVERT
    GITAWAY_AI_ENDPOINT_<JOB>, GITAWAY_AI_KEY_<JOB>                            another provider for one job (any OpenAI-compatible v1 endpoint)

(<JOB> is the job's name in capitals, "-" as "_": AROUND_YOU.) Switching a job's model or provider is a setting, never a code change.

Privacy. The log is a table in the HOST database (`ga_ai_usage`): when, job, family id, deployment, tokens in and out, milliseconds, ok or the
kind of error ("timeout", "http_429", "bad_json"). It never holds a prompt, an answer, a name or the key, and nothing here prints them; a failure
is told to the person in a fixed sentence, never with the service's own text.

Tests never reach the network: `TRANSPORT` (a function (url, headers, body bytes, timeout) -> (status, text)) replaces the real HTTP call.
"""

import json
import os
import socket
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
}
DEFAULT_TIMEOUT = 20
TRANSPORT = None   # tests: a function (url, headers, body, timeout) -> (status, text), used instead of the network

NOT_ON = "The assistant is not switched on for this site yet."
SLOW = "The assistant took too long. Nothing was lost; try again in a moment."
FAILED = "The assistant could not do that just now. Nothing was lost; try again in a moment."


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


def deployment(job=None) -> str:
    return _setting(job, "GITAWAY_AI_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT")


def _key(job) -> str:
    return _setting(job, "GITAWAY_AI_KEY", "AZURE_OPENAI_API_KEY")


def _endpoint(job) -> str:
    return _setting(job, "GITAWAY_AI_ENDPOINT", "AZURE_OPENAI_ENDPOINT")


def configured(job=None) -> bool:
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


def _post(job, payload, timeout):
    send = TRANSPORT or _http
    return send(_url(job), {"api-key": _key(job), "Content-Type": "application/json"}, json.dumps(payload).encode(), timeout)


def _refused_schema(status, body) -> bool:
    return status in (400, 422) and any(w in (body or "").lower() for w in ("json_schema", "response_format", "structured"))


def call_json(job, family, system, user, schema, *, name="result", timeout=None) -> dict:
    """Ask the model for JSON that matches `schema` and return it parsed. `family` is the family's id (for the log only). Raises AIError with a
    sentence fit to show; the call is logged either way. A model that refuses a strict schema is asked again for plain JSON."""
    if not configured(job):
        _log(job, family, deployment(job), 0, 0, 0, False, "off")
        raise AIError(NOT_ON, "off")
    timeout = timeout or JOBS.get(job, (DEFAULT_TIMEOUT,))[0]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    start, tin, tout, code = time.monotonic(), 0, 0, "error"
    try:
        for fmt in ({"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}, {"type": "json_object"}):
            payload = {"model": deployment(job), "messages": messages, "response_format": fmt}
            status, body = _post(job, payload, timeout)
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
    _log(job, family, deployment(job), tin, tout, _ms(start), True, "")
    return answer


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
