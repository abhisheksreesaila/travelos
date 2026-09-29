# TravelOS Redesign Specification — "Field Notes"

Status: proposed · Authored with Claude Opus 5.5 (`claude-opus-5-5`) · 2026-09-29
Supersedes: the untracked `DESIGN_SPEC.md` draft ("Omarchy × premium travel"). That draft's type/mono interplay survives here; its palette, surface rules, and page treatments are replaced.
Companion: [`redesign-reference.html`](redesign-reference.html) — a static, dependency-free page that renders every token and core component in both themes. Open it directly in a browser; it is the visual source of truth when this document and a screenshot disagree.

---

## 0. Why redesign

An audit of the running app (`TRAVELOS_PROTOTYPE=1`, 1440×900 and 390×844, both themes) found that the product does not currently read as one product:

| # | Finding | Evidence | Consequence |
|---|---------|----------|-------------|
| A1 | **Two unrelated identities.** Public pages (`/`, `/discover`, `/plans/*`, `/creators`) are a saturated "sunset poster" (navy→violet gradients, coral/sky/violet full-bleed bands). `/prototype` (Compass) is a quiet teal-green system-sans utility. | `assets/public.css` vs `assets/compass.css` (own `--accent`, `--bg`, `--font-display`) | A traveler moving from Discover to Compass appears to change websites. |
| A2 | **Web fonts are declared but never loaded.** `--font-sans: "Inter"`, `--font-serif: "Fraunces"`, `--font-mono: "JetBrains Mono"` have no `@font-face` and no bundled files. | `assets/tokens.css:10-12`; headlines render as Georgia/Times with `-0.06em` tracking | Headlines look cramped and accidental ("Lesssearching."); every machine renders differently. |
| A3 | **Hue names are reused for different hues.** `--color-sun` is orange `#ff6e40` in bright and yellow `#fbbf24` in dark; `DESIGN_SPEC.md` calls sun yellow and orange `--accent-orange`. | `assets/tokens.css` bright vs dark blocks | Components styled "sun" change meaning between themes; contributors can't reason about color. |
| A4 | **Workspace itinerary layout collapses.** Item titles sit in a ~60px column, wrapping one word per line, while descriptions overflow beside them. | `/plans/{slug}/preview`, `.command-*` grid in `assets/workspace.css` | The core object of ADR-0002 (the plan) is least legible exactly where users work on it. |
| A5 | **Plan detail and workspace render the same itinerary two different ways.** Public timeline (numbered sun circles, sans) vs workspace (mono table). Also 19 inline `style=""` blocks in `main.py` build places/friends/timeline rows. | `main.py:282,293,338,348,359` | Two code paths drift; inline styles bypass tokens and themes. |
| A6 | **Hero search is clipped.** The four-field search card overlaps the hero's bottom edge and is cut by `overflow:hidden` at desktop, and nearly fully hidden on mobile, leaving ~120px of blank paper. | `/` at 1440 and 390 widths | The primary entry point is half-visible. |
| A7 | **Discover search button floats inside its field** with a large dead zone to its right; region filters are pill-shaped while every other chip is square-mono. | `/discover` | Low-craft impression on the most-used page. |
| A8 | **Footer is a boxed inset** (`max-width` navy panel) on a full-bleed page; on short pages it floats mid-viewport with paper below. | `/discover`, `/creators`, `/prototype` | Pages feel unfinished. |
| A9 | **Plan imagery is placeholder geometry** (identical sun + two blocks per card, recolored). Real CC0 destination photos exist only for Compass. | `scene()` in `main.py`, `assets/photos/compass/` | Cards are indistinguishable; nothing says "Kyoto" vs "Oaxaca". |
| A10 | **Fixture disclaimers compete with content.** "FIXTURE DATA", "SIMULATED", "Illustrative fixture…", "Local demo data" appear in five styles. | plan detail rail, creators proof, discover header | Honest labeling is right, but it should be one quiet, consistent pattern. |

Everything below exists to fix A1–A10 without changing product scope, routes, or data contracts.

---

## 1. Design direction

**"Field Notes": a traveler's notebook, typeset by an engineer.**

TravelOS is "GitHub for travel": the plan is a living, forkable document (ADR-0002) and contributors are anonymous (ADR-0001). The visual system should therefore feel like a *well-made document*, not like an ad for a destination:

