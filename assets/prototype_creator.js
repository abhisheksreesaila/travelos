const SAMPLE_URL = "https://example.com/granada-family-weekend";
const SAMPLE_TITLE = "A long weekend in Granada, with kids";
const SAMPLE_TRANSCRIPT = [
  { time: "00:24", quote: "We made our way up to the Mirador de San Nicolás for the sunset view over Granada." },
  { time: "00:41", quote: "On the way down, Calle Calderería Nueva was an easy stop for tea and something sweet." },
  { time: "01:12", quote: "We booked the Alhambra first thing in the morning, then wandered through the Generalife gardens." },
  { time: "01:46", quote: "After a long morning, we slowed down for lunch around Realejo." },
  { time: "02:08", quote: "The Parque de las Ciencias gave everyone a hands-on afternoon and room to run around." },
  { time: "02:32", quote: "For our last evening, we took an unhurried walk along the Carrera del Darro." },
];
const SAMPLE_DAYS = [
  {
    label: "Albaicín",
    stops: [
      { name: "Mirador de San Nicolás", note: "Sunset · Albaicín", time: "00:24", evidence: "We made our way up to the Mirador de San Nicolás for the sunset view over Granada." },
      { name: "Calle Calderería Nueva", note: "Tea and pastries", time: "00:41", evidence: "Calle Calderería Nueva was an easy stop for tea and something sweet." },
    ],
  },
  {
    label: "Alhambra & Realejo",
    stops: [
      { name: "Alhambra & Generalife", note: "Timed entry · go early", time: "01:12", evidence: "We booked the Alhambra first thing in the morning, then wandered through the Generalife gardens.", uncertain: true },
      { name: "Realejo lunch stop", note: "Flexible afternoon reset", time: "01:46", evidence: "We slowed down for lunch around Realejo." },
    ],
  },
  {
    label: "A playful last day",
    stops: [
      { name: "Parque de las Ciencias", note: "Hands-on family morning", time: "02:08", evidence: "The Parque de las Ciencias gave everyone a hands-on afternoon and room to run around." },
      { name: "Carrera del Darro", note: "Easy final stroll", time: "02:32", evidence: "We took an unhurried walk along the Carrera del Darro." },
    ],
  },
];

