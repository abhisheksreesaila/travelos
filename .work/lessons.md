- 2026-09-26 · Designer · Keep private-trip edits separate from editable public contributions; every public version must exclude private participants, notes, receipts, booking references and private history.
- 2026-09-26 · Designer · Preserve selected itinerary versions intact when forking; shorten through explicit manual block edits, never automatic pace compression.
- 2026-09-26 · Designer · Ensure creator previews contain only the stops reviewed in the preceding screen; reusing a generic itinerary can silently add unreviewed flights and hotels.
- 2026-09-26 · Designer · Validate required tool parameters before dispatching file creation; an empty call creates no artifact and wastes a review step.
- 2026-09-26 · Clarifier · For this visual revision, seek approval on only two representative screens before extending the style to all 24 states; preserve settled product behavior and reduce visual overload rather than merely adding color.
- 2026-09-26 · Designer · For TravelOS, pair playful functional color with compact tiles and progressively disclosed context; keep notes in a side drawer and retain the preferred system-sans heading, rather than adding more permanent panels.
- 2026-09-26 · Designer · Test reverse Tab from the first native-dialog control; add explicit first/last wrapping when focus escapes to browser chrome, and retain the original opener when switching drawer content.
- 2026-09-26 · Designer · Check secondary ink against every colored fill, not only paper; token-level contrast failures can emerge when new semantic tiles reuse muted text.
- 2026-09-26 · Designer · Use file-edit tools or a script file instead of shell-embedded JavaScript or long Markdown strings; dollar-prefixed selectors and nested quoting can be evaluated or broken by the shell.
- 2026-09-26 · Reviewer · Populate user-entered input values through DOM properties rather than interpolating text-escaped strings into quoted HTML attributes; test double-quote round trips because text-node escaping does not escape attribute delimiters.
- 2026-09-26 · Reviewer · Set explicit values for enumerated ARIA states such as aria-current; do not toggle them as boolean HTML attributes, since an empty value can hide a visually selected state from assistive technology.
- 2026-09-26 · Designer · Keep all TravelOS generated design artifacts, validation reports, screenshots and browser profiles in the active session files/.lavish directory, not the repository; preserve the cleaned source tree and use .work only for compact project memory.
- 2026-09-26 · Developer · Guard absent drawer openers before querying selectors; restored or programmatically opened drawers must fall back to a surviving focus target.
- 2026-09-26 · Developer · Treat missing arrangement IDs as unlinked, never as an equality group; deleting one public-fork hotel block must not delete every activity with an undefined candidate.
- 2026-09-26 · Developer · Preserve the complete local fragment, including candidate/version/drawer parameters, through demo sign-in; a page-only return target loses pending context.
- 2026-09-26 · Developer · Run browser regressions in a fresh document and send complete native key events; same-fragment navigation and incomplete CDP key codes can report stale or false failures.

- 2026-09-26 · Reviewer · Bind publication approval to an immutable payload or checked draft revision, and invalidate it on edits/history restoration; a stale preview must never approve the current mutable draft.

- 2026-09-26 · Developer · Use file-edit tools for JavaScript containing backticks; shell command substitution can corrupt a regression before it runs.
- 2026-09-26 · Developer · Probe specific executable paths instead of listing environment variables; broad environment inspection can expose secrets.
- 2026-09-26 · Developer · Reject absent preview approval before validating its payload; restoring an empty contribution drawer must show expiry rather than throw public-content validation errors.
- 2026-09-26 · Developer · Account for native date/time subfield tab stops in browser keyboard regressions; assert reaching named controls and Save rather than assuming one Tab per input.
- 2026-09-26 · Developer · Keep modal keyboard focus below sticky headings with scroll padding; test reopening a previously scrolled drawer at enlarged reflow.
- 2026-09-26 · Developer · Run shared-browser native-key/CDP walkthroughs sequentially or disable background throttling; background animation-frame status updates can otherwise produce false failures.
- 2026-09-27 · Designer · For the TravelOS readability revision, preserve Snap colors and tactile actions but use selective coding-font headings/labels, 16px minimum interface copy and progressive disclosure; this supersedes the earlier sans-heading preference for this iteration.
- 2026-09-27 · Designer · Wrap CDP evaluation declarations in an IIFE to avoid redeclaring persistent top-level lexical bindings across browser probes.
- 2026-09-27 · Designer · Focus a control before a programmatic click when checking modal return focus; HTMLElement.click() alone does not reproduce native pointer focus.
- 2026-09-27 · Developer · Disable HTTP cache in browser acceptance runs after changing ES modules; a fresh render alone can still execute cached application code.
- 2026-09-27 · Developer · Use an isolated extension-free Chromium binary/profile for network acceptance; distro browser wrappers can inject extension scripts into an otherwise local-only app. Diagnose exact URLs rather than weakening network assertions.
- 2026-09-27 · Developer · Measure worst-case wrapped titles with arrangement grips at narrow and column-breakpoint widths; reserve measured card height before placing the next clock-aligned event, including non-snapped times entered in fields.
- 2026-09-27 · Developer · Preserve native disclosure state in same-drawer rerenders as well as main-route rerenders; successful form actions must not collapse the active appearance/options controls.
- 2026-09-27 · Developer · Align calendar header rows across dense and regular days before placing clock lanes; additional day-heading controls must not offset the shared hour baseline.
- 2026-09-27 · Designer · For accepted Fieldwork/Snap, increase comparison density by reducing padding, gaps and stacked chrome, not by shrinking text below 16px or hiding named actions; lead rich family trips with compact day summaries while keeping the editable clock calendar available.
- 2026-09-27 · Developer · Treat the family outbound 11:30 United BUR value as arrival, not departure or ambiguous time; preserve supplied endpoint semantics separately from editable calendar placements.
- 2026-09-27 · Developer · Measure first-result position and the entire result region, not only row height; stacked search/header chrome can hide otherwise compact comparisons below the fold.
- 2026-09-27 · Developer · Scope browser assertions to the active form when import and author modes coexist; hidden source-form errors are not the current authoring result.
- 2026-09-27 · Developer · Copy browser harness dependencies together and identify the publication a test creates rather than the first record; additive demo seeds must not redirect revision tests to a different owner.

