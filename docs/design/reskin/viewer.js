/* Artboard viewer. ?bare=1&screen=day&size=ph|dk&mode=light|dark&theme=scrapbook|structured|magazine renders one screen
   at its real size (for screenshots and the frames below); without bare it draws the overview of all six screens. */
(function () {
  const q = new URLSearchParams(location.search);
  const dir = document.documentElement.dataset.dir;
  const mode = q.get('mode') || localStorage.getItem('reskin-mode') || 'light';
  document.documentElement.classList.add('dir-' + dir, mode);
  if (q.get('bare')) {
    const size = q.get('size') || 'ph';
    document.body.innerHTML = GA.render(q.get('screen') || 'landing', size, q.get('theme') || 'scrapbook');
    document.body.firstElementChild.classList.add(size);
    return;
  }
  const NAMES = { landing: '1 · Signed-out landing', signin: '2 · Sign in', day: '3 · A trip’s day', book: '4 · Booking panel', trip: '5 · A creator’s public trip', creators: '6 · For creators' };
  const rows = [];
  for (const s of GA.screens) {
    const themes = s === 'trip' ? ['scrapbook', 'structured', 'magazine'] : [''];
    for (const t of themes) {
      const src = (size) => `?bare=1&screen=${s}&size=${size}&mode=${mode}${t ? '&theme=' + t : ''}`;
      rows.push(`<section class="row" id="${s}${t ? '-' + t : ''}"><h2>${NAMES[s]}${t ? ` <span>· ${t[0].toUpperCase() + t.slice(1)}</span>` : ''}</h2>
        <div class="frames"><div class="fr ph-fr"><iframe src="${src('ph')}" title="${s} phone" loading="lazy"></iframe><span>Phone · 390</span></div>
        <div class="fr dk-fr"><div class="dk-scale"><iframe src="${src('dk')}" title="${s} desktop" loading="lazy"></iframe></div><span>Desktop · 1440</span></div></div></section>`);
    }
  }
  document.body.innerHTML = `<header class="vbar"><b>${document.title}</b><nav>${GA.screens.map(s => `<a href="#${s === 'trip' ? 'trip-scrapbook' : s}">${NAMES[s].split(' · ')[1]}</a>`).join('')}</nav>
    <button class="btn tonal sm" id="mode">${GA.I(mode === 'light' ? 'moon' : 'sun')}<span>${mode === 'light' ? 'Dark' : 'Light'}</span></button></header>
    <main class="vmain">${document.getElementById('notes').innerHTML}${rows.join('')}</main>`;
  document.getElementById('mode').onclick = () => { localStorage.setItem('reskin-mode', mode === 'light' ? 'dark' : 'light'); location.search = ''; };
})();