- **Paper, ink, and one signal color.** A warm off-white page, near-black ink, and a single orange action color. Other hues are *semantic* (success, info, creator, day-marker), used small.
- **The plan is the hero.** Pages open on a plan's title and route, not on gradient art. Color comes from destination photography and small accents, not from full-bleed bands.
- **Sans for story, mono for facts.** Kept from the previous draft, because it is the brand's best idea: *"A long weekend in Granada"* over `DAY 01 · APR 12 · 15:00`.
- **Honest by default.** Demo/fixture status is a single, calm, always-present pattern (§5.9), never a banner fight.
- **One system, two lighting conditions.** Dark mode is the same product at night: identical layout, type, and components; only surface and ink tokens change. The workspace is no longer "a terminal"; it is the notebook with the lights down.

What we deliberately drop: full-bleed gradient hero bands, the rotating globe art, the "reach bubble" stickers, pill-shaped filters, the plum-to-coral preview banner, and the navy boxed footer.

---

## 2. Typography

### 2.1 Families (self-hosted, offline-safe)

| Role | Family | Fallback stack | Files to ship |
|------|--------|----------------|---------------|
| Display | **Fraunces** (variable, opsz 9–144, wght 300–800), SIL OFL | `"Iowan Old Style", Georgia, serif` | `assets/fonts/fraunces-var.woff2` (Latin subset) |
| Sans | **Inter** (variable, wght 400–800), SIL OFL | `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif` | `assets/fonts/inter-var.woff2` |
| Mono | **JetBrains Mono** (variable, wght 400–800), SIL OFL | `ui-monospace, "SF Mono", "Cascadia Code", monospace` | `assets/fonts/jetbrains-mono-var.woff2` |

Rules:

- Fonts are **self-hosted** under `assets/fonts/` and declared in a new `assets/fonts.css` loaded first. The project's "zero CDN, works offline" rule (AGENTS.md) stands.
- `font-display: swap`; preload only Inter (`<link rel="preload" as="font" crossorigin>`).
- Fraunces is used **only** for display sizes (≥ 32px): page titles and plan titles on hero/detail. Card titles, UI, and body are Inter. This fixes A2's "serif everywhere by accident".
- Fraunces settings: `font-variation-settings: "opsz" 96, "SOFT" 50, "WONK" 0`; weight 600. Never italic except the single emphasized word in a page title (`<em>`), which uses weight 500 italic in `--accent-ink`.

### 2.2 Scale

Fluid only at display sizes; UI sizes are fixed for density and predictability.

| Token | Size | Line-height | Tracking | Family / weight | Use |
|-------|------|-------------|----------|-----------------|-----|
| `--type-display` | `clamp(2.75rem, 1.6rem + 3.6vw, 4.5rem)` | 1.02 | −0.025em | Fraunces 600 | Home headline, plan title on detail |
| `--type-h1` | `clamp(2rem, 1.4rem + 1.9vw, 3rem)` | 1.08 | −0.02em | Fraunces 600 | Page titles |
| `--type-h2` | `1.5rem` (24px) | 1.2 | −0.015em | Inter 700 | Section titles |
| `--type-h3` | `1.125rem` (18px) | 1.3 | −0.01em | Inter 650 | Card titles, itinerary item titles |
| `--type-lede` | `1.125rem` (18px) | 1.6 | 0 | Inter 400 | Lede paragraphs |
| `--type-body` | `1rem` (16px) | 1.6 | 0 | Inter 400 | Body copy |
| `--type-ui` | `0.875rem` (14px) | 1.45 | 0 | Inter 500 | Buttons, nav, inputs, descriptions in dense panels |
| `--type-small` | `0.8125rem` (13px) | 1.45 | 0 | Inter 400 | Secondary copy, captions |
| `--type-label` | `0.6875rem` (11px) | 1.3 | 0.08em, uppercase | JetBrains Mono 600 | Eyebrows, field labels, status tags |
| `--type-data` | `0.8125rem` (13px) | 1.4 | 0 | JetBrains Mono 500, `tabular-nums` | Times, dates, prices, temps, counts |

Hard floor: **no text below 11px**. The previous 8px/9px/10px sizes are removed (they failed legibility at 1× DPR).

