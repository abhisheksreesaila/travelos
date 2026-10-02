# The phone trip view (F-054)

`/trip` is the trip home for phones and for the installed Home Screen app: **Today** (up next, the day's timeline, tonight's hotel), **All days** (a tinted tile per day) and **Notes** (the feed and composer), with a **+** that adds a plan.

| Where | What |
|---|---|
| `gitaway/pages/trip.py` | The page and its two writes: `POST /trip/plans` (title, start, kind) and `POST /trip/notes`. Both use `gitaway.tripcal` (the calendar's own validation, flight window and ride clashes included), so the calendar and `/trip` always agree. |
| `gitaway/tripday.py` | The pure model: phase of the trip (before, during, after), the day's items marked done/now/next, the "in 40 min" countdown, one line per day, the hotel card, Directions links, phone detection. |
| `assets/css/trip.css`, `assets/js/trip.js` | Phone-first styles (safe-area insets, 44px targets, no pulse under reduced motion) and the small script (tabs and sheet without a reload; every tab and the + are plain links without it). |

## Who gets it

- `/trip` opens for anyone signed in with a trip (signed out goes to sign-in, no trip goes to `/start`).
- A **plain** `/calendar` (no query) on a phone browser (`tripday.is_phone`: iPhone, Android phone; not iPad) redirects to `/trip`. `/calendar?view=whole` or any other query is never redirected, so "Open the full calendar" (on the trip view) and every in-calendar link keep working. Desktops and tablets keep the calendar.
- The manifest's `start_url` is `/trip`; the "Continue" card on `/start` links to `/trip` on phones.

## Today

"Today" is `catalog.today_in(zone)` and the minute is `tripday.now_minute(zone)`, in the trip's own time zone (F-057: `trips.timezone`, set on import from `timezone:` or the arrival airport via `gitaway/zones.py`, Los Angeles for demo trips); pin `catalog.now_utc` in tests. The server's past-date check and the date pickers keep one `catalog.today()` (Los Angeles). Before the trip: "Trip starts in N days" and day 1's plan. During: the dark Up next card (with "in N min", or "happening now"), Directions (Apple Maps on Apple devices, else Google Maps; only a place name or address goes in the link, never a confirmation number), and "Get an Uber" when a ride for the day is still to schedule (the simulated rides flow). After: a "Welcome home" recap. Tap a day in the strip (or a tile) to see another day.

## Roles and trips

Viewers see no + and no composer; the central write gate (`gitaway/access.py`) refuses their posts anyway. Every form carries the hidden `trip` field.

## Hook for F-051

The add sheet's start time is a plain native `<input type="time" data-time-picker>`. The themed picker attaches to `[data-time-picker]`.

After F-051 (themed pickers) merges, `HEAD` in `gitaway/pages/trip.py` must include `*pickers.HEAD` so the picker loads on this page. Whichever of F-051 and F-054 merges second wires it.
