// The cover's one stage (F-227, docs/decisions.md D-426..): one product frame stays pinned (CSS position: sticky) while the three parts pass it;
// the frame cross-fades between them. All this script does is watch which part's words (its card, not the tall block around it: D-456) cross a
// line on the screen (an IntersectionObserver: no layout read, no style written), say so on the stage (data-part, which cover.css fades on the
// --motion-* tokens), and give a part's screen and words .go the first time they show, which starts their moments and beats once (the sentence
// typing, the squares filling, the headline's phrases marked as the screen shows them, D-457). Where the browser has view transitions and motion
// is allowed, the change of part is one: cover.css names only the one trip that carries the story, so it grows from the lit square into the
// family's square into the card to post.
(function () {
  const root = document.documentElement, stage = document.querySelector('.cv-stage');
  if (!stage) return;
  const parts = [...stage.querySelectorAll('.cv-ch')];
  const layer = (n) => stage.querySelector(`.cv-L[data-n="${n}"]`);
  const words = (n) => stage.querySelector(`.cv-ch[data-n="${n}"]`);
  const wide = matchMedia('(min-width: 1100px)');           // cover.css puts the words beside the frame from here; under it they pass under the frame
  const calm = matchMedia('(prefers-reduced-motion: reduce)');
  let vt = null, want = stage.dataset.part;                 // want: the part the frame is going to (a view transition sets data-part a moment later)
  function go(n) { layer(n).classList.add('go'); words(n).classList.add('go'); }
  function show(n) {
    if (want === n) { go(n); return; }                       // part 1 is on the frame from the first paint; it plays when its words reach the line
    want = n;
    const swap = () => { stage.dataset.part = n; go(n); };
    if (!document.startViewTransition || calm.matches) { swap(); return; }
    if (vt) vt.skipTransition();                              // a quick reader: the last change wins, never a queue of morphs
    const t = vt = document.startViewTransition(swap);
    t.finished.finally(() => { if (vt === t) vt = null; });
  }
  let io;
  function watch() {      // the line: a band across the middle of a laptop's screen; on a phone, low, under the pinned frame
    if (io) io.disconnect();
    io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) show(e.target.closest('.cv-ch').dataset.n); }),
      { rootMargin: wide.matches ? '-42% 0px -42% 0px' : '-70% 0px -29% 0px' });
    parts.forEach((p) => io.observe(p.querySelector('.cv-card')));
  }
  if (root.classList.contains('cv-film')) {
    stage.classList.add('cv-live');                          // the words wait dimmed only once this script picks the part (cover.css)
    watch();
    wide.addEventListener('change', watch);
  }
  // every tap is a moment (cover.css): a heart, "This one" and Booked throw confetti when pressed; two class names for one animation, so a second tap starts it again
  stage.addEventListener('pointerdown', (e) => {
    const t = e.target.closest('.cv-hf, .cv-pill, .cv-book');
    if (t) { const a = t.classList.contains('tap-a'); t.classList.toggle('tap-a', !a); t.classList.toggle('tap-b', a); }
  });
  // a scene out of sight stands still: the sun, clouds and sea only move while someone can see them
  const scenes = document.querySelectorAll('.cv-scene');
  if (scenes.length) {
    const seen = new IntersectionObserver((es) => es.forEach((e) => e.target.classList.toggle('cv-off', !e.isIntersecting)));
    scenes.forEach((c) => seen.observe(c));
  }
  window.GA_COVER ={ part: () => stage.dataset.part, film: () => root.classList.contains('cv-film') };
})();