The old draft tracked headlines at −0.065em; with a real display face, −0.025em is the maximum. Never negative-track Inter below `--type-h2`.

### 2.3 Sans vs mono (kept, tightened)

Mono is for **values a machine could produce**: times, dates, durations, prices, temperatures, counts, coordinates, URLs, keyboard hints, and status tags. Everything a person would *write* (titles, descriptions, notes, quotes, buttons, nav) is sans or display.

Litmus test: if it would be right-aligned in a spreadsheet, it is mono.

Previously mono leaked into workspace titles and descriptions (A4 screenshot); that stops. The dark theme does **not** switch `--font-sans` to mono (remove `tokens.css:193`).

---

## 3. Color

### 3.1 Principle: semantic tokens only in components

Components reference **role tokens** (`--accent`, `--surface-1`, `--ink-2`, `--day`) and never hue names. Hue primitives live in one block and are referenced only by role tokens. This makes A3 structurally impossible.

### 3.2 Primitives

| Primitive | Light value | Notes |
|-----------|-------------|-------|
| `--paper-50` | `#FBF9F4` | page |
| `--paper-100` | `#F4F0E6` | sunken areas, rails |
| `--paper-0` | `#FFFFFF` | raised cards, inputs |
| `--ink-900` | `#16181B` | primary text |
| `--ink-700` | `#3A4048` | secondary text |
| `--ink-500` | `#5F6873` | tertiary / meta (5.4:1 on paper-50) |
| `--ink-300` | `#B9B3A6` | disabled, decorative rules |
| `--rule` | `#E3DDD0` | borders and dividers |
| `--orange-500` | `#E8552B` | signal |
| `--orange-700` | `#B63E1C` | signal text on paper (5.4:1) |
| `--orange-100` | `#FCE6DC` | signal tint |
| `--sun-400` | `#F5C542` | day markers, highlights (yellow; never orange) |
| `--sun-100` | `#FDF3D2` | |
| `--green-600` | `#17744E` | success text (5.5:1) |
| `--green-100` | `#DDF3E8` | |
| `--blue-600` | `#2167B8` | info text, links in dense UI (5.4:1) |
| `--blue-100` | `#E1ECF9` | |
| `--plum-600` | `#6A4BD1` | creator / contributor (5.6:1) |
| `--plum-100` | `#ECE6FB` | |
| `--red-600` | `#B3302A` | errors, destructive (5.9:1; 5.1:1 on red-100) |
| `--red-100` | `#FBE3E1` | |

Dark primitives: `--night-950 #0F1113`, `--night-900 #16191C`, `--night-800 #1E2226`, `--night-700 #2A2F35`, `--moon-100 #ECE8DF`, `--moon-300 #B4AFA5`, `--moon-500 #8A867E`; accents shift one step lighter (`--orange-400 #F2764F`, `--sun-300 #F8D56E`, `--green-400 #4CC08D`, `--blue-400 #6FA6E6`, `--plum-400 #9C85EC`, `--red-400 #EC6B63`).

### 3.3 Role tokens

| Role | Light | Dark | Meaning |
|------|-------|------|---------|
| `--bg` | paper-50 | night-950 | page |
| `--surface-1` | paper-0 | night-900 | cards, panels, inputs |
| `--surface-2` | paper-100 | night-800 | sunken rails, hover, table stripes |
| `--surface-inverse` | ink-900 | moon-100 | tooltips, toasts, primary button |
| `--ink-1` / `--ink-2` / `--ink-3` | ink-900 / 700 / 500 | moon-100 / 300 / 500 | text hierarchy |
| `--rule` | rule | night-700 | 1px borders |
| `--accent` | orange-500 | orange-400 | primary CTA fill, active indicators, focus ring |
| `--accent-ink` | orange-700 | orange-400 | orange text / links on bg |
| `--accent-tint` | orange-100 | `color-mix(in oklab, orange-400 18%, night-900)` | selected rows, active chips |
| `--day` / `--day-tint` | sun-400 / sun-100 | sun-300 / 18% mix | day markers, "today", featured |
| `--ok` / `--ok-tint` | green-600 / 100 | green-400 / 18% | booked, confirmed, saved |
| `--info` / `--info-tint` | blue-600 / 100 | blue-400 / 18% | info, fixture/demo notices, links in dense UI |
| `--creator` / `--creator-tint` | plum-600 / 100 | plum-400 / 18% | creator attribution, creator studio accents |
| `--danger` / `--danger-tint` | red-600 / 100 | red-400 / 18% | errors, destructive actions |