- 2026-09-27 · Reviewer · Render every allowlisted public field in the exact approval preview and published view regardless of fixture/demo tags; test non-demo imports whenever the public payload gains fields, so unreviewed wording cannot be silently published.
- 2026-09-27 · Developer · Test native disclosure activation with complete CDP keyboard events (Space down/up or Enter char) in the focused tab; never auto-open a details ancestor before clicking its summary, since that click closes it instead. Instrument event delivery before diagnosing a product failure.
- 2026-09-27 · Developer · When reusing a demo renderer for ordinary publications, keep fixture classifications conditional on the existing tag; shared presentation must not relabel normal contributions as synthetic demos.

- 2026-09-27 · Reviewer · When replacing a shared itinerary renderer with collapsed disclosures, verify every caller including Print/Save as PDF; interactive accessibility does not ensure exported documents include hidden endpoint details.
- 2026-09-27 · Developer · Keep full snapshot exports independent of native collapsible UI; explicitly render semantic complete content and regression-test actual PDF text, because closed disclosure descendants may not print even with CSS overrides.
- 2026-09-27 · Developer · Search every caller before replacing an import used by snapshots; live shared-view rendering may still need the original public-safe contribution helper.
- 2026-09-27 · Developer · Clear CDP media overrides after print screenshots before calling printToPDF; an explicit screen override makes the next PDF use screen styles and creates false navigation/privacy failures.
- 2026-09-27 · Developer · Derive snapshot zone assertions from the actual fixture: the authored Del Mar sample is California PDT, not legacy UTC.
- 2026-09-27 · Developer · Carry the explicit plan end into full snapshots, not just the last scheduled stop; trailing unscheduled days are itinerary information too.
- 2026-09-27 · Developer · Keep full snapshot stop descriptions in block flow rather than inherited compact flex rows; verify complete extracted PDF wording so interleaved columns cannot silently scramble details.
- 2026-09-29 · Clarifier · For the new TravelOS frontend milestone, supersede the old 16px-all-text and mono-led constraints: use narrower sans primary, 13–14px body, 12px secondary, selective mono metadata, desktop targets at least 24px and touch targets 44px; measure whole-page comparison density including close controls, preserve recoverable Fieldwork/Snap, and use designer judgment without another style interview.
- 2026-09-29 · DevOps · Parse both Node spec (ℹ tests) and TAP (# tests) summaries, or explicitly select a reporter; exit success alone does not validate the archived test count.
- 2026-09-29 · DevOps · Set the snapshot working directory explicitly before checksum checks; fresh tool shells start in the repository, and a later successful probe must not mask a failed archive verification.
- 2026-09-29 · Designer · Use route fragments distinct from DOM IDs in visual prototypes (for example #/search); native anchor scrolling can hide the header and invalidate above-fold density measurements.
- 2026-09-29 · Designer · Never move offscreen calendar anchors onto the first visible hour to make them fit; preserve the real clock offset or show a clearly untimed Earlier notice.
- 2026-09-29 · Designer · Do not fabricate loading for immediate local fixture refreshes; animate only genuine asynchronous loading and honor reduced motion.
- 2026-09-29 · Designer · Preselect neither consent nor simulation acknowledgment; verify the unchecked state blocks continuation and explicit selection enables it.
- 2026-09-29 · Designer · Use installed Lavish playbook names from CLI help; route diagrams to diagram and comparisons to slides rather than inventing a mockup playbook.

- 2026-09-28 · Developer · Exclude closed-details descendants (except its own summary) when computing dialog tab order; getClientRects alone can include invisible controls and break reverse-Tab.

- 2026-09-28 · Developer · Use the existing public sample vocabulary when importing fixture drafts; unsupported demo enum labels are correctly stripped by the privacy allowlist and lose truthful sample labeling.

- 2026-09-28 · Reviewer · Distinguish an absent optional numeric filter from an explicit zero; verify zero budgets in both adapter predicates and form round-trips so zero never becomes unlimited.
- 2026-09-28 · Reviewer · Give repeated dialog launchers unique stable identifiers and verify focus returns to each exact opener; a shared action selector restores focus to the first matching control.

- 2026-09-28 · Developer · Use the live sticky-summary rectangle when clearing keyboard focus; native tab scrolling can leave partially visible controls underneath sticky content.
- 2026-09-28 · Developer · Verify shared search chrome at 320px in every appearance; a correct sticky rule cannot bring an initially below-fold Save button into view.
- 2026-09-28 · Developer · Derive dialog wrap expectations from every visible control, including the shared Appearance disclosure; do not assume the form submit is last.
- 2026-09-28 · Developer · Wait for the scheduled animation frame before asserting post-focus geometry, and match actual user-facing capitalization in text assertions.
- 2026-09-28 · Developer · Set the project source path when testing an external editable environment; setuptools module lists may omit prototype-only modules.
