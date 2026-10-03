# Photos on the plan (F-071)

Code: `gitaway/photos.py` (rules, storage, matching), `gitaway/pages/photos.py` (routes, Photos view, photo page), `gitaway/familydb_photos.py` (table), `assets/js/photos.js`.

- **Add.** The Family tab has a camera button in the compose row (an `<input type=file accept="image/*" capture=environment multiple>`: iPhone opens the camera) and, in the Photos view, "Take a photo" and "From your library" (no `capture`: iPhone offers its library). JS uploads one file per request to `POST /trip/photos`.
- **Accepted.** JPEG, PNG, WebP, HEIC by magic bytes; 15 MB each (checked from Content-Length before parsing, then per file); 80 megapixels; 6 per upload. HEIC is decoded with `pillow-heif` (conda-forge).
- **Stored.** `<GITAWAY_DATA_DIR>/photos/<family>/<trip>/<random id>.<ext>` (original, never served) plus `-display.jpg` (1600) and `-thumb.jpg` (640), re-encoded without EXIF/GPS. Time and coordinates live only in the `photos` table.
- **Matching.** EXIF DateTimeOriginal (the trip's clock if no offset; else upload time) selects the day and the plan whose window contains it; otherwise the nearest plan that day within 3 km using only places `gitaway.geo` has cached (F-068; none yet, so this falls through); otherwise the day.
- **Who.** Every member adds (viewers too, like messages; POST routes are on `access.OPEN_POSTS`). Remove: the author or an admin. Files are served only by `GET /trip/photos/<id>/<display|thumb>` to a member of the photo's family, `Cache-Control: private`.
- **Thread.** Each photo posts a card (`familythread.post_photo`); removing it deletes the card. Other open browsers drop the card on their next reload (the poll only appends).
