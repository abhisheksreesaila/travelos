# What the AI does (F-079)

Azure OpenAI is a stopgap for the October 2026 trip. Every call goes through `gitaway/ai.py` and is logged, so after a week we can see which jobs it really did and decide, job by job, what to keep, swap for a cheaper model or a small classifier, or drop.

## The jobs

| Job | What it does | What it replaces, and why the model | Ticket |
|---|---|---|---|
| `convert` | Turns pasted (or dictated) family messages into park days, parts and steps, with notes, set-aside items and lists. | Typing the plan in by hand, step by step. Since F-087 it is the "plan" half of the one Ask box (`gitaway/say.py`): any text over 600 characters, up to 20,000, from a day (everything on that day) or from no day (spread across the trip; the model also reads a date when the text gives one). The messages are free text with initials, repeats and notes buried mid-line; a rule-based parser would fail on the next message that is worded differently. Candidate to keep: it is the one job nothing simpler can do. | F-080 |
| `speak` | Ask GitAway (Ask tab, F-072): turns a typed or spoken change to one day ("we're tired, block the next two hours and move lunch to 12:30"; since F-087 the "change" half of the one Ask box: a request of up to 600 characters, on the day it came from or the day the family picks in a quick follow-up. A new or moved plan with no time is left null by the model and the app asks) into a proposal of added, moved and removed plans and steps, shown as before and after; nothing changes until Apply, which tells the family. The model sees one day as compact JSON (plan and step ids, times, titles, the family's first names, the trip's zone) plus the request, and answers to a strict schema of operations; the app validates every id and time itself and caps the counts (12 operations; at most 4 added plans, 2 removed plans). | Dragging and tapping through the edit screens, one at a time. Candidate to swap for a small intent classifier plus the existing editors if the phrases stay few (move X to T, skip X, rest for N hours); keep the model for the open-ended ones. | F-072 |
| `ask` | Answers a question about the trip, with search, as a proposal. | Searching the web and the plan by hand. Candidate to drop if nobody uses it. | later |
| `around-you` | Around you (Map tab, F-073): from up to 15 places OpenStreetMap lists near the family (name, distance in metres, open now, a few tags such as cuisine) it picks the best 5 for the chip that was tapped (vegetarian food, coffee, groceries, Costco/Walmart, pharmacy, gas, restrooms) and gives each a one-line reason. The model gets the category, whether the family eats vegetarian and that list, never a coordinate, an address or a family member's name. Every id it returns is checked against the list (unknown and repeated ones are dropped); if it is off, busy, fails or returns nothing valid, places are ordered by distance with closed ones last. | A map search. Candidate to drop: distance plus open now is already a fair ranking and the one-line reason is the only thing it adds. | F-073 |
| `ocr` | Reads a boarding pass or a booking from a photo. | Typing the numbers in. Candidate to replace with a dedicated OCR/vision service or on-device reading. | later |

| `transcribe` | Ask's microphone where the phone has no working speech recognition (the iPhone Home Screen app; F-102): the page records up to 3 minutes (MediaRecorder), `POST /trip/ask/transcribe` sends the audio (at most 4 MB, checked by its first bytes) to a speech-to-text deployment and the words are added to the Ask box for review. | Typing, or the keyboard's own dictation (which still works and costs nothing). A speech model, not a chat model: nothing else here can turn audio into text. Candidate to drop if the keyboard's dictation is enough, or to swap to a provider that handles Hindi and other Indian languages (see below). The audio exists only in memory for the request; neither it nor the words are kept or logged (the log row has no tokens). Editors only, like the rest of Ask. | F-102 |

`convert`, `speak`, `around-you` and `transcribe` exist today; the others are named so the log and the report already have a place for them.

## What is logged

One row per call in the host database table `ga_ai_usage`: when, day, job, the family's id, the deployment used, tokens in, tokens out, milliseconds, ok (1/0) and, if it failed, the kind of error (`timeout`, `http_429`, `bad_json`, `off`). It never holds the prompt, the answer, a name, a place, a position or the key. Nothing in the app prints them either; a failure is shown as a fixed sentence.

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

### Voice typing (`transcribe`)

The provider is **Sarvam AI** (Hindi and other Indian languages, mixed with English) whenever `SARVAM_API_KEY` is set; Azure speech-to-text is the alternative (`GITAWAY_AI_TRANSCRIBE_PROVIDER=azure`, and it needs its own deployment because the chat one cannot transcribe). Nothing else needs setting on Railway for Sarvam: `SARVAM_API_KEY` (optional `SARVAM_STT_MODEL`, default `saarika:v2.5`; `SARVAM_TRANSLATE_MODEL`, default `saaras:v2.5`).

