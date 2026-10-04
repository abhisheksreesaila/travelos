# What the AI does (F-079)

Azure OpenAI is a stopgap for the October 2026 trip. Every call goes through `gitaway/ai.py` and is logged, so after a week we can see which jobs it really did and decide, job by job, what to keep, swap for a cheaper model or a small classifier, or drop.

## The jobs

| Job | What it does | What it replaces, and why the model | Ticket |
|---|---|---|---|
| `convert` | Turns pasted (or dictated) family messages into park days, parts and steps, with notes, set-aside items and lists. | Typing the plan in by hand, step by step. The messages are free text with initials, repeats and notes buried mid-line; a rule-based parser would fail on the next message that is worded differently. Candidate to keep: it is the one job nothing simpler can do. | F-080 |
| `speak` | Turns a spoken change ("move Fast & Furious to after lunch") into a proposal the person applies. | Dragging and tapping through the edit screens. Candidate to swap for a small intent classifier plus the existing editors if the phrases stay few. | later |
| `ask` | Answers a question about the trip, with search, as a proposal. | Searching the web and the plan by hand. Candidate to drop if nobody uses it. | later |
| `around-you` | Recommendations near where the family is (lunch, a quiet break). | A map search. Candidate to replace with Nominatim plus a fixed list of categories. | later |
| `ocr` | Reads a boarding pass or a booking from a photo. | Typing the numbers in. Candidate to replace with a dedicated OCR/vision service or on-device reading. | later |

Only `convert` exists today; the others are named so the log and the report already have a place for them.

## What is logged

One row per call in the host database table `ga_ai_usage`: when, day, job, the family's id, the deployment used, tokens in, tokens out, milliseconds, ok (1/0) and, if it failed, the kind of error (`timeout`, `http_429`, `bad_json`, `off`). It never holds the prompt, the answer, a name, a place or the key. Nothing in the app prints them either; a failure is shown as a fixed sentence.

## The report

```
pixi run ai-report                 # counts, time and tokens per job, per day, and per day and job
pixi run ai-report --since 2026-10-04
pixi run ai-report --data-dir path/to/copy-of-the-data-folder
```

Read only; it opens the host database file and nothing else.

## Switching the model or provider for one job

Settings only (environment variables), no code change:

| Variable | Effect |
|---|---|
| `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` | The default for every job. |
| `GITAWAY_AI_DEPLOYMENT_<JOB>` | A different deployment for one job, e.g. `GITAWAY_AI_DEPLOYMENT_CONVERT=gpt-4o-mini`. |
| `GITAWAY_AI_ENDPOINT_<JOB>`, `GITAWAY_AI_KEY_<JOB>` | A different provider for one job: any OpenAI-compatible `/openai/v1` endpoint. |

`<JOB>` is the job name in capitals with `-` as `_` (`AROUND_YOU`).

## Tests

The suite never calls the network: `ai.TRANSPORT` is replaced by a fake, and the conftests pin the `AZURE_*` keys to empty. `python -m gitaway.ai_smoke` is the one real call, run by hand (it prints counts and the time taken only).
