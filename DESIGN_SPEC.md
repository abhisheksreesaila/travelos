# TravelOS Visual Design Specification

**"GitHub for travel" — the lovechild of Omarchy Linux and colorful premium travel.**

---

## Table of Contents

1. [Typography System](#1-typography-system)
2. [Color System Refinements](#2-color-system-refinements)
3. [Surface & Border Language](#3-surface--border-language)
4. [Spacing & Layout Rhythm](#4-spacing--layout-rhythm)
5. [Interactive Details](#5-interactive-details)
6. [Key Page Treatments](#6-key-page-treatments)
7. [Motion & Transition Principles](#7-motion--transition-principles)

---

## 1. Typography System

### 1.1 Font Pairing

| Role | Font Stack | Purpose |
|------|-----------|---------|
| **Sans lead** | `'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif` | Headlines, card titles, marketing copy, CTAs, lede paragraphs |
| **Mono tool** | `'JetBrains Mono', 'Cascadia Code', 'Fira Code', ui-monospace, monospace` | Labels, metadata, inputs, data displays, keyboard hints, status indicators, timestamps, itinerary step numbers, breadcrumbs, URLs |

**The rule**: If it feels like "warmth and story," use sans. If it feels like "precision, code, or tooling," use mono. The interplay creates the identity.

### 1.2 Type Scale

```
┌─────────────────────────────────────────────────────────────┐
│  TOKEN          │ SIZE                    │ USAGE            │
├─────────────────────────────────────────────────────────────┤
│  --text-hero    │ clamp(48px, 6vw, 84px)  │ Hero headlines   │
│  --text-h1      │ clamp(38px, 5vw, 60px)  │ Page headlines   │
│  --text-h2      │ clamp(28px, 3.5vw, 44px)│ Section headers  │
│  --text-h3      │ 20px–24px              │ Card titles      │
│  --text-lede    │ clamp(16px, 1.55vw, 19px)│ Lede paragraphs │
│  --text-body    │ 16px                    │ Body copy        │
│  --text-small   │ 13px                    │ Secondary copy   │
│  --text-label   │ 10px                    │ Mono labels      │
│  --text-meta    │ 9px                     │ Timestamps, meta │
│  --text-micro   │ 8px                     │ Legal, footnotes │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Font-Weight Map

| Weight | Use Case |
|--------|----------|
| **850** (`font-weight: 850`) | Hero/h1/h2 headlines — maximum impact |
| **750** (`font-weight: 750`) | Button text, nav links, emphasized sans |
| **700** (`font-weight: 700`) | Card titles, section headings, strong emphasis |
| **600** (`font-weight: 600`) | Sub-headings, table headers |
| **400** (`font-weight: 400`) | Body copy, lede paragraphs |
| **800 (mono)** | Mono labels, keyboard hints, workflow steps |

### 1.4 Letter-Spacing Rules

```
--ls-hero:     -0.065em       (tight, dramatic headlines)
--ls-title:    -0.04em        (section titles, card titles)
--ls-normal:   0              (body text)
--ls-label:    0.09em         (mono uppercase labels — the Omarchy signature)
--ls-meta:     0.055em        (timestamps, meta data, breadcrumbs)
--ls-key:      0.07em         (keyboard shortcuts, status badges)
--ls-wide:     0.14em         (section eyebrow labels)
```

### 1.5 Line-Heights

```
--lh-heading:  0.98–1.03      (hero/h1/h2 — tight stack)
--lh-title:    1.12–1.2       (card titles, section heads)
--lh-body:     1.55           (body copy)
--lh-lede:     1.65           (lede paragraphs)
--lh-mono:     1.35–1.4       (mono text — tighter than sans)
--lh-label:    1.2            (mono labels)
```

### 1.6 Hierarchy Rules: When Sans vs Mono

**ALWAYS SANS (marketing-layer):**
- Hero headlines (`.p-title`, `h1`)
- Section headings (`h2`, `h3`)
- Card titles
- Lede paragraphs
- Button text
- Navigation links
- Body copy
- The "OS" suffix in the brand mark (color accent, sans weight)

**ALWAYS MONO (tool-layer):**
- Section eyebrow labels (`.p-eyebrow`)
- Field labels (`<label>`)
- Breadcrumbs
- Timestamps and dates
- "Day 01", "Day 02" markers
- Status indicators ("NOT RUN", "EXAMPLE", "PREVIEW ONLY")
- Keyboard hints (`⌘K`, `← →`)
- Live state readouts
- URL displays
- Metadata rows
- Footer legal text
- Workflow/stage indicators
- Input placeholder text (mixed: mono styling, sans fallback)
- Chip/badge text in tool contexts
- Itinerary step numbers

**THE INTERPLAY (where identity lives):**
- A page opens with a sans-serif warm headline
- Directly beneath it, a mono eyebrow or metadata line grounds it with precision
- Cards use sans for the human story, mono for the data points
- The contrast between a warm "A long weekend in Granada" and a precise `DAY 01 · OCT 09 · 10:30 AM` IS the brand

---

## 2. Color System Refinements

### 2.1 Core Palette

```
┌──────────────────────────────────────────────────────────────────┐
│  TOKEN            │ HEX       │ ROLE                             │
├──────────────────────────────────────────────────────────────────┤
│  --ink             │ #1A1C1E   │ Primary text, headers, icons     │
│  --ink-soft        │ #3D444B   │ Secondary headings, active nav   │
│  --muted           │ #5E6A75   │ Body text, meta, placeholders   │
│  --faint           │ #8B95A1   │ Disabled, very subtle text       │
│  --paper           │ #F5F2E8   │ Page background                  │
│  --card            │ #FFFDF7   │ Card/panel backgrounds           │
│  --surface-raised  │ #FFFEFA   │ Elevated surfaces, inputs        │
│  --line            │ #DED9CC   │ Borders, dividers                │
│  --line-subtle     │ #EAE6DD   │ Very subtle dividers             │
│  --chrome          │ #1A1C1E   │ Toolbars, status bars, code bg  │
│  --chrome-text     │ #D5D0C5   │ Text on chrome                   │
│  --chrome-muted    │ #8B867A   │ Secondary text on chrome         │
└──────────────────────────────────────────────────────────────────┘
```

**Key change from current**: `--p-ink` darkens from `#202B39` to `#1A1C1E`. This creates stronger contrast against the warm paper and makes the terminal/chrome elements feel more authoritative. The paper stays at `#F5F2E8` — warm but not yellow.

### 2.2 Accent Colors

```
┌──────────────────────────────────────────────────────────────────┐
│  TOKEN            │ HEX       │ PURPOSE                          │
├──────────────────────────────────────────────────────────────────┤
│  --accent-orange  │ #F0643D   │ Primary CTA, active states,       │
│                   │           │ highlights, "warmth" signal       │
│  --accent-plum    │ #7357D8   │ Focus rings, creator context,     │
│                   │           │ "precision/intelligence" signal   │
│  --accent-mint    │ #76D7B1   │ Success, complete states,         │
│                   │           │ kid-friendly, "easy/safe" signal │
│  --accent-sky     │ #63C7E7   │ Information, illustrations,       │
│                   │           │ previews, "discovery" signal     │
│  --accent-sun     │ #FFD257   │ Warnings, highlights, badges,     │
│                   │           │ day markers, "joy/warmth" signal │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Accent Usage Rules

| Accent | Use For | Never Use For |
|--------|---------|---------------|
| **Orange** | Primary buttons (traveler), active indicators, price/saving highlights, key CTA links, breadcrumb current step | Large background areas, text on dark backgrounds, error states |
| **Plum** | Focus rings globally, creator-studio elements, "intelligence/AI" badges, `is-active` on variant selectors | Primary traveler CTAs (use orange), success states |
| **Mint** | Complete/success states, kid-mode toggle (ON), eco/sustainable badges, "verified" indicators | Primary CTAs, text that needs high contrast |
| **Sky** | Information cards, preview badges, illustration accents, discovery context, "sample" badges | Critical alerts, destructive actions |
| **Sun** | Day markers, warning badges, brand mark, highlighted chips, "featured" indicators, `is-active` day selectors | Primary CTAs (use orange), error states |

### 2.4 Contrast Rules (WCAG AA minimum)

```
--ink on --paper:          contrast ratio ~14.5:1  ✓ AAA
--ink on --card:           contrast ratio ~14.8:1  ✓ AAA
--muted on --paper:        contrast ratio ~5.2:1   ✓ AA
--muted on --card:         contrast ratio ~5.4:1   ✓ AA
white on --chrome:         contrast ratio ~14.2:1  ✓ AAA
white on --accent-orange:  contrast ratio ~3.8:1   ✗ — NEVER use white text on orange
white on --accent-plum:    contrast ratio ~5.1:1   ✓ AA (use for badges only, ≥10px)
--ink on --accent-sun:     contrast ratio ~10.8:1  ✓ AAA
```

**Critical rule**: White text may ONLY appear on `--chrome` (`#1A1C1E`), `--accent-plum` (badges/labels ≥10px), or `--accent-orange` at large sizes (≥18px bold). Never use white text on `--accent-mint` or `--accent-sky`.

### 2.5 Surface Layering

```
Layer 0:  --paper          #F5F2E8   (page background)
Layer 1:  --card           #FFFDF7   (cards, panels)
Layer 2:  --surface-raised #FFFEFA   (inputs, elevated cards)
Layer 3:  --chrome         #1A1C1E   (toolbars, status bars)
Layer 4:  Modal backdrop   rgba(26, 28, 30, 0.5)
```

Depth is communicated through:
1. **Background color darkening**: paper → card → surface-raised (very subtle)
2. **Chrome inversion**: chrome elements are dark-on-warm, creating maximum distinction
3. **Border presence**: only at layer boundaries that need explicit separation

### 2.6 Accent Background Tints (for chips, badges, banners)

```
--tint-orange:  #FFF0EB   (orange at ~8% opacity on paper)
--tint-plum:    #F0EAFF   (plum at ~8% opacity on paper)
--tint-mint:    #E8F8F0   (mint at ~12% opacity on paper)
--tint-sky:     #E8F6FA   (sky at ~12% opacity on paper)
--tint-sun:     #FFF8DC   (sun at ~15% opacity on paper)
```

---

## 3. Surface & Border Language

### 3.1 Core Principle: Borders Are a Last Resort

The default is NO borders. Visual separation comes from:
- Background color shifts (paper → card → surface-raised)
- Typographic hierarchy
- Generous spacing
- Subtle shadows for elevation (not decoration)

When borders ARE needed, they follow a strict hierarchy.

### 3.2 Border Scale

```
┌──────────────────────────────────────────────────────────────┐
│  TOKEN                 │ VALUE                                │
├──────────────────────────────────────────────────────────────┤
│  --border-none         │ none (default)                       │
│  --border-hairline     │ 1px solid var(--line-subtle)         │
│  --border-divider      │ 1px solid var(--line)               │
│  --border-input        │ 1px solid #D4CFC2 (slightly darker) │
│  --border-accent       │ 1px solid var(--ink)                │
│  --border-focus        │ 1px solid var(--accent-plum)         │
│  --border-error        │ 1px solid var(--accent-orange)      │
│  --left-rule           │ 3px solid var(--accent-orange)       │
│  --left-rule-plum      │ 3px solid var(--accent-plum)        │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Panel Treatment: The Three Panel Types

**Type 1: Card (default content container)**
```css
background: var(--card);
border: var(--border-hairline);
border-radius: var(--radius-card);
padding: 24px;
box-shadow: 0 2px 12px rgba(26, 28, 30, 0.06);
```

**Type 2: Panel (tool/work area)**
```css
background: var(--card);
border: var(--border-divider);
border-left: var(--left-rule);     /* The Omarchy terminal accent */
border-radius: var(--radius-panel);
padding: 24px;
/* NO box-shadow — flat, precise, tool-like */
```

**Type 3: Chrome Panel (dark toolbar/status area)**
```css
background: var(--chrome);
color: var(--chrome-text);
border: none;
border-radius: var(--radius-chrome);
padding: 12px 16px;
font-family: var(--p-mono);
font-size: --text-label;
```

### 3.4 Input Styling: CLI-Prompt Inspired

The signature TravelOS input feels like a beautiful terminal prompt:

```css
background: var(--surface-raised);
border: var(--border-input);
border-radius: var(--radius-input);
padding: 12px 16px;
font-family: var(--p-mono);   /* Mono for inputs — tool layer */
font-size: 14px;
color: var(--ink);
```

**Focus state** — the "active prompt" feel:
```css
border-color: var(--accent-plum);
box-shadow: 0 0 0 3px rgba(115, 87, 216, 0.12);
background: #FFFFFF;   /* Brightens slightly */
```

**Placeholder text** — the "dim comment" feel:
```css
color: var(--faint);
font-style: italic;    /* Differentiates from entered text */
```

**The URL input (creator studio)** — the most terminal-like:
```css
font-family: var(--p-mono);
font-size: 13px;
letter-spacing: 0.02em;
background: #FBFAF6;   /* Slightly cooler than surface-raised */
border-color: var(--line);
/* Prefix with a subtle ">" or protocol monogram in the design */
```

### 3.5 Terminal Accent Details

**Status Bar (chrome strip)**
- Full-width, dark background (`#1A1C1E`)
- Mono type, 10px, uppercase
- Padding: `8px 16px`
- Example: "READY · SYNTHETIC · MEMORY-ONLY" in `--chrome-muted` with current stage in `--chrome-text`

**Scanline/Grid Background (subtle, in tool areas only)**
```css
background-image:
  linear-gradient(rgba(26, 28, 30, 0.02) 1px, transparent 1px);
background-size: 100% 4px;
```
Applied ONLY to `.creator-transcript`, `.creator-plan-panel`, and `.p-itinerary-board` — never to marketing surfaces.

**Left-Rule Accent**
- 3px solid border on the left side of tool panels
- Color varies by context: orange (default), plum (creator), mint (success/complete)
- This is the single strongest Omarchy signal — it frames tool content with a terminal-like gutter

**Prompt-Styled Labels**
Field labels in tool areas get this treatment:
```css
font-family: var(--p-mono);
font-size: 10px;
font-weight: 700;
color: var(--muted);
letter-spacing: var(--ls-label);
text-transform: uppercase;
```
With an optional `::before` pseudo-element adding a subtle `>` or `$` prompt character in `--faint`.

**Workflow/Stage Indicators**
```css
display: flex;
align-items: center;
gap: 12px;
font-family: var(--p-mono);
font-size: 9px;
text-transform: uppercase;
```
Each stage: numbered circle (dark when current, mint when complete, line-colored when pending), connected by 1px lines.

### 3.6 Border-Radius Scale

```
--radius-sm:      4px    (keyboard hints, tiny badges, inline code)
--radius-md:      6px    (chips, small buttons, day selectors)
--radius-input:   8px    (inputs, select dropdowns)
--radius-button:  8px    (buttons, interactive elements)
--radius-card:    10px   (cards, panels)
--radius-chrome:  6px    (chrome strips — tighter, more tool-like)
--radius-lg:      14px   (hero illustrations, feature cards)
--radius-xl:      24px   (large illustration frames)
```

---

## 4. Spacing & Layout Rhythm

### 4.1 Grid System

```css
--grid-columns: 12;
--grid-gap:     24px;
--grid-gap-sm:  16px;
--grid-gap-lg:  32px;
--content-max:  1320px;    /* max-width of .p-container */
--content-narrow: 820px;   /* max-width for reading/hero copy */
--content-sidebar: 300px;  /* standard sidebar width */
```

### 4.2 Section Spacing

```
┌───────────────────────────────────────────────────────────┐
│  TOKEN              │ VALUE          │ USAGE              │
├───────────────────────────────────────────────────────────┤
│  --space-section    │ clamp(48px, 6vw, 80px) │ Major sections │
│  --space-block      │ 32px–48px     │ Content blocks      │
│  --space-component  │ 24px           │ Between components  │
│  --space-element    │ 16px           │ Between elements    │
│  --space-tight      │ 8px–12px      │ Related items       │
│  --space-micro      │ 4px–6px       │ Icon-label gaps     │
└───────────────────────────────────────────────────────────┘
```

### 4.3 Marketing vs Tool Spacing

| Context | Section Spacing | Internal Density | Border Usage |
|---------|----------------|-----------------|--------------|
| **Marketing** (home hero, discover, plan intro) | Generous (`--space-section`) | Airy, lots of white space | Minimal — shadows for depth |
| **Tool** (creator panels, workspace controls, itinerary editor) | Compact (`24px–40px`) | Dense but organized, mono rhythm | Left-rules, subtle dividers |
| **Hybrid** (plan detail, sign-in) | Moderate | Sans-led with mono data accents | Hairline borders on cards |

**The rule**: Marketing sections breathe. Tool sections hum. The transition between them — a hero headline flowing into a mono status bar — IS the TravelOS feel.

### 4.4 Container Padding

```css
/* Desktop */
.p-container {
  width: min(var(--content-max), calc(100% - 64px));
  margin-inline: auto;
}

/* Tablet (<900px) */
.p-container {
  width: min(var(--content-max), calc(100% - 40px));
}

/* Mobile (<680px) */
.p-container {
  width: calc(100% - 36px);
}
```

### 4.5 Header Dimensions

```
Header height:        72px (sticky, top: 0)
Demo banner height:   39px
Combined offset:      111px (used for scroll-margin-top)
```

---

## 5. Interactive Details

### 5.1 Button Hierarchy

**Primary Button (charcoal, authoritative)**
```css
background: var(--ink);              /* #1A1C1E */
color: #FFFFFF;
border: none;
border-radius: var(--radius-button); /* 8px */
padding: 12px 24px;
min-height: 48px;
font-family: var(--p-sans);
font-size: 14px;
font-weight: 750;
letter-spacing: -0.01em;
box-shadow: 0 2px 0 rgba(0, 0, 0, 0.2);
transition: background-color 150ms ease, transform 120ms ease, box-shadow 150ms ease;
```
Hover: `background: #2D3033; transform: translateY(-1px); box-shadow: 0 3px 0 rgba(0, 0, 0, 0.2);`
Active: `background: #0D0E0F; transform: translateY(0); box-shadow: 0 1px 0 rgba(0, 0, 0, 0.2);`

**Primary Button (orange, traveler warmth)** — used for traveler CTAs
```css
background: var(--accent-orange);    /* #F0643D */
color: #FFFFFF;
/* ... same structure as above */
box-shadow: 0 2px 0 #C84B2B;
```
Hover: `background: #E05A36;`
Active: `background: #C84B2B;`

**Secondary Button (sun, warm highlight)**
```css
background: var(--accent-sun);       /* #FFD257 */
color: var(--ink);
border: none;
box-shadow: 0 2px 0 #DDB847;
```
Hover: `background: #FFDA6B;`
Active: `background: #E8C04A;`

**Ghost Button (border, neutral)**
```css
background: transparent;
color: var(--ink);
border: var(--border-hairline);
/* No shadow */
```
Hover: `background: rgba(26, 28, 30, 0.04); border-color: var(--line);`
Active: `background: rgba(26, 28, 30, 0.08);`

**Chrome Button (on dark backgrounds only)**
```css
background: rgba(255, 255, 255, 0.1);
color: var(--chrome-text);
border: 1px solid rgba(255, 255, 255, 0.12);
```
Hover: `background: rgba(255, 255, 255, 0.18);`

### 5.2 Focus States

**Global focus-visible (all interactive elements)**
```css
*:focus-visible {
  outline: 3px solid var(--accent-plum);
  outline-offset: 3px;
  border-radius: 2px;
}
```

**Input focus (the "active prompt")**
```css
border-color: var(--accent-plum);
box-shadow: 0 0 0 3px rgba(115, 87, 216, 0.12);
background: #FFFFFF;
```

**Skip link**
```css
position: fixed;
z-index: 100;
top: -80px;
left: 12px;
padding: 10px 14px;
border-radius: var(--radius-md);
color: #FFFFFF;
background: var(--ink);
```
Focus: `top: 12px;`

### 5.3 Keyboard Shortcut Hints

```css
.kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 6px;
  border-radius: var(--radius-sm);         /* 4px — tight, keycap-like */
  background: var(--surface-raised);
  border: var(--border-hairline);
  font-family: var(--p-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0;
  line-height: 1;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.08); /* subtle keycap depth */
}
```

Usage: `⌘K`, `← →`, `ESC` — always rendered with the `.kbd` treatment.

### 5.4 Status Indicators & Badges

**Status Badge (mono, uppercase, tight)**
```css
display: inline-flex;
align-items: center;
padding: 4px 8px;
border-radius: var(--radius-sm);
font-family: var(--p-mono);
font-size: 8px;
font-weight: 800;
letter-spacing: 0.1em;
text-transform: uppercase;
line-height: 1.2;
```

Color variants:
- `.is-not-run`: `color: var(--faint); background: var(--line-subtle);`
- `.is-example`: `color: #216279; background: var(--tint-sky);`
- `.is-complete`: `color: #246848; background: var(--tint-mint);`
- `.is-live`: `color: var(--accent-orange); background: var(--tint-orange);`
- `.is-preview`: `color: #5C43B5; background: var(--tint-plum);`

**Status Dot (inline, pulsing for "live")**
```css
width: 8px;
height: 8px;
border-radius: 50%;
background: var(--accent-orange);
```
With animation for "live" state:
```css
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
animation: pulse-dot 2s ease-in-out infinite;
```

### 5.5 Chips (Mono, Compact)

```css
.p-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
  padding: 5px 10px;
  border-radius: var(--radius-md);   /* 6px */
  font-family: var(--p-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.025em;
  line-height: 1.3;
}
```

Color variants use the accent tints (see 2.6):
- `.is-sun`: `background: var(--tint-sun); color: var(--ink);`
- `.is-mint`: `background: var(--tint-mint); color: #246848;`
- `.is-sky`: `background: var(--tint-sky); color: #216279;`
- `.is-plum`: `background: var(--tint-plum); color: #5C43B5;`
- `.is-orange`: `background: var(--tint-orange); color: #943B22;`

### 5.6 Hover States

All interactive elements should feel responsive:

| Element | Hover Effect |
|---------|-------------|
| Primary button | Background darkens, lifts 1px |
| Ghost button | Light background wash appears |
| Nav link | Color shifts to `--ink`, `--paper` background |
| Card (clickable) | Shadow deepens slightly, no transform |
| Day selector | Border darkens, subtle background tint |
| Input | Border stays but brightens slightly |
| Link in body text | Underline appears, `text-underline-offset: 3px` |
| Chip | No hover (they're labels, not buttons) |
| Icon button | Color shifts to accent |

### 5.7 Selection States

**Day selector (workspace):**
- Default: `background: var(--surface-raised); border: var(--border-hairline);`
- Hover: `border-color: var(--line); background: #FFFEFA;`
- Active/Selected: `border-color: var(--ink); background: var(--tint-sun); box-shadow: 2px 2px 0 var(--ink);`

**Nav link:**
- Default: `color: var(--muted);`
- Hover: `color: var(--ink); background: var(--paper);`
- Active: `color: var(--ink); background: #F0E8D0;` (warmer paper tint)

**Kid-mode toggle:**
- Off: `border-color: #C9DFD3; background: var(--tint-mint);`
- On (pressed): `border-color: var(--accent-plum); background: var(--tint-plum);`

---

## 6. Key Page Treatments

### 6.1 Home Hero

**Layout**: Two-column grid (`1fr 0.95fr`), generous gap (`clamp(36px, 6vw, 80px)`), min-height `470px`.

**Left (copy)**:
- Mono eyebrow: `font: 700 10px/1.5 var(--p-mono); letter-spacing: 0.105em; color: #5A6673;` with orange dot `::before`
- Sans hero title: `font-size: clamp(48px, 6vw, 84px); font-weight: 850; line-height: 0.98; letter-spacing: -0.065em;` — em element in orange (`#F0643D`)
- Sans lede: `max-width: 590px; color: var(--muted); font-size: clamp(16px, 1.55vw, 19px); line-height: 1.65;`
- CTA row: Primary (orange) + Secondary (sun), `gap: 12px; margin-top: 29px;`
- Trust line: Mono 9px, uppercase, `color: #65717B; letter-spacing: 0.04em;`

**Right (illustration)**:
- SVG illustration with `border: 1px solid rgba(26, 28, 30, 0.09); border-radius: var(--radius-xl);`
- Floating "postcard" element: `position: absolute; right: -8px; bottom: 38px; border: 1px solid var(--line); background: var(--card); box-shadow: 4px 5px 0 var(--ink);` — this is a key brand element: the postcard as physical artifact in a digital space
- Art caption: Mono 9px, `letter-spacing: 0.06em;`

**The Feel**: Warm marketing landing with precise tool details embedded. The postcard floating over the illustration, the mono trust line beneath the sans CTA — this is where sans warmth and mono precision first meet.

### 6.2 Creator Studio (Most Terminal-Like)

**Hero**: Three-part row: eyebrow with orange dot + title + simulation stamp (right-aligned).

**Source Panel**: The primary tool surface.
- Left-rule accent (orange, 3px)
- Label: mono, uppercase, 10px
- URL input: mono font, `background: #FBFAF6;` (cooler paper)
- The input IS the CLI — entering a URL should feel like typing a command
- Help text: 10px mono below input
- Error state: `border-left: 3px solid var(--accent-orange); background: var(--tint-orange);`

**Workflow Strip**: Mono, uppercase, centered.
- Connected steps: numbered circles (dark when current, mint when complete)
- Connected by 1px horizontal lines
- This is the terminal pipeline metaphor made visual

**Transcript Panel**: The most code-like surface.
- Left-rule accent (plum, 3px)
- Subtle scanline/grid background
- Mono timestamp + excerpt pairs
- Source URL display in a dark pill: `background: #F4F2EC; border-radius: 7px; font-family: var(--p-mono);`
- "NOT RUN" badge: faint on line-subtle

**Plan/Itinerary Panel**: 
- Left-rule accent (mint, 3px)
- Editable title field
- Day cards with mono step numbers
- Preview button triggers a slide-in or expand

**Live State Readout** (bottom):
- Dark chrome strip: `background: var(--chrome); color: var(--chrome-text);`
- JSON-like state display in mono
- "Ready." status in `--chrome-text`, active state pulses

### 6.3 Workspace — Day Panels and Controls

**Sidebar Controls**:
- Card with no shadow, hairline border
- Mono field labels
- Inputs styled as CLI prompts
- Date input, number selects, pace dropdown
- Kid-mode global toggle: pill with sun/mint → plum state change

**Day Selector Row**:
- Grid of 3 buttons, each showing: `DAY 0X` (mono, orange) + title (sans, 10px) + date (mono, 8px)
- Active state: `border-color: var(--ink); background: var(--tint-sun); box-shadow: 2px 2px 0 var(--ink);`

**Selected Day Panel**:
- Large, tonal background (tint-sun, tint-plum, tint-mint by day tone)
- Mono eyebrow: area label
- Orange time display: `font: 800 11px var(--p-mono);`
- Sans title: 25px, `letter-spacing: -0.04em;`
- Stop line: orange dot + bold place name
- Body copy in muted
- Kid tag: `background: #D1F0E0; color: #315848; font: 8px var(--p-mono);`
- Day action button: full-width, border-top divider, "Show kid-friendly swaps" with orange arrow

**Live State Bar** (sticky, bottom):
```css
position: sticky;
bottom: 94px;  /* above variant bar */
background: var(--card);
border: 1px solid #C8C4B8;
border-radius: 5px;
font: 9px/1.4 var(--p-mono);
color: #46515C;
box-shadow: 0 3px 10px rgba(26, 28, 30, 0.09);
```

### 6.4 Plan/Itinerary Display

**Breadcrumb**: Mono 10px, `color: var(--muted);` current step in orange.

**Plan Hero**: Two-column grid, illustration + copy.
- Left-rule variant: the illustration gets a `border-radius: var(--radius-xl);` and sometimes a colored shadow (`box-shadow: 8px 8px 0 var(--accent-mint);`)
- Floating sticker element: rotated mono label over the illustration corner

**Day Row (timeline)**:
```
[Day Marker Circle] — [Meta Row] — [Stamp]
    |                  [Title]
    |                  [Stop Line: Time · Place]
    |                  [Copy]
    |                  [Kid Copy (hidden)]
```
- Day marker: numbered circle with sun/plum/mint background, 35px, mono 10px
- Vertical line connecting markers: `1px solid var(--line)`
- Meta: `font: 9px var(--p-mono); color: var(--muted); letter-spacing: 0.04em;`
- Time: orange, mono
- Stop dot: 7px orange circle
- Copy: 13px sans, muted
- Stamp: faded mono number, decorative

**Sidebar**:
- Weather card: `background: var(--tint-sun);` with large temp in mono
- Source attribution: card with avatar circle (plum background, white mono initials)
- Disclaimer: mint-tinted card with icon

**Fork Banner**: Full-width dark strip.
```css
background: var(--chrome);     /* #1A1C1E */
color: #FFFDF7;
border-radius: 9px;
padding: 22px 25px;
```
Eyebrow in `--chrome-muted`, title in white, body in `--chrome-muted`.

### 6.5 Discover Page

**Search Form**: Card-wrapped, icon + borderless input + primary button.
```css
background: var(--card);
border: var(--border-hairline);
border-radius: 9px;
padding: 16px;
```
The search input itself: `border: 0; background: transparent;` — the card provides the container, the input is bare.

**Mood/Filter Chips**: Row of mono chips, separated by `1px solid var(--line)` above and below.

**Plan Grid**: Responsive auto-fit grid, `gap: 18px`. Cards have hairline border, no shadow by default — shadow appears on hover.

**Empty State**: Centered, dashed border (`1px dashed var(--line)`), sun icon in circle, friendly copy.

### 6.6 Sign-In Page

**Two-Column**: Illustration + persona panel.
- Persona card: `border: 1px solid var(--line); background: var(--card);`
- Avatar circle: plum background, white mono initials, 42px
- Continue button: full-width, primary (orange), arrow on right
- "No account" notice: grid of mono numbers + sans explanations, `border-top: 1px solid var(--line);`
- Boundary badges: mono 8px, tint-mint background pills

---

## 7. Motion & Transition Principles

### 7.1 The Duality of Motion

TravelOS motion exists on a spectrum:

```
Warm & Smooth ←————————————————————→ Precise & Snappy
(Marketing surfaces)                  (Tool surfaces)
```

- **Marketing transitions** (hero reveals, card hovers, page enters): smooth, eased, 200–300ms
- **Tool transitions** (panel opens, state changes, input focus): crisp, immediate, 120–180ms
- **Terminal accents** (status updates, workflow advances): near-instant, 80–120ms, sometimes with a subtle "blink"

### 7.2 Transition Tokens

```css
--ease-out:     cubic-bezier(0.16, 1, 0.3, 1);     /* smooth deceleration */
--ease-in-out:  cubic-bezier(0.65, 0, 0.35, 1);    /* symmetric, polished */
--ease-spring:  cubic-bezier(0.34, 1.56, 0.64, 1); /* slight overshoot — for joyful micro-interactions */
--ease-snap:    cubic-bezier(0.22, 0.61, 0.36, 1); /* tool-like, no overshoot */

--duration-instant:  80ms;
--duration-fast:     120ms;
--duration-normal:   180ms;
--duration-slow:     250ms;
--duration-glide:    350ms;
```

### 7.3 Specific Motion Rules

| Interaction | Duration | Easing | Behavior |
|------------|----------|--------|----------|
| Button hover lift | 120ms | ease-out | `translateY(-1px)` — subtle, never bouncy |
| Button press | 80ms | ease-snap | `translateY(0)` — immediate return |
| Card hover (shadow) | 200ms | ease-out | Shadow deepens, no transform |
| Input focus | 150ms | ease-out | Border color + box-shadow fade in |
| Panel expand/collapse | 200ms | ease-in-out | Max-height or grid-row animation |
| Page section enter | 300ms | ease-out | Fade-up: `opacity 0→1, translateY(8px→0)` |
| Day panel switch | 180ms | ease-snap | Quick crossfade or slide |
| Status badge change | 100ms | ease-snap | Color swap, no movement |
| Workflow step advance | 150ms | ease-snap | Circle color + connecting line fill |
| Share dialog open | 250ms | ease-spring | Scale from 0.95 + fade in — slight pop |

### 7.4 The "Terminal Blink"

For live/active status indicators in tool areas:
```css
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
```
Applied to the live-state dot or cursor-like element. Duration: 1s, step-end timing (hard on/off, like a terminal cursor).

### 7.5 Page Transitions

When navigating between pages in the prototype:
- **Marketing → Marketing** (home → discover): 300ms ease-out fade
- **Marketing → Tool** (discover → creator studio): 250ms — the transition itself feels like entering a different mode
- **Within Tool** (creator variant switch): 150ms snap — immediate, purposeful

### 7.6 Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 7.7 The "Feel" Summary

- **On marketing pages**: Movements are smooth and warm. Buttons lift gently. Cards breathe. The user should feel welcomed, not rushed.
- **On tool pages**: Movements are precise and confident. State changes snap. Inputs respond instantly. The user should feel capable, in control.
- **The transition between**: Moving from a warm hero into a dark chrome status bar should feel like stepping from a sunlit plaza into a focused workspace. Both are TravelOS. The contrast is the point.

---

## Appendix A: CSS Custom Properties Master List

```css
:root {
  /* === COLOR: NEUTRALS === */
  --ink:              #1A1C1E;
  --ink-soft:         #3D444B;
  --muted:            #5E6A75;
  --faint:            #8B95A1;
  --paper:            #F5F2E8;
  --card:             #FFFDF7;
  --surface-raised:   #FFFEFA;
  --line:             #DED9CC;
  --line-subtle:      #EAE6DD;
  --chrome:           #1A1C1E;
  --chrome-text:      #D5D0C5;
  --chrome-muted:     #8B867A;

  /* === COLOR: ACCENTS === */
  --accent-orange:    #F0643D;
  --accent-plum:      #7357D8;
  --accent-mint:      #76D7B1;
  --accent-sky:       #63C7E7;
  --accent-sun:       #FFD257;

  /* === COLOR: TINTS === */
  --tint-orange:      #FFF0EB;
  --tint-plum:        #F0EAFF;
  --tint-mint:        #E8F8F0;
  --tint-sky:         #E8F6FA;
  --tint-sun:         #FFF8DC;

  /* === TYPOGRAPHY: FAMILIES === */
  --p-mono:           'JetBrains Mono', 'Cascadia Code', 'Fira Code', ui-monospace, monospace;
  --p-sans:           'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;

  /* === TYPOGRAPHY: SCALE === */
  --text-hero:        clamp(48px, 6vw, 84px);
  --text-h1:          clamp(38px, 5vw, 60px);
  --text-h2:          clamp(28px, 3.5vw, 44px);
  --text-h3:          20px;
  --text-lede:        clamp(16px, 1.55vw, 19px);
  --text-body:        16px;
  --text-small:       13px;
  --text-label:       10px;
  --text-meta:        9px;
  --text-micro:       8px;

  /* === TYPOGRAPHY: LETTER-SPACING === */
  --ls-hero:          -0.065em;
  --ls-title:         -0.04em;
  --ls-normal:        0;
  --ls-label:         0.09em;
  --ls-meta:          0.055em;
  --ls-key:           0.07em;
  --ls-wide:          0.14em;

  /* === TYPOGRAPHY: LINE-HEIGHT === */
  --lh-heading:       0.98;
  --lh-title:         1.15;
  --lh-body:          1.55;
  --lh-lede:          1.65;
  --lh-mono:          1.35;
  --lh-label:         1.2;

  /* === BORDERS === */
  --border-hairline:  1px solid var(--line-subtle);
  --border-divider:   1px solid var(--line);
  --border-input:     1px solid #D4CFC2;
  --border-accent:    1px solid var(--ink);
  --border-focus:     1px solid var(--accent-plum);
  --border-error:     1px solid var(--accent-orange);
  --left-rule:        3px solid var(--accent-orange);
  --left-rule-plum:   3px solid var(--accent-plum);
  --left-rule-mint:   3px solid var(--accent-mint);

  /* === BORDER-RADIUS === */
  --radius-sm:        4px;
  --radius-md:        6px;
  --radius-input:     8px;
  --radius-button:    8px;
  --radius-card:      10px;
  --radius-chrome:    6px;
  --radius-lg:        14px;
  --radius-xl:        24px;

  /* === SPACING === */
  --space-section:    clamp(48px, 6vw, 80px);
  --space-block:      40px;
  --space-component:  24px;
  --space-element:    16px;
  --space-tight:      10px;
  --space-micro:      5px;

  /* === LAYOUT === */
  --content-max:      1320px;
  --content-narrow:   820px;
  --content-sidebar:  300px;
  --grid-gap:         24px;
  --grid-gap-sm:      16px;
  --grid-gap-lg:      32px;

  /* === SHADOWS === */
  --shadow-card:      0 2px 12px rgba(26, 28, 30, 0.06);
  --shadow-card-hover: 0 4px 20px rgba(26, 28, 30, 0.10);
  --shadow-button:    0 2px 0 rgba(0, 0, 0, 0.2);
  --shadow-dialog:    0 12px 35px rgba(26, 28, 30, 0.18);
  --shadow-tool:      2px 2px 0 var(--ink);

  /* === MOTION === */
  --ease-out:         cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out:      cubic-bezier(0.65, 0, 0.35, 1);
  --ease-spring:      cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-snap:        cubic-bezier(0.22, 0.61, 0.36, 1);
  --duration-instant: 80ms;
  --duration-fast:    120ms;
  --duration-normal:  180ms;
  --duration-slow:    250ms;
  --duration-glide:   350ms;
}
```

---

## Appendix B: Quick Decision Reference

| Situation | Answer |
|-----------|--------|
| Sans or mono for this label? | Is it data/precision? Mono. Is it warmth/story? Sans. |
| Border or no border? | No border. Use background shift or shadow. If unavoidable, hairline. |
| Which accent color? | Orange = warmth/action. Plum = precision/intelligence. Mint = success/safe. Sky = info/discovery. Sun = joy/highlight. |
| Shadow or flat? | Marketing: subtle shadow. Tool: flat with left-rule. Chrome: flat, dark. |
| Rounded or sharp? | Marketing: softer (8–14px). Tool: tighter (4–8px). Chrome: tight (6px). |
| Animation speed? | Marketing: slow–normal (200–300ms). Tool: fast–instant (80–150ms). |

---

*This specification is the single source of truth for TravelOS visual design. All implementation decisions should be checked against this document. When in doubt, return to the core thesis: warm where it tells a story, precise where it becomes a tool.*