### 3.4 Usage budget

- **Accent budget:** at most one filled `--accent` element per viewport (the primary action). Everything else orange is text or a 2px indicator.
- Semantic tints appear only in chips, tags, and small callouts (≤ 1 per card).
- **No full-bleed color bands** anywhere. The largest colored area on any page is a photograph.
- Text on `--accent` fill is `--ink-900` (light) / `--night-950` (dark) at 15px+ bold: never white (white on orange-500 is 3.6:1; ink-900 is 4.9:1).
- Focus ring: `outline: 2px solid var(--accent); outline-offset: 2px`, everywhere, both themes. (Previously a mix of gold `#efb409`, plum, and glow shadows.)

### 3.5 Theming mechanics

- `data-theme` on `<html>` (not `<body>`), values `light` | `dark`; absent = follow `prefers-color-scheme`.
- Rename theme values `bright`→`light`; keep reading the legacy `bright` from `localStorage["travelos-theme"]` and migrate it.
- **The workspace no longer forces dark.** It follows the user's theme like every other page (A1). The `.command-shell` scope keeps only layout rules.

---

## 4. Space, layout, surface

### 4.1 Spacing

4px base, one scale: `--s-1:4 --s-2:8 --s-3:12 --s-4:16 --s-5:24 --s-6:32 --s-7:48 --s-8:64 --s-9:96`. Section rhythm on public pages: `--s-8` between sections (desktop), `--s-7` (mobile). Inside panels: `--s-4` padding dense, `--s-5` default.

### 4.2 Grid and containers

- Page container: `width: 100%; max-width: 1200px; margin-inline: auto; padding-inline: clamp(16px, 4vw, 40px)`. The explicit `width: 100%` matters: inside the grid `body` (§5.11), auto inline margins otherwise shrink the container to its content's min-content width.
- 12 columns, 24px gutter. Standard splits: **8/4** (content + context rail), **6/6** (hero), **3×4** (card grid).
- Reading measure for prose: `max-width: 64ch`.
- Workspace container: full width, `grid-template-columns: 280px minmax(0, 1fr) 340px`; collapses to `minmax(0,1fr)` + drawer rail below 1100px, single column below 720px. **Every grid track that holds text is `minmax(0, …)`**. This fixes A4.

### 4.3 Surfaces

Three surface types, no others:

1. **Sheet**: `--surface-1`, `1px solid var(--rule)`, `border-radius: 12px`, no shadow. Default card/panel.
2. **Rail**: `--surface-2`, no border, radius 12px. Context rails (weather, places, friends), sidebars, callouts.
3. **Float**: `--surface-1`, `--rule` border, radius 12px, `--shadow-float: 0 12px 32px -12px rgb(22 24 27 / .22)`. Only for menus, popovers, the sticky search, and dialogs.

