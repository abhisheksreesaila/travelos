"""Three throwaway creator-flow layouts for the TravelOS UI prototype.

Three structurally different creator prototypes share the /creators?variant=A
host route; this module returns page content only, not a document or shell.
"""

from html import escape


_SAMPLE_DAYS = (
    (
        ("Mirador de San Nicolás", "Sunset · Albaicín", "00:24"),
        ("Calle Calderería Nueva", "Tea and pastries", "00:41"),
    ),
    (
        ("Alhambra & Generalife", "Go early · timed entry", "01:12"),
        ("Realejo lunch stop", "Easy afternoon reset", "01:46"),
    ),
    (
        ("Parque de las Ciencias", "Hands-on family morning", "02:08"),
        ("Carrera del Darro", "Slow final stroll", "02:32"),
    ),
)


def _icon(name: str, size: int = 22) -> str:
    paths = {
        "link": '<path d="M10 13a5 5 0 0 0 7.1 0l3-3A5 5 0 0 0 13 2.9l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.1 0l-3 3A5 5 0 0 0 11 21.1l1.7-1.7"/>',
        "play": '<path d="m8 5 11 7-11 7V5Z"/>',
        "route": '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path d="M8 6h4a4 4 0 0 1 4 4v4a4 4 0 0 0 4 4"/>',
        "spark": '<path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2Z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L15 19l2.2-.8L19 16Z"/>',
        "pin": '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "check": '<path d="m5 12 4 4L19 6"/>',
    }
    return (
        f'<svg aria-hidden="true" viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="none" stroke="currentColor" stroke-width="2.3" '
        f'stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'
    )


def _source_form(variant: str, compact: bool = False) -> str:
    compact_class = " creator-source-compact" if compact else ""
    return f"""
      <section class="p-card creator-source{compact_class}" data-component="source" aria-labelledby="creator-source-heading">
        <div class="creator-source-heading">
          <span class="creator-icon creator-icon-sun">{_icon("link", 23)}</span>
          <div>
            <p class="p-eyebrow">01 / START WITH A STORY</p>
            <h2 id="creator-source-heading">Paste a link you already have</h2>
            <p class="p-muted">A reel, video, or travel article URL. This demo never opens or fetches it.</p>
          </div>
        </div>
        <label class="creator-field-label" for="creator-url-{variant}">Story URL</label>
        <div class="creator-url-row">
          <input class="p-input creator-url-input" id="creator-url-{variant}" data-url-input
            type="text" inputmode="url" autocomplete="url" spellcheck="false"
            placeholder="https://example.com/my-granada-story" aria-describedby="creator-url-help-{variant} creator-url-error-{variant}">
          <button class="p-button is-secondary creator-sample-button" type="button" data-action="sample">
            { _icon("spark", 17) } Try sample link
          </button>
        </div>
        <p class="creator-help" id="creator-url-help-{variant}">Use any well-formed http(s) URL; the address is shown as plain text and stays in this page.</p>
        <p class="creator-error" id="creator-url-error-{variant}" data-url-error role="alert" hidden></p>
        <div class="creator-source-options">
          <label class="creator-field-label" for="creator-scenario-{variant}">Demo scenario</label>
          <select class="p-input creator-scenario" id="creator-scenario-{variant}" data-scenario>
            <option value="synthetic">Synthetic Granada story (default)</option>
            <option value="unavailable">Private / unavailable source (simulated)</option>
          </select>
          <button class="p-button is-primary creator-run-button" type="button" data-action="run">
            <span data-run-label>Make a demo plan</span> {_icon("arrow", 17)}
          </button>
        </div>
        <p class="creator-local-note">{_icon("check", 15)} All steps are simulated locally · nothing is transcribed, saved, or published.</p>
      </section>
    """


