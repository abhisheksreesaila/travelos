# What the AI does (F-079)

Azure OpenAI is a stopgap for the October 2026 trip. Every call goes through `gitaway/ai.py` and is logged, so after a week we can see which jobs it really did and decide, job by job, what to keep, swap for a cheaper model or a small classifier, or drop.

## The jobs

| Job | What it does | What it replaces, and why the model | Ticket |
|---|---|---|---|
| `convert` | Turns pasted (or dictated) family messages into park days, parts and steps, with notes, set-aside items and lists. | Typing the plan in by hand, step by step. The messages are free text with initials, repeats and notes buried mid-line; a rule-based parser would fail on the next message that is worded differently. Candidate to keep: it is the one job nothing simpler can do. | F-080 |
| `speak` | Ask GitAway (Ask tab, F-072): turns a typed or spoken change to one day ("we're tired, block the next two hours and move lunch to 12:30") into a proposal of added, moved and removed plans and steps, shown as before and after; nothing changes until Apply, which tells the family. The model sees one day as compact JSON (plan and step ids, times, titles, the family's first names, the trip's zone) plus the request, and answers to a strict schema of operations; the app validates every id and time itself and caps the counts (12 operations; at most 4 added plans, 2 removed plans). | Dragging and tapping through the edit screens, one at a time. Candidate to swap for a small intent classifier plus the existing editors if the phrases stay few (move X to T, skip X, rest for N hours); keep the model for the open-ended ones. | F-072 |
| `ask` | Answers a question about the trip, with search, as a proposal. | Searching the web and the plan by hand. Candidate to drop if nobody uses it. | later |
| `around-you` | Around you (Map tab, F-073): from up to 15 places OpenStreetMap lists near the family (name, distance in metres, open now, a few tags such as cuisine) it picks the best 5 for the chip that was tapped (vegetarian food, coffee, groceries, Costco/Walmart, pharmacy, gas, restrooms) and gives each a one-line reason. The model gets the category, whether the family eats vegetarian and that list, never a coordinate, an address or a family member's name. Every id it returns is checked against the list (unknown and repeated ones are dropped); if it is off, busy, fails or returns nothing valid, places are ordered by distance with closed ones last. | A map search. Candidate to drop: distance plus open now is already a fair ranking and the one-line reason is the only thing it adds. | F-073 |
| `ocr` | Reads a boarding pass or a booking from a photo. | Typing the numbers in. Candidate to replace with a dedicated OCR/vision service or on-device reading. | later |

`convert`, `speak` and `around-you` exist today; the others are named so the log and the report already have a place for them.

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

## Tests

The suite never calls the network: `ai.TRANSPORT` is replaced by a fake, and the conftests pin the `AZURE_*` keys to empty. `python -m gitaway.ai_smoke` (Convert) and `python -m gitaway.speak_smoke` (Ask GitAway, on a canned day) are the real calls, run by hand: they print counts and the time taken only. `python -m gitaway.around_smoke [lat lon]` asks the real Overpass API for vegetarian food and restrooms near a point (default Disneyland) and has the model rank the candidates; it prints counts and seconds, no place names.
