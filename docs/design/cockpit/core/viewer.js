/* Artboard viewer for a direction page.
   ?bare=1&screen=cockpit|book|day|paste&size=ph|dk&mode=light|dark[&day=N][&phase=open|read|landed] renders one artboard
   at its real size (the frames below and the PNGs use it); without bare it draws the overview: every screen, phone and
   desktop side by side, live (tap a day, paste a confirmation), with a Light/Dark switch. */
(function () {
  const q = new URLSearchParams(location.search);
  const D = window.DIR;
  const mode = q.get('mode') || localStorage.getItem('cockpit-mode') || 'light';
  document.documentElement.className = mode;
  document.body.className = 'v-' + mode;
  window.VIEW = { ready() { window.__ready = true; document.documentElement.dataset.ready = '1'; } };
  if (q.get('bare')) {
    const screen = q.get('screen') || 'cockpit', size = q.get('size') || 'dk';
    const sc = D.screens[screen];
    if (q.get('day')) window.UI.S.day = +q.get('day');
    const root = document.createElement('div');
    root.className = `ab ${size} ${mode} dir-${D.id} scr-${screen}${sc.fixed && sc.fixed.includes(size) ? ' fixed' : ''}`;
    document.body.appendChild(root);
    document.body.style.margin = 0;
    root.innerHTML = sc.render(size, q);
    window.UI.bindPress(root);
    sc.mount(root, size, q);
    return;
  }
  const NAMES = { cockpit: '1 · The trip cockpit', book: '2 · Book this trip', day: '3 · One day, on the phone', paste: '4 · A pasted confirmation lands' };
  const rows = Object.entries(D.screens).map(([k, sc]) => {
    const src = (size) => `?bare=1&screen=${k}&size=${size}&mode=${mode}`;
    const fr = sc.sizes.map((s) => s === 'ph'
      ? `<div class="fr ph-fr"><iframe src="${src('ph')}" title="${k} phone" loading="lazy"></iframe><span>Phone · 390 · <a href="${src('ph')}" target="_blank">open</a></span></div>`
      : `<div class="fr dk-fr"><div class="dk-scale"><iframe src="${src('dk')}" title="${k} desktop" loading="lazy"></iframe></div><span>Desktop · 1440 × 900 · <a href="${src('dk')}" target="_blank">open full size</a></span></div>`).join('');
    return `<section class="row" id="${k}"><h2>${NAMES[k]}</h2>${sc.note ? `<p class="rn">${sc.note}</p>` : ''}<div class="frames">${fr}</div></section>`;
  }).join('');
  const others = [['1-diorama.html', '1 · Diorama'], ['2-widgets.html', '2 · Widget board'], ['3-ticket.html', '3 · Ticket line']];
  document.body.innerHTML = `<header class="vbar"><a href="index.html" class="vback">All directions</a><b>${document.title}</b><nav>${others.map(([h, n]) => `<a href="${h}" class="${h.startsWith(D.id + '-') ? 'on' : ''}">${n}</a>`).join('')}</nav>
    <button class="vmode" id="mode">${mode === 'light' ? 'Dark' : 'Light'}</button></header>
    <main class="vmain"><div class="notes">${D.notes}</div>${rows}</main>`;
  document.getElementById('mode').onclick = () => { localStorage.setItem('cockpit-mode', mode === 'light' ? 'dark' : 'light'); location.search = ''; };
})();