def _illustration(compact: bool = False) -> str:
    sample = "".join(
        f"""
        <div class="creator-illustration-day">
          <span class="creator-day-number">DAY 0{index + 1}</span>
          <strong>{_escape_text(("Albaicín", "Alhambra & Realejo", "A playful last day")[index])}</strong>
          <ul>{"".join(f'<li><span>{escape(place)}</span><small>{escape(time)}</small></li>' for place, time, _ in day)}</ul>
        </div>
        """
        for index, day in enumerate(_SAMPLE_DAYS)
    )
    return f"""
      <div class="creator-illustration{" creator-illustration-compact" if compact else ""}" data-illustration>
        <div class="creator-output-label">
          <span class="p-chip is-sky">ILLUSTRATIVE DRAFT</span>
          <span class="creator-synthetic-mark">Synthetic example · not extracted from a link</span>
        </div>
        <h3>A long weekend in Granada, with kids</h3>
        <p class="p-muted">A preview of the shape of a trip. Run the simulation to get timestamped evidence and editable stops.</p>
        <div class="creator-illustration-days">{sample}</div>
      </div>
    """


def _transcript_panel(variant: str, empty_large: bool = False) -> str:
    return f"""
      <section class="p-card creator-transcript" data-component="transcript" data-transcript-panel aria-labelledby="creator-transcript-heading">
        <div class="creator-panel-heading">
          <div>
            <p class="p-eyebrow">02 / SOURCE EVIDENCE</p>
            <h2 id="creator-transcript-heading">A story, with its receipts</h2>
          </div>
          <span class="p-chip is-plum" data-transcript-badge>NOT RUN</span>
        </div>
        <div class="creator-transcript-source">
          <span class="creator-mini-icon">{_icon("link", 15)}</span>
          <span class="creator-source-caption">Submitted URL</span>
          <span class="creator-source-value" data-source-display>—</span>
        </div>
        <div class="creator-transcript-empty{" creator-transcript-empty-large" if empty_large else ""}" data-transcript-empty>
          <span class="creator-empty-mark">{_icon("play", 19)}</span>
          <div><strong>No transcript yet</strong><p>A synthetic, timestamped example appears here after you run the demo. No source is contacted.</p></div>
        </div>
        <ol class="creator-transcript-list" data-transcript-list hidden></ol>
        <p class="creator-attribution-note" data-attribution-note hidden>
          Synthetic demo copy and timestamps. Not a real transcript, creator endorsement, or verified recommendation.
        </p>
      </section>
    """


def _output_panel(variant: str, rail: bool = False, day_columns: bool = False) -> str:
    rail_class = " creator-plan-rail" if rail else ""
    layout_class = " creator-plan-day-columns" if day_columns else ""
    return f"""
      <section class="p-card creator-plan-panel{rail_class}{layout_class}" data-component="plan" aria-labelledby="creator-plan-heading">
        <div class="creator-panel-heading">
          <div>
            <p class="p-eyebrow">03 / SHAPE THE STOPS</p>
            <h2 id="creator-plan-heading">A route worth following</h2>
          </div>
          <span class="p-chip is-mint" data-plan-badge>EXAMPLE</span>
        </div>
        <div class="creator-title-editor" data-title-editor hidden>
          <label class="creator-field-label" for="creator-title-{variant}">Trip title</label>
          <input class="p-input" id="creator-title-{variant}" type="text" maxlength="90" data-title-input>
        </div>
        {_illustration(compact=rail)}
        <div class="creator-generated-plan" data-generated-plan hidden>
          <div class="creator-review-note" data-review-note>
            <span class="creator-review-icon">{_icon("spark", 17)}</span>
            <span><strong>One detail needs your judgment</strong><br>Opening hours and timed entry are not verified in this demo. Check before you go.</span>
          </div>
          <div class="creator-plan-results" data-plan-results></div>
        </div>
        <button class="p-button is-secondary creator-preview-button" type="button" data-action="preview" hidden>
          Preview this trip {_icon("arrow", 17)}
        </button>
      </section>
    """