How a recording flows (F-102): the page records (MediaRecorder: `audio/mp4` on iPhone, `audio/webm` elsewhere, at most 3 minutes, 4 MB) and posts it to `/trip/ask/transcribe`. Sarvam `POST https://api.sarvam.ai/speech-to-text` (`api-subscription-key` header; multipart `file`, `model=saarika:v2.5`, `language_code=unknown` to detect it) returns `{"transcript", "language_code"}`; the box shows `transcript` as said, in the language it was said. When `language_code` is not English, a second call to `POST /speech-to-text-translate` (`model=saaras:v2.5`; same key; returns `{"transcript"}` in English) gives the English version. The page keeps the pair in a hidden `heard` field and shows "Understood as: ..." quietly under the box; when the person taps Ask, the planner receives the box's text with each dictated passage swapped for its English, so plan and step titles come out in English (the planner prompts in `speak.py` and `canvas.py` also say to write titles in English whatever the language). A passage the person edited is sent as written, and the planner reads it in any language. A failed translation is not an error: the planner gets the original and is told to write English titles. Both calls are logged as job `transcribe` (two rows for a non-English recording), never the audio or words.

Limits found: Sarvam's docs list WAV, MP3, AAC, AIFF, OGG, OPUS, FLAC, MP4/M4A, AMR, WMA and WebM, so both recorder formats are listed as accepted; this was read from its documentation, not tried with a real iPhone recording. A recording the service refuses (HTTP 400, 415 or 422) shows "The voice service could not read that recording. Tap the microphone on your keyboard to dictate, or type it." and no transcoding is attempted. Translation adds a second round trip (a few seconds) for non-English speech. Sarvam documents the REST speech-to-text endpoint "for quick responses under 30 seconds" (it states no hard limit; longer audio is for its Batch API): a 3-minute recording may be refused or cut. Not tried with a long real recording yet: check it before relying on long dictation, and if it fails, split the recording on the page into 30 s pieces.

| Variable | Effect |
|---|---|
| `SARVAM_API_KEY` | Switches voice typing on with Sarvam AI (the default provider when it is set). |
| `AZURE_OPENAI_TRANSCRIBE_DEPLOYMENT` | The speech-to-text deployment (for example a `gpt-4o-transcribe` or `whisper` one). It never falls back to the chat deployment. Without it the route answers "Voice typing isn't set up yet — tap the microphone on your keyboard to dictate". `GITAWAY_AI_DEPLOYMENT_TRANSCRIBE` overrides it. |
| `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` | The same key and endpoint as the other jobs (`GITAWAY_AI_KEY_TRANSCRIBE` / `GITAWAY_AI_ENDPOINT_TRANSCRIBE` override them). |
| `AZURE_OPENAI_TRANSCRIBE_API_VERSION` | Optional; default `2024-06-01`. |
| `GITAWAY_AI_TRANSCRIBE_PROVIDER` | Optional; `sarvam` or `azure`; default `sarvam` when `SARVAM_API_KEY` is set, else `azure`. Which adapter in `ai.PROVIDERS` does the call. An unknown name switches the job off. |

The language is detected by the service (Hindi mixed with English comes back as spoken). `ai.transcribe(..., language="hi")` and the route's optional `lang` field pass a hint; the page does not send one yet (`data-lang` on the box would).

**Adding a provider** (for example for Hindi and other Indian languages). Add one entry to `ai.PROVIDERS` in `gitaway/ai.py`, three small functions, and nothing else: the call, the 45 s limit, the one-at-a-time rule, the log and the fixed failure sentences are shared.

1. `configured()`: true when all its settings (key, endpoint or region, model) are present.
2. `request(audio, filename, mime, language)` returns `(url, headers, body)`: its endpoint, its auth header (`api-key`, `Authorization: Bearer ...`, `xi-api-key`...), and the request body (multipart with the file, or the raw audio bytes with a content type). `language` is a code or `None` for auto-detect.
3. `text(reply)` returns the words from the response body (the JSON field that holds the transcript); raise `ValueError`, `KeyError` or `TypeError` when the shape is wrong.

Then set `GITAWAY_AI_TRANSCRIBE_PROVIDER=<name>` and its own settings. `tests/test_transcribe.py` shows a fake adapter (`test_another_provider_is_one_setting_and_one_small_adapter`): copy it for the new one, with a recorded sample response.

## Tests

The suite never calls the network: `ai.TRANSPORT` is replaced by a fake, and the conftests pin the `AZURE_*` keys to empty. `python -m gitaway.ai_smoke` (Convert) and `python -m gitaway.speak_smoke` (Ask GitAway, on a canned day) are the real calls, run by hand: they print counts and the time taken only. `python -m gitaway.around_smoke [lat lon]` asks the real Overpass API for vegetarian food and restrooms near a point (default Disneyland) and has the model rank the candidates; it prints counts and seconds, no place names.
