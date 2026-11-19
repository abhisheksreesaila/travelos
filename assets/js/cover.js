// The cover's postcard (F-266, docs/briefs/cover-v3.md): one card travels four beats on a pinned stage (CSS position: sticky). All this script does is watch four markers
// with an IntersectionObserver, say which beat the story is on (data-beat and the custom property --k on the stage, which cover.css turns into the card's size, the ring's
// turn and the gallery's slots, and classes on the face, the words and the pager). It writes no transform, reads no layout and listens to no
// scroll. The faces are drawn by the server (gitaway/pages/cover.py); a face shown gets .on (visible) and .live (its moments play); the one it leaves keeps .live a moment,
// so it holds its last frame while it fades.
(function () {
  const root = document.documentElement, stage = document.querySelector('.stage');
  if (!stage) return;
  const all = (s) => [...stage.querySelectorAll(s)];
  const sides = all('.side'), caps = all('.cap'), dots = all('.pager button'), words = all('.ring text'), marks = [...document.querySelectorAll('.beats i')];
  const film = root.classList.contains('cv-film');
  const calm = matchMedia('(prefers-reduced-motion: reduce)');
  let beat = 0;
  const drop = new Map();      // a face that left: when it stops being .live
  function setBeat(k) {
    if (k === beat) return;
    beat = k;
    stage.dataset.beat = k;
    stage.style.setProperty('--k', k);
    sides.forEach((s, i) => {
      if (i === k) { clearTimeout(drop.get(s)); s.classList.add('on', 'live'); }
      else if (s.classList.contains('on')) { s.classList.remove('on'); drop.set(s, setTimeout(() => s.classList.remove('live'), 700)); }
    });
    caps.forEach((c, i) => { c.classList.toggle('now', i === k); c.classList.toggle('past', i < k); });
    words.forEach((w, i) => w.classList.toggle('now', i === k));
    dots.forEach((d, i) => { if (i === k) d.setAttribute('aria-current', 'step'); else d.removeAttribute('aria-current'); });
  }
  if (film && marks.length) {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) setBeat(+e.target.style.getPropertyValue('--k')); }), { rootMargin: '-50% 0px -50% 0px' });
    marks.forEach((m) => io.observe(m));
    dots.forEach((d, k) => d.addEventListener('click', () => marks[k].scrollIntoView({ behavior: calm.matches ? 'auto' : 'smooth', block: 'start' })));
  }
  // the wish: Enter sends it, Shift+Enter is a new line
  const wish = document.querySelector('.cv-wish textarea');
  if (wish) wish.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); wish.form.requestSubmit(); } });
  window.GA_COVER = { beat: () => beat, film: () => film };
})();