def _preview_panel() -> str:
    return f"""
      <section class="p-card creator-public-preview" data-component="preview" data-preview-panel hidden aria-labelledby="creator-preview-heading">
        <div class="creator-preview-topline">
          <span class="p-chip is-plum">TRAVELER VIEW · SIMULATED</span>
          <span class="creator-preview-status" data-publish-status>PREVIEW ONLY</span>
        </div>
        <p class="p-eyebrow">YOUR STORY, TURNED INTO A TRIP</p>
        <h2 id="creator-preview-heading" data-preview-title></h2>
        <p class="creator-preview-byline">Built from a synthetic example · Source details are unverified</p>
        <div class="creator-preview-days" data-preview-days></div>
        <div class="creator-publish-result" data-publish-result hidden>
          <span class="creator-icon creator-icon-mint">{_icon("check", 19)}</span>
          <div><strong>Preview simulated. Nothing was published.</strong><p>No trip was saved and no public link was created.</p></div>
        </div>
        <button class="p-button is-primary creator-publish-button" type="button" data-action="publish">
          Simulate publish <span class="creator-button-small">preview only</span> {_icon("arrow", 17)}
        </button>
      </section>
    """


def _workflow_status() -> str:
    return """
      <div class="creator-workflow-strip" data-component="workflow" aria-label="Demo stages">
        <span data-stage-indicator="source" class="is-current"><b>1</b> Link</span>
        <i aria-hidden="true"></i><span data-stage-indicator="transcript"><b>2</b> Evidence</span>
        <i aria-hidden="true"></i><span data-stage-indicator="plan"><b>3</b> Itinerary</span>
        <i aria-hidden="true"></i><span data-stage-indicator="preview"><b>4</b> Preview</span>
      </div>
    """


def _actions(reset: str) -> str:
    return f"""
      <div class="creator-action-toolbar" data-component="actions">
        <p class="p-muted" data-stage-copy>First, choose a travel story.</p>
        <div class="creator-toolbar-actions">
          <button class="p-button is-primary creator-extract-button" type="button" data-action="extract" hidden>Extract stops {_icon("arrow", 17)}</button>
          {reset}
        </div>
      </div>
    """


def _slot(name: str, components: dict[str, str], active: str, layout: str) -> str:
    contents = components[name] if active == layout else ""
    return f'<div class="creator-slot" data-slot="{name}">{contents}</div>'


def _layout_a(components: dict[str, str], active: str) -> str:
    return f"""
      <div class="p-container creator-layout creator-layout-a" data-creator-layout="A"{" hidden" if active != "A" else ""}>
        <div class="creator-source-lead">
          <div class="creator-source-lead-copy">
            <span class="creator-section-index">01</span>
            <p class="p-eyebrow">NO NEW CONTENT TO WRITE</p>
            <h2>Bring the link.<br><em>We’ll find the stops.</em></h2>
            <p class="p-muted">A travel video or article is the starting point—not a blank editor.</p>
          </div>
          {_slot("source", components, active, "A")}
        </div>
        {_slot("workflow", components, active, "A")}
        {_slot("actions", components, active, "A")}
        <div class="creator-a-columns">
          {_slot("transcript", components, active, "A")}
          {_slot("plan", components, active, "A")}
        </div>
        {_slot("preview", components, active, "A")}
      </div>
    """


def _layout_b(components: dict[str, str], active: str) -> str:
    return f"""
      <div class="p-container creator-layout creator-layout-b" data-creator-layout="B"{" hidden" if active != "B" else ""}>
        <div class="creator-b-source-row">
          <div><span class="creator-section-index">01</span><p class="p-eyebrow">YOUR EXISTING STORY</p><strong>Drop a link. Keep the good bits.</strong></div>
          {_slot("source", components, active, "B")}
        </div>
        {_slot("workflow", components, active, "B")}
        {_slot("actions", components, active, "B")}
        <div class="creator-b-columns">
          <div class="creator-b-reading">
            <div class="creator-reading-intro"><span class="creator-section-index">02</span><div><p class="p-eyebrow">TIMESTAMPED READING VIEW</p><h2>Keep the story attached.</h2><p class="p-muted">Every excerpt stays beside its timecode. No unsupported claims.</p></div></div>
            {_slot("transcript", components, active, "B")}
          </div>
          <aside class="creator-b-rail" aria-label="Itinerary and preview">
            {_slot("plan", components, active, "B")}
            {_slot("preview", components, active, "B")}
          </aside>
        </div>
      </div>
    """


