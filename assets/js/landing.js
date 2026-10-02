/* Landing (F-060): feature tiles that play on touch, and the shared calendar that plans itself.
   Plain JS. Without it the page is complete: every plan block is filled and the tiles animate on hover and focus in CSS. */
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasIO = 'IntersectionObserver' in window;

  /* Touch screens have no hover: play each tile once as it scrolls into view, and again on tap. */
  var feats = document.querySelectorAll('.feature');
  feats.forEach(function (f) { f.addEventListener('click', function () { f.classList.toggle('play'); }); });
  if (!reduce && hasIO && window.matchMedia('(hover: none)').matches) {
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('play'); seen.unobserve(e.target); }
      });
    }, { threshold: 0.6 });
    feats.forEach(function (f) { seen.observe(f); });
  }

  /* The calendar: four people drop plans in, and each block fills top to bottom, until three days are full. Then it loops.
     It rests complete (every block has .on from the server) until it scrolls into view, and under reduced motion it never starts. */
  var cal = document.getElementById('cal');
  if (!cal || reduce) return;
  var steps = [['Priya', 's1'], ['Mom', 's2'], ['Kid', 's5'], ['Dad', 's3'], ['Kid', 's4'], ['Mom', 's6'], ['Priya', 's7']];
  var STEP = 1100, LEAD = 600, FILL = 800, REST = 3500;
  var slots = cal.querySelectorAll('.slot[data-s]');
  var cursors = {};
  var timers = [];
  var visible = false, waiting = false;

  cal.getAttribute('data-people').split(',').forEach(function (pair, i) {
    var name = pair.split(':')[0], color = pair.split(':')[1];
    var c = document.createElement('div');
    c.className = 'cursor';
    c.setAttribute('aria-hidden', 'true');
    c.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 3l7 18 2.5-7.5L21 11z" style="fill:var(--' + color + ')" stroke="#1E1A2E" stroke-width="1.6" stroke-linejoin="round"/></svg>' +
      '<span class="tag" style="background:var(--' + color + ')">' + name + '</span>';
    c.style.opacity = '0';
    c.style.transform = 'translate(' + (i % 2 ? cal.clientWidth - 40 : 10) + 'px,' + (i < 2 ? -10 : cal.clientHeight - 20) + 'px)';
    cal.appendChild(c);
    cursors[name] = c;
  });

  function slot(id) { return cal.querySelector('[data-s="' + id + '"]'); }
  function moveTo(name, el) {
    var r = el.getBoundingClientRect(), c = cal.getBoundingClientRect();
    cursors[name].style.opacity = '1';
    cursors[name].style.transform = 'translate(' + (r.left - c.left + r.width * 0.55) + 'px,' + (r.top - c.top + r.height * 0.45) + 'px)';
  }
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
  function stop() { timers.forEach(clearTimeout); timers = []; }

  function run() {
    stop();
    waiting = false;
    cal.setAttribute('data-state', 'playing');
    slots.forEach(function (s) { s.classList.remove('on'); });
    steps.forEach(function (st, i) {
      var t = LEAD + i * STEP;
      later(function () { moveTo(st[0], slot(st[1])); }, t);
      later(function () { slot(st[1]).classList.add('on'); }, t + FILL);
    });
    /* Everyone has finished: rest complete for a moment, then loop (only while someone is looking). */
    later(function () {
      cal.setAttribute('data-state', 'resting');
      Object.keys(cursors).forEach(function (n) { cursors[n].style.opacity = '0'; });
    }, LEAD + steps.length * STEP + FILL);
    later(function () { if (visible) run(); else waiting = true; }, LEAD + steps.length * STEP + FILL + REST);
  }

  var replay = document.getElementById('replay');
  if (replay) replay.addEventListener('click', run);
  if (hasIO) {
    var started = false;
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
      if (visible && (!started || waiting)) { started = true; run(); }
    }, { threshold: 0.4 }).observe(cal);
  }
})();