Radius scale: `--r-sm 6px` (chips, tags, inputs' inner elements), `--r-md 10px` (buttons, inputs), `--r-lg 12px` (sheets), `--r-xl 20px` (photo frames). **No pills** except the avatar and the toggle switch.

---

## 5. Components

All components live in `assets/components.css` (shared) and are rendered from **one Python helper each** (in a new `ui.py`) so `main.py`, `prototype_*.py`, and Compass share markup. No inline `style=""` in rendered HTML (A5).

### 5.1 Header

- Height 64px, `--bg` with `border-bottom: 1px solid var(--rule)`; becomes `--surface-1` + float shadow after 8px scroll.
- Left: wordmark (§5.13) · nav links `Discover`, `Creators`, `My trips` (Inter 500 14px, `--ink-2`; current page `--ink-1` + 2px `--accent` underline offset 20px).
- Right: theme toggle (icon button), `Sign in` (secondary button) or avatar menu.
- Mobile (< 720px): wordmark + menu button; nav opens a full-height sheet.
- One header for public, plan, workspace, and Compass. The workspace adds a **breadcrumb row** below it (§6.4), it does not replace it.

### 5.2 Buttons

| Variant | Fill | Text | Border | Use |
|---------|------|------|--------|-----|
| Primary | `--accent` | `--ink-900` | none | One per viewport: Fork, Search, Submit |
| Secondary | `--surface-1` | `--ink-1` | `--rule` | Share, Sign in, Preview |
| Quiet | transparent | `--ink-2` | none | Tertiary actions, inline "Save note" |
| Danger | `--danger-tint` | `--danger` | none | Delete, discard |

Sizes: `md` 40px (default), `lg` 48px (hero search, plan Fork CTA), `sm` 32px (dense panels). Inter 600 14px (lg: 15px). Icon 16px, gap 8px. Hover: fill darkens via `color-mix(... 90%, black)`; press: `translateY(1px)`. Disabled: 40% opacity, `cursor: not-allowed`.

### 5.3 Inputs and the search bar

- Input: 44px, `--surface-1`, `--rule` border, radius `--r-md`, label above in `--type-label` mono. Focus: border `--accent` + ring.
- **Search bar (single component, two sizes)** (A6, A7):
  - `lg` (home): a Float, 64px tall, segments `Where` · `When` · `Who`, then a primary `lg` button *inside* the right edge. Segments separated by 1px `--rule` verticals. Placed **below** the hero headline in normal flow, never overlapping a clipped container.
  - `md` (discover, header-sticky): Sheet, 48px, destination only + icon button flush right. No dead zone: the input grows (`flex:1`).
  - Mobile: segments stack; the whole bar is one Float with a full-width primary button.
- Date segment uses one date-range button that opens a popover; no raw `mm/dd/yyyy` natives visible in the resting state.

### 5.4 Chips, tags, filters

- **Tag** (read-only attribute: "Food-forward", "Walkable"): `--type-small` Inter 500, `--surface-2` fill, `--ink-2`, radius `--r-sm`, 24px tall.
- **Status tag** (system state: `CREATOR TIP`, `BOOKED`, `FLEX`, `SAMPLE`): `--type-label` mono, semantic tint fill + semantic ink, radius `--r-sm`, 20px tall.
- **Filter** (region, interests): segmented control. Row of 36px buttons sharing one `--rule` border; active = `--ink-1` fill + `--bg` text. Replaces pill filters (A7).

### 5.5 Plan card

The most-repeated component. Anatomy top→bottom:

1. **Cover**: 16:10 photo, radius `--r-xl` top, `object-fit: cover`. Top-left: duration data tag (`4 DAYS`). Top-right: save icon button (Float, 36px). No price overlay on the image.
2. **Meta row**: `--type-data`: `EUROPE · APR 12–16`.
3. **Title**: `--type-h3` Inter 650, 2-line clamp.
4. **Summary**: `--type-small`, `--ink-2`, 2-line clamp.
5. **Footer row**: creator attribution (§5.8, compact) left; `from $624` (`--type-data`, `--ink-1`) and fork count (`⑂ 1.8k`) right.

Whole card is one link (`<a>` wraps; save button stops propagation). Hover: cover image scales 1.03 over 400ms; title gets `--accent-ink`. No card-level shadow.

**Imagery (A9):** each fixture plan gets one real CC0/public-domain destination photo, stored under `assets/photos/plans/{slug}.jpg` (≤ 180KB, 1200×750, with a credits entry in the existing photo-credits dialog pattern from Compass). Until a photo exists, render the **route card fallback**: `--surface-2` fill, the plan's stop names as a mono dotted route line, and the city name in Fraunces. Never the generic geometric scene.

### 5.6 Itinerary (one component, three densities)

Single renderer `ui.itinerary(days, density)` used by plan detail, workspace, preview, PDF snapshot, and Compass calendar list (A5).

```
DAY 01 · SAT APR 12                                    ☀ 24° · 3 stops
├─ 15:00   Check in, then let the city lead                    [FLEX]
│          Settle near Plaza Nueva. First evening unbooked.
│          ♡ Save note   ⌖ Nearby
├─ 19:30   Tapas route through Realejo               [CREATOR TIP]
│          Three tiny bars, one viewpoint…
└─ ·····   Unscheduled time                     (dotted, ink-3)
```

- Grid: `grid-template-columns: 64px minmax(0,1fr) auto`. Time column (mono `--type-data`, `--ink-2`), content column (title `--type-h3`, description `--type-small`), tag column.
- Vertical rule: 2px `--rule`, with a 10px `--day` dot at each item; booked items get an `--ok` dot; the current/next item a ringed `--accent` dot.
- Day header: mono `--type-label` date + right-aligned weather/stop count. Sticky under the header in the workspace.
- **Unscheduled time is shown**, as a dotted row: CONTEXT.md says unscheduled time is valid, so the UI should make it visible and calm.
- Densities: `comfortable` (public, 24px item gap), `compact` (workspace, 12px gap, descriptions 1-line clamp, expand on click), `print` (no actions, full text, black ink).
- Mobile: time column drops to a line above the title.

### 5.7 Context rail

Right-column stack on plan detail and workspace: **Weather**, **Places**, **Friends' notes**, **Getting there** (flights/hotels stubs). Each is a Rail surface with:

- Head: 16px icon + `--type-label` title + right-aligned source tag (§5.9).
- Body rows: 48px min, `--rule` dividers, name in Inter 600 14px, category in `--type-data` `--ink-3`, description `--type-small` 2-line clamp.
- Places list shows 5 then "Show all 10". (Previously 10 tall rows made the rail 2× the itinerary height.)
- Weather: big temp in `--type-h2` mono, 4-day strip as a 4-column mono grid, one sentence of advice.

### 5.8 Creator attribution

Consistent with ADR-0001 (no platform usernames): attribution is **the creator's external channel**, never a TravelOS profile.

- Compact (cards): 24px monogram avatar (`--creator-tint` fill, `--creator` text) + name (Inter 600 13px) + channel glyph. No follower counts on cards.
- Full (plan detail): Sheet with avatar 40px, name, one-line bio, channel buttons (Secondary sm, with platform glyph + handle). Reach numbers, if shown, are `--type-data` with a fixture tag.
- Anonymous plans show `Community plan` with a ⑂ glyph in the same slot. The slot is never empty.

### 5.9 Honest-data pattern (A10)

One pattern replaces "FIXTURE DATA", "SIMULATED", "Illustrative fixture…", "Local demo data", the preview gradient banner, and Compass's "LOCAL DEMO" strip:

- **Global:** a 32px **demo strip** under the header on every page: `--info-tint` background, `--type-small` `--info`: `Demo · sample prices, weather and people. Nothing is booked.` + `About this demo` quiet link. Dismissible per session; it returns in the footer.
- **Local:** a single `SAMPLE` status tag (info tint) in a panel head where the data is synthetic. No sentences inside panels.

### 5.10 Feedback

- Toast: `--surface-inverse`, bottom-center, 4s, one line + optional action.
- Empty state: Rail surface, 16px icon, one sentence, one secondary action.
- Error: inline under field (`--danger`, `--type-small`) + field border `--danger`.
- Loading: skeleton blocks in `--surface-2` with a 1.2s opacity pulse (disabled under reduced motion).

### 5.11 Footer

Full-bleed `--surface-2`, `border-top: 1px solid var(--rule)`; container-aligned three columns (wordmark + one-line mission · product links · demo notice + photo credits). Always pinned to page bottom via `body { min-height: 100dvh; display: grid; grid-template-rows: auto auto 1fr auto; grid-template-columns: minmax(0, 1fr); }` (A8). The explicit `minmax(0, 1fr)` column is required: without it the body's grid column grows to the widest child's min-content and causes horizontal scroll at 320px; likewise set `body > * { min-width: 0; }` because grid items default to `min-width: auto`.

### 5.12 Icons

Keep the dual server (`icon()` in `main.py`) / client (`assets/icons.js`) systems, move the server copy into `ui.py`, and add a test that asserts both export the same icon names. 1.75px stroke, 16/20/24px sizes, `currentColor`.

### 5.13 Wordmark

`Travel` in Inter 750 + `OS` in JetBrains Mono 700, `--accent-ink`, preceded by a 24px mark: a rounded square in `--ink-1` containing a 3-dot route in `--accent`/`--day`. Remove the coral gradient tile.

---

## 6. Page treatments

### 6.1 Home `/`

1. **Hero (6/6 split, `--bg`, no gradient):** left: `--type-label` eyebrow `FORKABLE TRAVEL PLANS`, display headline *"Borrow a great trip. **Make it** yours."* (one `<em>`), lede, then the `lg` search bar in normal flow. Right: a stacked pair of real plan cards (§5.5) slightly rotated (−2°/3°) to show "plans, not destinations" (ADR-0002).
2. **Proof row:** three mono stats as a single line with `·` separators, `--ink-2`, each with a `SAMPLE` tag, not three boxed columns.
3. **Plans with a pulse:** section title + filter (segmented) + 3×N plan-card grid + "Explore all plans" quiet link.
4. **How it works:** three numbered steps (`01 FIND` / `02 FORK` / `03 GO`) as a horizontal itinerary using the §5.6 visual language (dots and rule).
5. **For creators:** one Sheet, 8/4 split, plum used only for the eyebrow and attribution preview; secondary button to `/creators`.
6. Footer.

### 6.2 Discover `/discover` and `/search`

- Title row: h1 "Find a plan to start from" + `md` search bar on the same row (desktop), stacked on mobile.
- Filter bar: region segmented control + sort (`Most forked` · `Shortest` · `Newest`) as a quiet select, right-aligned result count in mono.
- Grid: 3 columns ≥ 1100px, 2 ≥ 720px, 1 below.
- Empty results: empty state with "Clear filters" and 3 suggested plans.

### 6.3 Plan detail `/plans/{slug}`

- **Header block (8/4):** left: breadcrumb (`Discover / Europe / Granada`, mono), display plan title, meta line (`4 DAYS · APR 12–16 · GRANADA, SPAIN`, mono), tags, summary. Right: **Fork card** (Float, sticky at `top: 88px`): price-from, fork count, primary `lg` **Fork this plan** (label becomes *Sign in to fork* when signed out), secondary Share, and the one-line "No booking happens here" note.
- **Photo band:** single `--r-xl` framed 21:9 destination photo under the header block (not behind the title; titles never sit on imagery).
- **Body (8/4):** left: "Why this route works" (creator quote in Fraunces italic 24px, `--creator` rule on the left), then the itinerary (§5.6, comfortable) grouped by day with a sticky day-jump bar (`D1 D2 D3 D4`). Right: creator attribution (full), then the context rail (§5.7).
- The three colored cards (cream / navy / mint) are replaced by: creator block (rail) + quote (inline) + "Carry these into your fork" as a checklist Sheet within the left column.

### 6.4 Workspace `/workspace`, `/plans/{slug}/preview`

- Shared header + **workspace bar** (48px, `--surface-1`, bottom rule): breadcrumb `My trips / Granada after dark`, save state in mono (`SAVED 2m AGO`), collaborators avatars, Share (secondary), Export PDF (quiet).
- **Three-pane grid** (§4.2): left **plan sidebar** (Rail): trip facts (dates, group, budget, pace) as an editable definition list, then the preferences form. Center: day tabs + itinerary (compact). Right: context rail.
- Preview mode: the workspace bar shows a `READ-ONLY PREVIEW` status tag and a primary **Fork to edit**. No gradient banner.
- Light theme by default like every page; dark follows the toggle.

### 6.5 Creators `/creators`

- Hero (6/6, no gradient): headline *"Your route, **credited** wherever it travels."*; right: a live-looking plan card with the full attribution block visible, as proof of what creators get.
- Benefits: three columns, numbered in mono, no dividers.
- Quote: inline Fraunces italic, not a navy slab. Metrics chips carry `SAMPLE` tags.
- Submission: 5/7 split; form fields per §5.3; primary submit. Confirmation replaces the form with a Sheet linking to the generated plan.

### 6.6 Sign in `/signin`

Centered 440px Sheet on `--bg`: wordmark, h1 "Welcome back", one primary button "Continue as Ari Rivera (demo)", one-paragraph honest note, back link. Remove the split visual panel.

### 6.7 Compass `/prototype`

Compass adopts this system wholesale: delete its private tokens in `assets/compass.css` (`--accent`, `--bg`, `--font-display`, …) and map to role tokens; its hero photo and credits pattern become the reference for §5.5 imagery. The "Explore / Community" tabs become header nav items. Its FAQ uses the Rail surface with `details` rows.

---

## 7. Motion

- Durations: `--t-fast 120ms` (hover, press), `--t-base 200ms` (menus, tabs), `--t-slow 400ms` (image hover scale, drawer). Easing: `cubic-bezier(.2,.7,.2,1)`.
- Allowed motion: opacity, transform. No layout-property animation, no parallax, no rotating globe.
- Itinerary reorder/move: 200ms transform; the moved item flashes `--accent-tint` for 600ms.
- `prefers-reduced-motion: reduce` → all durations 0ms, skeleton pulse off, image hover scale off.

---

## 8. Accessibility (acceptance criteria)

- Text contrast ≥ 4.5:1 (≥ 3:1 for ≥ 24px) in both themes for every role pairing in §3.3; verified by a test that parses `tokens.css` role pairs.
- All interactive elements ≥ 44×44px touch target on coarse pointers.
- Visible focus (§3.4) on every focusable element; tab order follows visual order.
- Segmented controls use `role="radiogroup"`; day tabs use `role="tablist"`.
- Photos have meaningful `alt` naming the place; the route fallback is `aria-hidden` with the plan title in the link.
- Reflow at 320px width without horizontal scroll (WCAG 1.4.10) on every page.

---

## 9. Responsive breakpoints

| Name | Min width | Changes |
|------|-----------|---------|
| base | 0 | single column; header menu sheet; search stacked; context rail after itinerary |
| `sm` | 560px | 2-column card grid starts at 720 |
| `md` | 720px | 2-col cards; plan detail still single column; workspace = main + drawer rail |
| `lg` | 1100px | 3-col cards; 8/4 detail; workspace 3 panes |
| `xl` | 1400px | container stays 1200; workspace side panes widen to 300/360 |

---

## 10. Implementation plan

Each phase is independently shippable and keeps `python -m unittest discover -s tests -v` and the Node suites green.

| Phase | Scope | Files | Done when |
|-------|-------|-------|-----------|
| **P1 · Foundations** | Ship fonts; rewrite `tokens.css` as primitives + role tokens; `data-theme` on `<html>` with `bright`→`light` migration; delete dark `--font-sans: mono`; alias old token names to roles for one release | `assets/fonts/*`, `assets/fonts.css`, `assets/tokens.css`, `document()` in `main.py`, `assets/app.js` | Headlines render in Fraunces/Inter on a machine without them installed; contrast test passes |
| **P2 · Shared components** | `ui.py` helpers (header, footer, button, tag, search bar, plan card, itinerary, context rail, attribution, demo strip, icon); remove all inline `style=""` in `main.py` | `ui.py`, `assets/components.css`, `main.py`, `prototype_*.py` | `grep 'style="' main.py` is empty; icon-parity test passes |
| **P3 · Public pages** | Home, Discover/Search, Plan detail, Creators, Sign in per §6 | `assets/public.css`, `main.py` | A6, A7, A8, A10 closed; 320px reflow check passes |
| **P4 · Workspace** | Three-pane grid, compact itinerary, workspace bar, preview mode; drop forced dark | `assets/workspace.css`, `main.py` | A4 closed (no item title narrower than 200px at 1440); PDF snapshot unchanged in content |
| **P5 · Compass merge** | Map Compass private tokens to role tokens; shared header/footer | `assets/compass.css`, `assets/compass-views.mjs` | A1 closed: `/prototype` and `/` share header, type, and palette |
| **P6 · Imagery** | Destination photos for the four fixture plans + credits; route-card fallback | `assets/photos/plans/*`, `data.py` fixture fields | A9 closed; every photo has a credits entry |

Out of scope: new routes, new data fields beyond an optional `photo` key per plan, live providers, and any change to publishing/identity semantics (ADR-0001/0002).

---

## 11. Decision reference

| Question | Answer |
|----------|--------|
| Serif or sans for this title? | Fraunces only at ≥ 32px page/plan titles; otherwise Inter |
| Mono or sans? | Would it be right-aligned in a spreadsheet? → mono |
| Can I use orange here? | Only for the single primary action or a 2px indicator/`--accent-ink` text |
| Which yellow/orange token? | `--day` = yellow (days, featured). `--accent` = orange (action). There is no "sun" role |
| Card, rail, or float? | Content = Sheet; supporting context = Rail; overlays and sticky = Float |
| Is this data fake? | Put one `SAMPLE` tag in the panel head. No sentences |
| New color band for a section? | No. Use a photo or nothing |
| Dark mode layout change? | Never. Only surface/ink tokens change |
