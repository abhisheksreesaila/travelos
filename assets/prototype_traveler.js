const root = document.querySelector('.traveler-prototype');

if (root) {
  const workspace = root.matches('[data-workspace]') ? root : root.querySelector('[data-workspace]');
  const state = workspace?.querySelector('[data-trip-state]');
  const dateInput = workspace?.querySelector('[data-plan-input="start"]');
  const adultsInput = workspace?.querySelector('[data-plan-input="adults"]');
  const kidsInput = workspace?.querySelector('[data-plan-input="kids"]');
  const ageInput = workspace?.querySelector('[data-plan-input="age"]');
  const paceInput = workspace?.querySelector('[data-plan-input="pace"]');
  let selectedDay = 0;
  let showKidOptions = false;
  const MAX_TRAVELERS = 12;

  const formatDate = (date, options = { month: 'short', day: '2-digit' }) =>
    new Intl.DateTimeFormat('en', options).format(date);

  const ageMessage = () => {
    if (Number(kidsInput?.value || 0) === 0) return 'No kids in this sample crew. Add a kid to see the family-friendly swap cues.';
    const age = Number(ageInput?.value || 7);
    return age < 4 || age > 10
      ? `Swaps are written for a broad family range; adapt these notes for a ${age}-year-old.`
      : 'Kid-friendly swaps are written for a wide range of ages; adapt them to your family.';
  };

  const paintDaySelection = () => {
    workspace?.querySelectorAll('[data-select-day]').forEach((button) => {
      const active = Number(button.dataset.selectDay) === selectedDay;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    workspace?.querySelectorAll('[data-day-panel]').forEach((panel) => {
      panel.hidden = Number(panel.dataset.dayPanel) !== selectedDay;
    });
  };

  const paintKidOptions = () => {
    const hasKids = !workspace || Number(kidsInput?.value || 0) > 0;
    if (workspace && !hasKids) showKidOptions = false;
    root.querySelectorAll('[data-kid-copy]').forEach((copy) => { copy.hidden = !showKidOptions || !hasKids; });
    root.querySelectorAll('[data-primary-copy]').forEach((copy) => { copy.hidden = showKidOptions; });
    root.querySelectorAll('[data-kid-toggle], [data-global-kid-toggle]').forEach((button) => {
      button.hidden = Boolean(workspace && !hasKids);
      button.disabled = Boolean(workspace && !hasKids);
      button.setAttribute('aria-pressed', String(showKidOptions));
      button.setAttribute('aria-label', showKidOptions ? 'Hide kid-friendly swaps' : 'Show kid-friendly swaps');
      const text = button.querySelector('span:first-child');
      const globalLabel = button.querySelector('[data-kid-global-label]');
      const switchState = button.querySelector('[data-kid-switch-state]');
      if (globalLabel) globalLabel.textContent = showKidOptions && !switchState ? '✳ Kid swaps ON' : '✳ Kid swaps';
      if (switchState) switchState.textContent = showKidOptions ? 'ON' : 'OFF';
      if (button.matches('.p-day-action') && text) {
        text.textContent = showKidOptions ? 'Hide kid-friendly swaps' : 'Show kid-friendly swaps';
      } else if (button.matches('.p-kid-toggle')) {
        const label = button.querySelector('i');
        if (label?.firstChild) label.firstChild.textContent = showKidOptions ? 'Hide swaps ' : 'Show swaps ';
      }
    });
    workspace?.querySelectorAll('[data-kid-affordance]').forEach((item) => { item.hidden = !hasKids; });
    const ageField = ageInput?.closest('.p-field');
    if (ageField) ageField.hidden = !hasKids;
    if (ageInput) ageInput.disabled = !hasKids;
    const ageNote = workspace?.querySelector('[data-age-note]');
    if (ageNote) ageNote.textContent = ageMessage();
    const feedback = root.querySelector('[data-kid-feedback]');
    if (feedback) feedback.textContent = showKidOptions
      ? 'Kid-friendly swaps are shown. Sofía & Mateo’s source credit stays attached.'
      : 'Showing the original creator route.';
  };

  const updateTripState = () => {
    if (!workspace || !state) return;
    const rawDate = dateInput?.value || '';
    const start = rawDate ? new Date(`${rawDate}T12:00:00`) : null;
    if (!start || Number.isNaN(start.getTime())) {
      paintKidOptions();
      state.textContent = 'Choose a valid start date · trip changes stay in memory only';
      return;
    }
    const end = new Date(start);
    end.setDate(start.getDate() + 2);
    const adults = Number(adultsInput?.value || 2);
    const kids = Number(kidsInput?.value || 1);
    const total = adults + kids;
    if (kids === 0) showKidOptions = false;
    const party = `${adults} ${adults === 1 ? 'adult' : 'adults'}${kids ? ` + ${kids} ${kids === 1 ? 'kid' : 'kids'} (youngest ${ageInput?.value || 7})` : ' + no kids'}`;
    const pace = paceInput?.selectedOptions[0]?.textContent || 'Balanced';
    const paceKey = paceInput?.value || 'balanced';
    const dateRange = `${formatDate(start)}–${formatDate(end)}`;

    workspace.querySelectorAll('[data-day-date]').forEach((label) => {
      const date = new Date(start);
      date.setDate(start.getDate() + Number(label.dataset.dayDate));
      label.textContent = label.tagName === 'TIME'
        ? `DAY ${String(Number(label.dataset.dayDate) + 1).padStart(2, '0')} · ${formatDate(date, { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase()}`
        : formatDate(date, { month: 'short', day: '2-digit' }).toUpperCase();
    });
    workspace.querySelectorAll('[data-share-date]').forEach((label) => {
      const date = new Date(start);
      date.setDate(start.getDate() + Number(label.dataset.shareDate));
      label.textContent = formatDate(date, { month: 'short', day: '2-digit' }).toUpperCase();
    });
    workspace.querySelectorAll('[data-weather-day]').forEach((label) => {
      const date = new Date(start);
      date.setDate(start.getDate() + Number(label.dataset.weatherDay));
      label.textContent = formatDate(date, { weekday: 'short' }).toUpperCase();
    });
    workspace.querySelectorAll('[data-time]').forEach((time) => {
      const key = `time${paceKey[0].toUpperCase()}${paceKey.slice(1)}`;
      if (time.dataset[key]) time.firstChild.textContent = `${time.dataset[key]} `;
    });

    const group = `${total} ${total === 1 ? 'traveler' : 'travelers'} · ${party}`;
    const kidLabel = showKidOptions ? 'kid swaps on' : kids === 0 ? 'no kid swaps' : 'creator route';
    state.textContent = `${group} · ${dateRange} · ${pace} · Day ${selectedDay + 1} of 3 · ${kidLabel} · memory-only sample`;
    const shareSummary = workspace.querySelector('[data-share-summary]');
    if (shareSummary) shareSummary.textContent = `${group} · ${dateRange} · ${pace} · Day ${selectedDay + 1} · ${showKidOptions ? 'kid-friendly swaps' : 'creator route'}`;
    const shareTitle = workspace.querySelector('#share-title');
    if (shareTitle) shareTitle.textContent = `Granada with room for ${total === 1 ? 'one' : 'your crew'}`;
    paintKidOptions();
  };

  workspace?.querySelectorAll('[data-select-day]').forEach((button) => {
    button.addEventListener('click', () => {
      selectedDay = Number(button.dataset.selectDay);
      paintDaySelection();
      updateTripState();
    });
  });
  const constrainParty = (changed) => {
    if (!workspace || !adultsInput || !kidsInput) return;
    let adults = Number(adultsInput.value);
    let kids = Number(kidsInput.value);
    if (adults + kids > MAX_TRAVELERS) {
      if (changed === adultsInput) {
        kids = Math.max(0, MAX_TRAVELERS - adults);
        kidsInput.value = String(kids);
      } else {
        adults = Math.max(1, MAX_TRAVELERS - kids);
        adultsInput.value = String(adults);
      }
    }
    [...adultsInput.options].forEach((option) => { option.disabled = Number(option.value) + kids > MAX_TRAVELERS; });
    [...kidsInput.options].forEach((option) => { option.disabled = Number(option.value) + adults > MAX_TRAVELERS; });
  };

  workspace?.querySelectorAll('[data-plan-input]').forEach((input) => {
    const update = () => {
      if (input === adultsInput || input === kidsInput) constrainParty(input);
      updateTripState();
    };
    input.addEventListener('input', update);
    input.addEventListener('change', update);
  });
  root.querySelectorAll('[data-kid-toggle], [data-global-kid-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      showKidOptions = !showKidOptions;
      paintKidOptions();
      updateTripState();
    });
  });

  if (workspace) {
    const forked = new URLSearchParams(window.location.search).get('fork') === '1';
    if (forked) {
      const memoryLabel = workspace.querySelector('.p-memory-ribbon b');
      if (memoryLabel) memoryLabel.textContent = 'Fork preview opened. Changes are only in this page; nothing is saved.';
    }
    constrainParty();
    paintDaySelection();
    updateTripState();
  }
  paintKidOptions();

  const dialog = root.querySelector('[data-share-dialog]');
  root.querySelectorAll('[data-share-open]').forEach((button) => {
    button.addEventListener('click', () => {
      if (dateInput && !dateInput.value && typeof dateInput.reportValidity === 'function') {
        dateInput.reportValidity();
        return;
      }
      updateTripState();
      if (typeof dialog?.showModal === 'function') dialog.showModal();
    });
  });
  root.querySelectorAll('[data-share-close]').forEach((button) => button.addEventListener('click', () => dialog?.close()));
  dialog?.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
  root.querySelector('[data-share-print]')?.addEventListener('click', () => window.print());
}