def _layout_c(components: dict[str, str], active: str) -> str:
    return f"""
      <div class="p-container creator-layout creator-layout-c" data-creator-layout="C"{" hidden" if active != "C" else ""}>
        <div class="creator-c-source-row">
          <div class="creator-c-source-title"><span class="creator-section-index">01</span><div><p class="p-eyebrow">DROP IN YOUR EXISTING STORY</p><h2>Start with a link.</h2></div></div>
          {_slot("source", components, active, "C")}
        </div>
        {_slot("workflow", components, active, "C")}
        {_slot("actions", components, active, "C")}
        <div class="creator-c-itinerary">
          <div class="creator-c-heading"><div><span class="creator-section-index">02</span><p class="p-eyebrow">ITINERARY FIRST</p><h2>Three days, easy to explore.</h2></div><span class="p-chip is-sky">DAY BY DAY</span></div>
          {_slot("plan", components, active, "C")}
        </div>
        <details class="creator-evidence-disclosure">
          <summary><span class="creator-section-index">03</span><span><b>Show source evidence</b><small>See the timestamped transcript behind each stop</small></span><span class="creator-disclosure-arrow">{_icon("arrow", 17)}</span></summary>
          {_slot("transcript", components, active, "C")}
        </details>
        {_slot("preview", components, active, "C")}
      </div>
    """


def _live_state() -> str:
    return """
      <details class="creator-state-details" open>
        <summary><span>DEMO STATE</span><span class="creator-state-summary">See exactly what this page is simulating</span></summary>
        <pre data-demo-state>{"stage":"ready","sourceUrl":"","sourceContacted":false,"scenario":"synthetic","transcript":"not generated","stops":"illustrative only","review":"not started","publish":"not published","error":""}</pre>
      </details>
      <div class="creator-live-region" data-live role="status" aria-live="polite" aria-atomic="true">Ready. Paste a story URL or try the sample link.</div>
    """


def _escape_text(value: str) -> str:
    return escape(value, quote=True)


def render_creator(variant: str) -> str:
    """Return the requested creator prototype as an HTML content fragment."""
    selected = str(variant).upper() if str(variant).upper() in {"A", "B", "C"} else "A"
    hero = f"""
      <section class="p-container p-section creator-hero">
        <div class="creator-hero-copy">
          <p class="p-eyebrow"><span class="creator-eyebrow-dot"></span> CREATOR STUDIO <span class="creator-prototype-tag">PROTOTYPE</span></p>
          <h1 class="p-title">Turn a story into someone’s <em>next trip.</em></h1>
          <p class="p-muted creator-hero-subtitle">Start with the travel story you already made. Shape its best stops into a plan people can actually follow.</p>
        </div>
        <div class="creator-simulation-stamp">{_icon("spark", 19)}<span>LOCAL SIMULATION<br><b>No fetch · no save · no publish</b></span></div>
      </section>
    """
    reset = '<button class="p-button is-ghost creator-reset-button" type="button" data-action="reset">Reset demo</button>'
    components = {
        "source": _source_form(selected, compact=selected in {"B", "C"}),
        "workflow": _workflow_status(),
        "actions": _actions(reset),
        "transcript": _transcript_panel(selected, empty_large=True),
        "plan": _output_panel(selected, rail=selected == "B", day_columns=selected == "C"),
        "preview": _preview_panel(),
    }
    layouts = _layout_a(components, selected) + _layout_b(components, selected) + _layout_c(components, selected)

    return f"""
      <main class="creator-prototype creator-variant-{selected.lower()}" data-creator-variant="{escape(selected)}">
        {hero}
        <div class="creator-top-rule"></div>
        {layouts}
        <footer class="p-container creator-footer">
          <span>TravelOS Creator Studio <b>·</b> Interface prototype</span>
          <span>Synthetic example only. No external services are called.</span>
        </footer>
        {_live_state()}
      </main>
    """
