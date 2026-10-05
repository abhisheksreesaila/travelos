# Talk on the block (F-091)

Messages, photos and voice notes that belong to a plan, or to one part of a park day (Lunch). Brief: `docs/briefs/day-plan.md`.

## Storage

- A message is a family-thread item (`thread` table, `docs/family-db.md`), so the Family tab shows it too. Payload: `{"act": "<plan id>", "part": "<part id or empty>"}`. Kinds: `message`, `photo` (also `{"url", "photo"}`), `voice` (also `{"file", "mime", "secs"}`).
- Voice files: `<data folder>/voicenotes/<family>/<trip>/<random id>.<m4a|webm|ogg>` (`gitaway/voicenotes.py`). Kind from the first bytes (`ftyp` mp4, EBML webm, `OggS`), at most 4 MB and 180 s (the page times it; audio is not decoded). Empty, too big, too long or another type is refused with a plain message. Removed with the trip (`importer.delete`).
- Photos reuse `gitaway/photos.py` (`add(..., talk=...)`): same checks and resizing, pinned to the plan.
- Served only by the thread item's address, to members of the family that owns it; Starlette's `FileResponse` answers byte ranges (206) for iPhone audio.

## Routes (`gitaway/pages/plantalk.py`, model `gitaway/plantalk.py`)

| Route | |
|---|---|
| `GET /trip/talk?act=aN[&part=pN]` | the chat, in the phone shell (Today tab); back goes to `/trip/canvas?day=N` |
| `GET /trip/talk/items?act=&part=&since=` | new items as a fragment (the chat polls it, `thread.js`) |
| `POST /trip/talk/message`, `/photo`, `/voice` | open to every member, viewers too (`access.OPEN_POSTS`, `tests/test_roles.py`); `X-Fragment: 1` answers with the new items or a plain message and status |
| `GET /trip/talk/voice/<item id>` | the audio |

An upload over its cap is refused from Content-Length before the body is read (`UploadLimit` middleware). The push is the thread's (`familythread.announce`): title is the first name, body "on Lunch · Universal Studios: voice note" (text for messages), same quiet and two-minute rules.

## On the canvas

`plantalk.counts(session)` gives `{(plan, part): {"n", "voice", "photo"}}`, loaded once in `tripcanvas.load` as `v["talk"]`. `talk_badge(v["talk"], act, part)` draws the pill: bubble, count, a mic when a voice note is in it; a plan with nothing said shows a quiet "+ chat", a part shows nothing. Used on the park block card (block row and part headers), the plain plan card (`kind == "plan"` only) and the block view.

## Family tab

Each plan message carries an "on Lunch · Universal Studios" tag linking to its chat (`tab_family.item_view(..., labels)`); voice notes play there too (`voicenote.js`).

## Scripts

`assets/js/plantalk.js` (photo button, mic: MediaRecorder with audio/mp4, then webm; red dot, timer, Cancel, Send; auto-stop at 3:00; the mic is hidden without MediaRecorder or getUserMedia), `voicenote.js` (play in place), `thread.js` (polls `data-poll-url`, sends the form's fields).

## Tests

`tests/test_plantalk.py` (voice files, model, counts, push), `tests/test_plantalk_routes.py` (page, posts, refusals, roles, another family's file, Range, Family tab, canvas badges), `tests_browser/test_plan_talk.py` (fake microphone: cancel, record, send, play, photo, badge, Family tab; 390 and 320).
