// The cover's one stage (F-227, docs/decisions.md D-426..): one product frame stays pinned (CSS position: sticky) while the three parts scroll past;
// the frame cross-fades between them. All this script does is watch which part's words cross a line on the screen (an IntersectionObserver: no
// scroll listener, no layout read, no transform written), say so on the stage (data-part, which cover.css fades on the --motion-* tokens), and give
// a part .go the first time it shows, which starts its small moments once (the sentence typing, the squares filling, the hearts landing).
(function () {
  const root = document.documentElement, stage = document.querySelector('.cv-stage');
  if (!stage) return;
  const parts = [...stage.querySelectorAll('.cv-ch')], frame = stage.querySelector('.cv-frame');
  const layer = (n) => stage.querySelector(`.cv-L[data-n="${n}"]`);
  const wide = matchMedia('(min-width: 1100px)');           // cover.css puts the words beside the frame from here; under it they pass under the frame
  function show(n) {
    if (stage.dataset.part === n) return;
    stage.dataset.part = n;
    layer(n).classList.add('go');
  }
  let io;
  function watch() {                                        // the line: the middle of a laptop's screen; on a phone, low, under the pinned frame
    if (io) io.disconnect();
    io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) show(e.target.dataset.n); }),
      { rootMargin: wide.matches ? '-50% 0px -49% 0px' : '-70% 0px -29% 0px' });
    parts.forEach((p) => io.observe(p));
  }
  if (root.classList.contains('cv-film')) {
    watch();
    wide.addEventListener('change', watch);
    const first = new IntersectionObserver((es) => {         // the first part plays as soon as the frame is well on screen
      if (es.some((e) => e.isIntersecting)) { layer(stage.dataset.part).classList.add('go'); first.disconnect(); }
    }, { threshold: 0.4 });
    first.observe(frame);
  }
  window.GA_COVER = { part: () => stage.dataset.part, film: () => root.classList.contains('cv-film') };
})();