function cloneDays() {
  return SAMPLE_DAYS.map((day) => ({ ...day, stops: day.stops.map((stop) => ({ ...stop })) }));
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function initializeCreator(root) {
  const input = root.querySelector("[data-url-input]");
  const scenario = root.querySelector("[data-scenario]");
  const error = root.querySelector("[data-url-error]");
  const live = root.querySelector("[data-live]");
  const stateOutput = root.querySelector("[data-demo-state]");
  const transcriptList = root.querySelector("[data-transcript-list]");
  const transcriptEmpty = root.querySelector("[data-transcript-empty]");
  const transcriptBadge = root.querySelector("[data-transcript-badge]");
  const attribution = root.querySelector("[data-attribution-note]");
  const sourceDisplay = root.querySelector("[data-source-display]");
  const illustration = root.querySelector("[data-illustration]");
  const generatedPlan = root.querySelector("[data-generated-plan]");
  const planBadge = root.querySelector("[data-plan-badge]");
  const planResults = root.querySelector("[data-plan-results]");
  const titleEditor = root.querySelector("[data-title-editor]");
  const titleInput = root.querySelector("[data-title-input]");
  const previewButton = root.querySelector('[data-action="preview"]');
  const previewPanel = root.querySelector("[data-preview-panel]");
  const previewTitle = root.querySelector("[data-preview-title]");
  const previewDays = root.querySelector("[data-preview-days]");
  const publishButton = root.querySelector('[data-action="publish"]');
  const publishResult = root.querySelector("[data-publish-result]");
  const publishStatus = root.querySelector("[data-publish-status]");
  const stageCopy = root.querySelector("[data-stage-copy]");
  const extractButton = root.querySelector('[data-action="extract"]');
  const runButton = root.querySelector('[data-action="run"]');
  const runLabel = root.querySelector("[data-run-label]");
  const stageIndicators = [...root.querySelectorAll("[data-stage-indicator]")];
  const evidenceDetails = root.querySelector(".creator-evidence-disclosure");
  let timer;

  const state = {
    variant: root.dataset.creatorVariant,
    stage: "ready",
    sourceUrl: "",
    sourceContacted: false,
    scenario: "synthetic",
    transcript: "not generated",
    transcriptEntries: 0,
    title: "",
    stops: "illustrative only",
    review: "not started",
    publish: "not published",
    error: "",
  };

  function announce(message) {
    live.textContent = message;
  }

  function updateState() {
    stateOutput.textContent = JSON.stringify(state, null, 2);
    stageIndicators.forEach((indicator) => {
      const names = ["source", "transcript", "plan", "preview"];
      const stageOrder = { ready: 0, processing: 0, unavailable: 1, transcript: 1, extracting: 1, itinerary: 2, preview: 3, published: 3 };
      const index = names.indexOf(indicator.dataset.stageIndicator);
      const current = stageOrder[state.stage] ?? 0;
      indicator.classList.toggle("is-current", index === current);
      indicator.classList.toggle("is-complete", index < current || (state.stage === "published" && index === 3));
    });
    if (stageCopy) {
      const copy = {
        ready: "First, choose a travel story.",
        processing: "Running a local-only simulation…",
        unavailable: "No content is available in this scenario. Try the synthetic sample.",
        transcript: "Review the synthetic timestamps, then extract a first-pass itinerary.",
        extracting: "Turning the example transcript into editable stops…",
        itinerary: "Edit the trip title and any stop before opening the preview.",
        preview: "Review the traveler-facing preview. Publishing remains simulated.",
        published: "Preview simulated. Nothing was persisted or made public.",
      };
      stageCopy.textContent = copy[state.stage] ?? copy.ready;
    }
  }

  function switchVariant(value, announceChange = true) {
    const next = String(value ?? "").toUpperCase();
    if (!["A", "B", "C"].includes(next)) return;
    if (state.variant === next && root.dataset.creatorVariant === next) return;

    const target = root.querySelector(`[data-creator-layout="${next}"]`);
    if (!target) return;
    root.querySelectorAll("[data-component]").forEach((component) => {
      const slot = target.querySelector(`[data-slot="${component.dataset.component}"]`);
      if (slot) slot.append(component);
    });
    root.querySelectorAll("[data-creator-layout]").forEach((layout) => {
      layout.hidden = layout !== target;
    });

    root.dataset.creatorVariant = next;
    root.classList.remove("creator-variant-a", "creator-variant-b", "creator-variant-c");
    root.classList.add(`creator-variant-${next.toLowerCase()}`);
    const source = root.querySelector('[data-component="source"]');
    const plan = root.querySelector('[data-component="plan"]');
    const illustration = root.querySelector("[data-illustration]");
    source.classList.toggle("creator-source-compact", next !== "A");
    plan.classList.toggle("creator-plan-rail", next === "B");
    plan.classList.toggle("creator-plan-day-columns", next === "C");
    illustration.classList.toggle("creator-illustration-compact", next === "B");
    state.variant = next;
    updateState();
    if (announceChange) {
      announce(`Variant ${next} layout selected. The current draft and demo state are preserved.`);
    }
  }

  function setError(message) {
    error.textContent = message;
    error.hidden = !message;
    input.setAttribute("aria-invalid", message ? "true" : "false");
    state.error = message;
  }

  function showTranscript() {
    transcriptList.replaceChildren();
    SAMPLE_TRANSCRIPT.forEach((entry) => {
      const item = node("li", "creator-transcript-line");
      item.append(node("span", "creator-timecode", entry.time));
      const quote = node("p", "creator-quote");
      quote.textContent = `“${entry.quote}”`;
      item.append(quote);
      transcriptList.append(item);
    });
    transcriptList.hidden = false;
    transcriptEmpty.hidden = true;
    attribution.hidden = false;
    transcriptBadge.textContent = "SYNTHETIC EXAMPLE";
    transcriptBadge.className = "p-chip is-plum";
    sourceDisplay.textContent = state.sourceUrl;
    sourceDisplay.title = state.sourceUrl;
  }

  function buildStop(dayIndex, stopIndex, stop) {
    const card = node("article", "creator-stop");
    const row = node("div", "creator-stop-input-row");
    row.append(node("span", "creator-stop-index", `${stopIndex + 1}`));
    const label = node("label", "creator-stop-label");
    const inputElement = document.createElement("input");
    inputElement.type = "text";
    inputElement.maxLength = 100;
    inputElement.value = stop.name;
    inputElement.dataset.stopDay = String(dayIndex);
    inputElement.dataset.stopIndex = String(stopIndex);
    inputElement.setAttribute("aria-label", `Day ${dayIndex + 1}, stop ${stopIndex + 1}`);
    label.append(inputElement);
    row.append(label);
    card.append(row);
    card.append(node("p", "creator-stop-meta", stop.note));
    const evidence = node("p", "creator-stop-evidence");
    const time = node("b", "", stop.time);
    evidence.append(time, document.createTextNode(` Synthetic evidence · “${stop.evidence}”`));
    card.append(evidence);
    if (stop.uncertain) {
      const missing = node("p", "creator-stop-meta creator-stop-uncertain", "Review: entry time and opening hours not checked");
      card.append(missing);
    }
    return card;
  }

  function renderEditablePlan() {
    planResults.replaceChildren();
    state.days.forEach((day, dayIndex) => {
      const dayNode = node("section", "creator-plan-day");
      const heading = node("div", "creator-day-heading");
      heading.append(node("strong", "", `Day ${dayIndex + 1} · ${day.label}`));
      heading.append(node("span", "", `${day.stops.length} STOPS`));
      dayNode.append(heading);
      day.stops.forEach((stop, stopIndex) => dayNode.append(buildStop(dayIndex, stopIndex, stop)));
      planResults.append(dayNode);
    });
  }

  function renderPreview() {
    previewTitle.textContent = state.title;
    previewDays.replaceChildren();
    state.days.forEach((day, index) => {
      const dayCard = node("section", "creator-preview-day");
      dayCard.append(node("span", "", `DAY 0${index + 1} · ${day.label.toUpperCase()}`));
      const list = document.createElement("ul");
      day.stops.forEach((stop) => list.append(node("li", "", stop.name)));
      dayCard.append(list);
      previewDays.append(dayCard);
    });
  }

  function showUnavailable() {
    state.stage = "unavailable";
    state.transcript = "unavailable (simulated; no request made)";
    state.transcriptEntries = 0;
    state.stops = "not extracted";
    state.review = "not started";
    state.publish = "not published";
    transcriptBadge.textContent = "UNAVAILABLE · SIMULATED";
    transcriptBadge.className = "p-chip is-sun";
    transcriptEmpty.hidden = false;
    transcriptEmpty.querySelector("strong").textContent = "This source is unavailable in the demo";
    transcriptEmpty.querySelector("p").textContent = "This is a preset scenario, not a network check. Nothing was requested. Try the synthetic Granada link instead.";
    sourceDisplay.textContent = state.sourceUrl;
    sourceDisplay.title = state.sourceUrl;
    sourceDisplay.closest(".creator-transcript-source").hidden = false;
    announce("Private or unavailable scenario simulated. No source was contacted.");
    updateState();
  }

  function clearDerivedState() {
    if (timer) clearTimeout(timer);
    timer = undefined;
    state.stage = "ready";
    state.sourceContacted = false;
    state.transcript = "not generated";
    state.transcriptEntries = 0;
    state.title = "";
    state.days = undefined;
    state.stops = "illustrative only";
    state.review = "not started";
    state.publish = "not published";
    state.error = "";
    runButton.disabled = false;
    runLabel.textContent = "Make a demo plan";
    extractButton.hidden = true;
    extractButton.disabled = false;
    previewButton.hidden = true;
    previewPanel.hidden = true;
    generatedPlan.hidden = true;
    titleEditor.hidden = true;
    illustration.hidden = false;
    transcriptList.replaceChildren();
    transcriptList.hidden = true;
    transcriptEmpty.hidden = false;
    transcriptEmpty.querySelector("strong").textContent = "No transcript yet";
    transcriptEmpty.querySelector("p").textContent = "A synthetic, timestamped example appears here after you run the demo. No source is contacted.";
    transcriptBadge.textContent = "NOT RUN";
    transcriptBadge.className = "p-chip is-plum";
    planBadge.textContent = "EXAMPLE";
    planBadge.className = "p-chip is-mint";
    attribution.hidden = true;
    sourceDisplay.textContent = input.value || "—";
    sourceDisplay.title = input.value;
    sourceDisplay.closest(".creator-transcript-source").hidden = false;
    publishResult.hidden = true;
    publishButton.hidden = false;
    publishStatus.textContent = "PREVIEW ONLY";
    if (evidenceDetails) evidenceDetails.open = false;
    updateState();
  }

  function runSimulation() {
    const rawUrl = input.value;
    const candidate = rawUrl.trim();
    setError("");
    if (!candidate) {
      setError("Add a story URL first, or use the sample link.");
      state.stage = "ready";
      state.sourceUrl = rawUrl;
      state.scenario = scenario.value;
      updateState();
      announce("A story URL is required. Nothing was requested.");
      input.focus();
      return;
    }
    let parsed;
    try {
      parsed = new URL(candidate);
    } catch {
      parsed = null;
    }
    if (!parsed || !["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) {
      setError("Enter a complete http:// or https:// URL. No URL was opened or checked.");
      state.stage = "ready";
      state.sourceUrl = rawUrl;
      state.scenario = scenario.value;
      updateState();
      announce("That address is not a valid http(s) URL. Nothing was requested.");
      input.focus();
      return;
    }
    if (timer) clearTimeout(timer);
    state.stage = "processing";
    state.sourceUrl = rawUrl;
    state.sourceContacted = false;
    state.scenario = scenario.value;
    state.transcript = "pending local simulation";
    state.transcriptEntries = 0;
    state.title = "";
    state.days = undefined;
    state.stops = "not extracted";
    state.review = "not started";
    state.publish = "not published";
    extractButton.hidden = true;
    previewButton.hidden = true;
    previewPanel.hidden = true;
    generatedPlan.hidden = true;
    illustration.hidden = false;
    titleEditor.hidden = true;
    transcriptList.hidden = true;
    transcriptEmpty.hidden = false;
    attribution.hidden = true;
    sourceDisplay.textContent = state.sourceUrl;
    sourceDisplay.title = state.sourceUrl;
    transcriptBadge.textContent = "SIMULATING";
    transcriptEmpty.querySelector("strong").textContent = "Simulating a transcript…";
    transcriptEmpty.querySelector("p").textContent = "Synthetic sample copy will appear here. No creator link is being accessed.";
    runButton.disabled = true;
    runLabel.textContent = "Simulating…";
    announce("Simulating a transcript locally. The submitted URL has not been contacted.");
    updateState();
    timer = setTimeout(() => {
      timer = undefined;
      runButton.disabled = false;
      runLabel.textContent = "Run demo again";
      if (scenario.value === "unavailable") {
        showUnavailable();
        return;
      }
      state.stage = "transcript";
      state.transcript = "synthetic timestamped example (not real transcription)";
      state.transcriptEntries = SAMPLE_TRANSCRIPT.length;
      state.title = "";
      state.days = undefined;
      showTranscript();
      extractButton.hidden = false;
      transcriptEmpty.hidden = true;
      announce("Synthetic transcript ready. Six timestamped example excerpts; no source was contacted.");
      updateState();
    }, 420);
  }

  function extractPlan() {
    if (state.stage !== "transcript") return;
    state.stage = "extracting";
    announce("Extracting a structured trip from the synthetic example transcript.");
    updateState();
    extractButton.disabled = true;
    timer = setTimeout(() => {
      timer = undefined;
      extractButton.disabled = false;
      state.stage = "itinerary";
      state.title = SAMPLE_TITLE;
      state.days = cloneDays();
      state.stops = state.days.flatMap((day) => day.stops.map((stop) => stop.name));
      state.review = "required: verify Alhambra entry time and opening hours; no details confirmed";
      titleInput.value = state.title;
      titleEditor.hidden = false;
      illustration.hidden = true;
      generatedPlan.hidden = false;
      planBadge.textContent = "NEEDS YOUR REVIEW";
      planBadge.className = "p-chip is-sun";
      renderEditablePlan();
      previewButton.hidden = false;
      announce("First-pass itinerary created from synthetic evidence. Review the Alhambra timing before previewing.");
      updateState();
    }, 350);
  }

  function openPreview() {
    if (!state.days || !state.title.trim()) {
      announce("Add a trip title before opening the preview.");
      titleInput.focus();
      return;
    }
    state.stage = "preview";
    state.publish = "preview open; not published";
    renderPreview();
    previewPanel.hidden = false;
    publishResult.hidden = true;
    publishButton.hidden = false;
    publishStatus.textContent = "PREVIEW ONLY";
    announce("Traveler preview opened. It is local, temporary, and not a public trip.");
    updateState();
    previewPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function simulatePublish() {
    if (!state.title.trim()) {
      announce("Add a trip title before simulating publish.");
      titleInput.focus();
      return;
    }
    state.stage = "published";
    state.publish = "preview simulated only; not persisted; no public URL";
    publishResult.hidden = false;
    publishButton.hidden = true;
    publishStatus.textContent = "NOT PUBLISHED";
    announce("Publish simulation complete. The preview was not saved and no public link exists.");
    updateState();
  }

  function reset() {
    if (timer) clearTimeout(timer);
    timer = undefined;
    state.stage = "ready";
    state.sourceUrl = "";
    state.sourceContacted = false;
    state.scenario = "synthetic";
    state.transcript = "not generated";
    state.transcriptEntries = 0;
    state.title = "";
    state.days = undefined;
    state.stops = "illustrative only";
    state.review = "not started";
    state.publish = "not published";
    input.value = "";
    scenario.value = "synthetic";
    runButton.disabled = false;
    runLabel.textContent = "Make a demo plan";
    extractButton.hidden = true;
    extractButton.disabled = false;
    previewButton.hidden = true;
    previewPanel.hidden = true;
    generatedPlan.hidden = true;
    titleEditor.hidden = true;
    illustration.hidden = false;
    transcriptList.replaceChildren();
    transcriptList.hidden = true;
    transcriptEmpty.hidden = false;
    transcriptEmpty.querySelector("strong").textContent = "No transcript yet";
    transcriptEmpty.querySelector("p").textContent = "A synthetic, timestamped example appears here after you run the demo. No source is contacted.";
    transcriptBadge.textContent = "NOT RUN";
    transcriptBadge.className = "p-chip is-plum";
    planBadge.textContent = "EXAMPLE";
    planBadge.className = "p-chip is-mint";
    attribution.hidden = true;
    sourceDisplay.textContent = "—";
    sourceDisplay.title = "";
    sourceDisplay.closest(".creator-transcript-source").hidden = false;
    publishResult.hidden = true;
    publishButton.hidden = false;
    publishStatus.textContent = "PREVIEW ONLY";
    setError("");
    if (evidenceDetails) evidenceDetails.open = false;
    announce("Demo reset. Nothing was saved or published.");
    updateState();
  }

  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button || !root.contains(button)) return;
    switch (button.dataset.action) {
      case "sample":
        if (state.stage !== "ready") clearDerivedState();
        input.value = SAMPLE_URL;
        scenario.value = "synthetic";
        state.sourceUrl = SAMPLE_URL;
        state.scenario = "synthetic";
        setError("");
        updateState();
        announce("Sample URL added. It is an example.com placeholder; running the demo will not open it.");
        input.focus();
        break;
      case "run":
        runSimulation();
        break;
      case "extract":
        extractPlan();
        break;
      case "preview":
        openPreview();
        break;
      case "publish":
        simulatePublish();
        break;
      case "reset":
        reset();
        break;
    }
  });

  root.addEventListener("input", (event) => {
    if (event.target === input) {
      if (state.stage !== "ready") clearDerivedState();
      setError("");
      state.sourceUrl = input.value;
      updateState();
    } else if (event.target === titleInput) {
      state.title = titleInput.value;
      if (state.stage === "preview" || state.stage === "published") renderPreview();
      updateState();
    } else if (event.target.matches("[data-stop-day][data-stop-index]")) {
      const day = Number(event.target.dataset.stopDay);
      const stop = Number(event.target.dataset.stopIndex);
      state.days[day].stops[stop].name = event.target.value;
      state.stops = state.days.flatMap((item) => item.stops.map((entry) => entry.name));
      if (state.stage === "preview" || state.stage === "published") renderPreview();
      updateState();
    }
  });

  root.addEventListener("change", (event) => {
    if (event.target === scenario) {
      if (state.stage !== "ready") clearDerivedState();
      state.scenario = scenario.value;
      updateState();
      announce(scenario.value === "unavailable"
        ? "Private or unavailable source scenario selected. It is preset and makes no request."
        : "Synthetic Granada scenario selected. It uses fabricated example content only.");
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runSimulation();
    }
  });
  document.addEventListener("travelos:variantchange", (event) => {
    switchVariant(event.detail?.variant ?? document.body.dataset.creatorVariant);
  });
  window.addEventListener("popstate", () => {
    switchVariant(document.body.dataset.creatorVariant);
  });
  updateState();
}

document.querySelectorAll(".creator-prototype[data-creator-variant]").forEach(initializeCreator);
