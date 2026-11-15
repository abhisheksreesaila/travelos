// liquid.js: the small script of the liquid design kit (F-264), taken from GitAway's v2 (v2.js, v2top.js, motion.js, toast.js). Plain JavaScript, no dependencies. window.Lq:
//   Lq.mode.get() / set('dark') / toggle()      light or dark on <html data-mode>, kept in localStorage 'lq-mode', else the system's; any [data-lq-mode] button toggles it (aria-pressed when dark)
//   Lq.sky.set('snow') / quiet(true)            the sky's mood; <div class="lq-sky" data-mood="shore"> is drawn here (a sun that becomes a moon in the dark, clouds, one object at the foot)
//   Lq.sheet.open('id', source) / close()       a sheet or drawer (.lq-sheet): grows out of `source` on a phone, a calm fade on a laptop; [data-lq-sheet="id"] opens one, [data-lq-close] shuts it
//   Lq.motion.open(el, source) / close(el, source)   the one opening: used by sheets, menus and toasts. Resolves when it has landed (or gone)
//   menus: <button aria-controls="m" data-lq-menu> opens <div id="m" class="lq-menu" role="menu" hidden> with arrow keys, Escape and outside tap
//   Lq.combobox(input, { source: function (q) { return [{label, hint}] or a Promise }, onPick })   the search box's autocomplete; <input data-lq-combobox data-options='["a","b"]'> does it with a fixed list
//   Lq.toast('Saved', { undo: fn, error: true })    one toast at a time, with a clear Undo that stays twice as long
//   [data-lq-folds] > .lq-fold > button.lq-fold-h: one card open at a time (add data-many to allow several)
// Motion: nothing in this file is a time or a curve: durations and springs are read from the --lq-t-* and --lq-spring* tokens in liquid.css. Reduced motion: things simply appear and go.
(function () {
  if (window.Lq) return;
  var Lq = window.Lq = {};
  var root = document.documentElement;
  var reducedQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  function css(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function t(n) { var v = css(n); return v.slice(-2) === 'ms' ? parseFloat(v) : (v.slice(-1) === 's' ? parseFloat(v) * 1000 : parseFloat(v)) || 0; }
  function calm() { return window.innerWidth >= (parseFloat(css('--lq-calm-min')) || 1020); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }

  // ---------- mode ----------
  var KEY = 'lq-mode';
  Lq.mode = {
    get: function () { return root.getAttribute('data-mode') === 'dark' ? 'dark' : 'light'; },
    set: function (m, keep) {
      root.setAttribute('data-mode', m);
      $$('[data-lq-mode]').forEach(function (b) { b.setAttribute('aria-pressed', m === 'dark' ? 'true' : 'false'); });
      if (keep !== false) try { localStorage.setItem(KEY, m); } catch (e) { /* not stored: it still applies to this page */ }
    },
    toggle: function () { Lq.mode.set(Lq.mode.get() === 'dark' ? 'light' : 'dark'); }
  };
  (function () {
    var m = null;
    try { m = localStorage.getItem(KEY); } catch (e) { m = null; }
    if (m !== 'dark' && m !== 'light') m = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    Lq.mode.set(m, false);
  })();
  document.addEventListener('click', function (e) { if (e.target.closest('[data-lq-mode]')) Lq.mode.toggle(); });

  // ---------- the sky: its objects (the drawings are GitAway v2's, one per mood) ----------
  var CLOUD = '<path d="M20 44a16 16 0 0 1 2-32 22 22 0 0 1 40-4 18 18 0 0 1 32 10 13 13 0 0 1 6 26z"/>';
  function palm(x, y, s) {
    return '<g transform="translate(' + x + ' ' + y + ') scale(' + s + ')"><path d="M0 0 Q2 -14 6 -28" fill="none" stroke="#7A4E26" stroke-width="2.4" stroke-linecap="round"/><g fill="#1F8A5B">' +
      '<path d="M6 -28q-10-3-15 4 8-3 15-4z"/><path d="M6 -28q10-4 15 3-8-3-15-3z"/><path d="M6 -28q-5-9-13-8 8 2 13 8z"/><path d="M6 -28q4-10 12-9-8 2-12 9z"/></g></g>';
  }
  function burst(cx, cy, r, c, n) {
    var o = '';
    for (var i = 0; i < n; i++) {
      var a = 2 * Math.PI * i / n, ca = Math.cos(a), sa = Math.sin(a);
      o += '<path d="M' + Math.round(cx + ca * r * .45) + ' ' + Math.round(cy + sa * r * .45) + ' L' + Math.round(cx + ca * r) + ' ' + Math.round(cy + sa * r) + '" stroke="' + c + '" stroke-width="4" stroke-linecap="round"/>' +
        '<circle cx="' + Math.round(cx + ca * r + ca * 9) + '" cy="' + Math.round(cy + sa * r + sa * 9) + '" r="3.5" fill="' + c + '"/>';
    }
    return '<g>' + o + '<circle cx="' + cx + '" cy="' + cy + '" r="6" fill="' + c + '"/></g>';
  }
  function star(x, y, s, c) { return '<path transform="translate(' + x + ' ' + y + ') scale(' + s + ')" d="M0 -10 L2.6 -2.6 L10 0 L2.6 2.6 L0 10 L-2.6 2.6 L-10 0 L-2.6 -2.6Z" fill="' + c + '"/>'; }
  function skyline() {
    var back = [[0, 120], [90, 160], [170, 100], [260, 150], [350, 90], [440, 140], [520, 110], [620, 160], [720, 96], [820, 150], [910, 118], [1010, 164], [1100, 104], [1200, 148], [1290, 112], [1370, 150]];
    var front = [[30, 70], [130, 110], [230, 60], [330, 100], [430, 84], [560, 120], [660, 66], [780, 104], [880, 76], [980, 112], [1080, 62], [1190, 100], [1280, 78], [1370, 108]];
    var o = back.map(function (b) { return '<rect x="' + b[0] + '" y="' + (260 - b[1]) + '" width="' + (b[1] > 90 ? 70 : 56) + '" height="' + b[1] + '" fill="#AEB8D2" opacity=".6"/>'; }).join('');
    front.forEach(function (b) {
      var x = b[0], h = b[1], w = h > 80 ? 64 : 52;
      o += '<rect x="' + x + '" y="' + (260 - h) + '" width="' + w + '" height="' + h + '" fill="#6D7899"/>';
      for (var wx = 0; wx < 2; wx++) for (var wy = 0; wy < 3; wy++) if (wy * 22 + 30 < h && (wx + wy + Math.floor(x / 10)) % 3) o += '<rect x="' + (x + 10 + wx * 20) + '" y="' + (260 - h + 12 + wy * 22) + '" width="9" height="11" rx="1.5" fill="#FBE9B0"/>';
    });
    return o + '<rect x="0" y="244" width="1440" height="16" fill="#56607F"/>';
  }
  var SH = '<g transform="translate(-300 0)">';      // the objects sit near the middle, so a phone (which shows the middle 390 of the 1440) keeps them whole
  var FEET = {
    shore: '<path d="M0 120 Q160 70 330 110 T700 96 T1060 108 T1440 92 V260 H0Z" fill="#C9B9D9" opacity=".55"/><path d="M0 150 Q240 132 480 146 T960 140 T1440 148 V260 H0Z" fill="#A7D3EE"/><path d="M0 176 Q240 160 480 172 T960 166 T1440 174 V260 H0Z" fill="#78B8E3"/>' +
      '<rect x="120" y="128" width="380" height="6" fill="#2B3A4A"/>' + [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].map(function (i) { return '<rect x="' + (130 + i * 24) + '" y="134" width="4" height="40" fill="#2B3A4A"/>'; }).join('') +
      '<rect x="456" y="104" width="40" height="24" rx="2" fill="#E4572E"/><path d="M450 104h52l-26-14z" fill="#2B3A4A"/><path d="M0 214 Q300 190 640 206 T1440 200 V260 H0Z" fill="#F4D9A0"/>' +
      palm(1180, 214, 2.1) + palm(1240, 220, 1.6) + palm(1320, 212, 2.4) + palm(70, 222, 1.8) +
      '<g transform="translate(860 150)"><path d="M0 0 h60 l-8 10 h-44z" fill="#C2410C"/><path d="M28 0 V-46 L56 -4z" fill="#FFD43B"/><path d="M26 -2 V-38 L6 -4z" fill="#fff"/></g>',
    snow: SH + '<path d="M820 214 L1040 36 L1260 214Z" fill="#8FA8C8"/><path d="M1040 36 L1260 214 L1130 214 L1066 96Z" fill="#7893B8"/><path d="M1040 36 L994 76 L1016 70 L1040 94 L1062 68 L1086 80Z" fill="#FFFFFF"/>' +
      '<path d="M1170 214 L1290 104 L1410 214Z" fill="#A9BCD6"/><path d="M1290 104 L1254 138 L1274 132 L1290 148 L1308 130 L1326 140Z" fill="#FFFFFF"/></g>' +
      '<path d="M0 206 Q300 180 640 198 T1440 196 V260 H0Z" fill="#F7FAFE"/><path d="M0 232 Q320 212 700 228 T1440 222 V260 H0Z" fill="#E3ECF7"/>',
    hills: '<path d="M0 132 Q200 84 430 124 T900 104 T1440 122 V260 H0Z" fill="#BFD59B" opacity=".6"/>' + SH + '<path d="M760 214 L1000 46 L1240 214Z" fill="#7BA568"/><path d="M1000 46 L1240 214 L1110 214 L1030 96Z" fill="#5F8F54"/></g>' +
      '<path d="M0 196 Q360 164 720 188 T1440 180 V260 H0Z" fill="#E8D48A"/><path d="M0 234 Q360 214 760 230 T1440 224 V260 H0Z" fill="#D5BE6A"/>' +
      SH + '<path d="M880 250 C 960 232, 940 214, 1004 200 S 1040 160, 1004 138 S 1020 100, 1000 74" fill="none" stroke="#FFF3C4" stroke-width="7" stroke-linecap="round" stroke-dasharray="2 14"/>' +
      '<path d="M1000 74 V44 L1024 52 L1000 60" fill="#C92A5E" stroke="#C92A5E" stroke-width="2.5" stroke-linejoin="round"/></g>',
    party: burst(780, 96, 74, '#FFC83D', 12) + burst(570, 152, 42, '#FF7DA6', 10) + burst(960, 150, 40, '#6FD8EE', 10) + star(700, 90, 1.1, '#FFC83D') + star(560, 160, .9, '#FF7DA6') + star(1380, 70, 1, '#6FD8EE') +
      star(300, 120, .8, '#FFFFFF') + star(120, 70, 1, '#FFC83D') + '<path d="M0 228 Q360 216 720 226 T1440 222 V260 H0Z" fill="#3E2C72"/>',
    city: skyline()
  };
  var MOON = '<svg class="moon" viewBox="0 0 100 100"><defs><mask id="lq-moon-cut"><rect width="100" height="100" fill="#fff"/><circle cx="73" cy="36" r="34" fill="#000"/></mask></defs><circle cx="50" cy="50" r="42" fill="#F3EBD3" mask="url(#lq-moon-cut)"/>' +
    '<path d="M19 57 q5 5 10 0" fill="none" stroke="#6B5B3A" stroke-width="2.4" stroke-linecap="round"/><path d="M21 69 q3.5 3 7 0" fill="none" stroke="#6B5B3A" stroke-width="2.2" stroke-linecap="round"/><circle cx="15" cy="64" r="3.4" fill="#F4A9A0" opacity=".7"/>' +
    '<g class="zz" fill="#F3EBD3" font-family="Newsreader, Georgia, serif" font-weight="600"><text x="80" y="28" font-size="13">z</text><text x="89" y="15" font-size="10">z</text></g></svg>';
  var STARS = [[70, 40, 2.4], [160, 110, 1.8], [260, 30, 2.2], [330, 150, 1.6], [430, 70, 2.6], [520, 20, 1.8], [610, 120, 2.2], [700, 50, 1.6], [790, 140, 2.4], [880, 24, 1.8], [960, 96, 2.2], [1040, 170, 1.6], [1130, 40, 2.4], [1240, 120, 1.8], [1330, 60, 2.2], [1400, 150, 1.6]];
  function cloud(style) { return '<svg class="cloud" style="' + style + '" viewBox="0 0 120 50">' + CLOUD + '</svg>'; }
  function drawSky(el) {
    if (!el.querySelector('.sun')) {
      el.innerHTML = '<div class="sun"></div>' + MOON +
        '<svg class="stars" viewBox="0 0 1440 220" preserveAspectRatio="xMidYMin slice">' + STARS.map(function (s, i) { return '<circle cx="' + s[0] + '" cy="' + s[1] + '" r="' + s[2] + '" style="--i:' + i + '"/>'; }).join('') + '</svg>' +
        cloud('left:6%;top:9%;width:170px') + cloud('left:58%;top:22%;width:120px;animation-duration:80s') + cloud('left:28%;top:44%;width:200px;animation-duration:95s') + '<svg class="foot" viewBox="0 0 1440 260" preserveAspectRatio="xMidYMax slice"></svg>';
    }
    var mood = FEET[el.getAttribute('data-mood')] ? el.getAttribute('data-mood') : 'shore';
    el.setAttribute('data-mood', mood);
    el.querySelector('.foot').innerHTML = FEET[mood];
  }
  Lq.sky = {
    moods: Object.keys(FEET),
    set: function (mood) { var el = $('.lq-sky'); if (el) { el.setAttribute('data-mood', mood); drawSky(el); } },
    quiet: function (on) { var el = $('.lq-sky'); if (el) el.classList.toggle('is-quiet', on !== false); }
  };
  $$('.lq-sky').forEach(drawSky);
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-lq-mood]');
    if (!b) return;
    Lq.sky.quiet(false); Lq.sky.set(b.getAttribute('data-lq-mood'));
    $$('[data-lq-mood],[data-lq-quiet]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-lq-quiet]');
    if (!b) return;
    Lq.sky.quiet(true);
    $$('[data-lq-mood],[data-lq-quiet]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
  });

  // ---------- the one opening ----------
  // A phone: the thing is already at its final place, clipped to the rectangle of its source and let out on the soft spring, so it grows from what was tapped and its words never stretch.
  // A laptop: a short fade, nothing grows. Closing folds back into the source (a phone) or fades (a laptop).
  var last = null;      // the thing tapped a moment ago: a toast, which nobody tapped, grows from it
  document.addEventListener('pointerdown', function (e) { last = e.target.closest ? e.target.closest('button, a, [role=button]') : null; }, true);
  function clipFrom(el, src) {
    var r = el.getBoundingClientRect(), s = src && src.getBoundingClientRect ? src.getBoundingClientRect() : null;
    if (!s || !s.width || s.bottom < 0 || s.top > window.innerHeight) return null;
    var cl = function (v, max) { return Math.max(0, Math.min(v, max - 1)); };
    var rad = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0;
    return { clip: 'inset(' + cl(s.top - r.top, r.height) + 'px ' + cl(r.right - s.right, r.width) + 'px ' + cl(r.bottom - s.bottom, r.height) + 'px ' + cl(s.left - r.left, r.width) + 'px round ' + Math.min(rad, s.height / 2) + 'px)',
      dx: (s.left + s.width / 2 - r.left - r.width / 2) * .3, dy: (s.top + s.height / 2 - r.top - r.height / 2) * .3, rad: rad };
  }
  var motion = Lq.motion = {
    open: function (el, src) {
      el.getAnimations().forEach(function (a) { a.cancel(); });
      if (reducedQ.matches || !el.animate) return Promise.resolve();
      if (calm()) return el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: t('--lq-t-calm'), easing: 'ease-out' }).finished.catch(function () {});
      var f = clipFrom(el, src), full = 'inset(0px 0px 0px 0px round ' + (f ? f.rad : 0) + 'px)';
      var kf = f ? [{ clipPath: f.clip, transform: 'translate(' + f.dx + 'px,' + f.dy + 'px) scale(.92)', opacity: .4 }, { clipPath: full, transform: 'none', opacity: 1 }]
        : [{ transform: 'translateY(2.5rem)', opacity: 0 }, { transform: 'none', opacity: 1 }];
      return el.animate(kf, { duration: t('--lq-t-sheet'), easing: css('--lq-spring-soft') }).finished.catch(function () {});
    },
    close: function (el, src) {
      el.getAnimations().forEach(function (a) { a.cancel(); });
      if (reducedQ.matches || !el.animate) return Promise.resolve();
      if (calm()) return el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: t('--lq-t-calm'), easing: 'ease-in', fill: 'forwards' }).finished.catch(function () {});
      var f = clipFrom(el, src);
      var kf = f ? [{ clipPath: 'inset(0px 0px 0px 0px round ' + f.rad + 'px)', transform: 'none', opacity: 1 }, { clipPath: f.clip, transform: 'translate(' + f.dx + 'px,' + f.dy + 'px) scale(.92)', opacity: 0 }]
        : [{ transform: 'none', opacity: 1 }, { transform: 'translateY(2.5rem)', opacity: 0 }];
      return el.animate(kf, { duration: t('--lq-t-out'), easing: css('--lq-ease'), fill: 'forwards' }).finished.catch(function () {});
    }
  };

  // ---------- sheets and drawers ----------
  var scrim = null, openSheet = null, sheetSrc = null;
  function getScrim() { if (!scrim) { scrim = document.createElement('div'); scrim.className = 'lq-scrim'; document.body.appendChild(scrim); scrim.addEventListener('click', function () { Lq.sheet.close(); }); } return scrim; }
  Lq.sheet = {
    open: function (id, src) {
      var el = document.getElementById(id);
      if (!el) return;
      if (openSheet && openSheet !== el) Lq.sheet.close(true);
      openSheet = el; sheetSrc = src || last;
      el.hidden = false; el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); el.tabIndex = -1;
      getScrim().classList.add('on');
      if (src && src.setAttribute) src.setAttribute('aria-expanded', 'true');
      motion.open(el, sheetSrc);
      el.focus({ preventScroll: true });      // the sheet itself, never a field: nothing jumps
    },
    close: function (instant) {
      var el = openSheet, src = sheetSrc;
      if (!el) return;
      openSheet = null; sheetSrc = null;
      getScrim().classList.remove('on');
      if (src && src.setAttribute) src.setAttribute('aria-expanded', 'false');
      var done = function () { if (openSheet !== el) el.hidden = true; };
      if (instant) { el.getAnimations().forEach(function (a) { a.cancel(); }); done(); } else motion.close(el, src).then(done);
      if (src && src.focus) src.focus({ preventScroll: true });
    }
  };
  document.addEventListener('click', function (e) {
    var o = e.target.closest('[data-lq-sheet]');
    if (o) { Lq.sheet.open(o.getAttribute('data-lq-sheet'), o); return; }
    if (e.target.closest('[data-lq-close]')) Lq.sheet.close();
  });
  document.addEventListener('keydown', function (e) {
    if (!openSheet) return;
    if (e.key === 'Escape') { e.preventDefault(); Lq.sheet.close(); return; }
    if (e.key !== 'Tab') return;      // keep Tab inside the open sheet
    var f = $$('a[href], button:not(:disabled), input, [tabindex]:not([tabindex="-1"])', openSheet);
    if (!f.length) { e.preventDefault(); return; }
    var first = f[0], lastEl = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === openSheet)) { e.preventDefault(); lastEl.focus(); }
    else if (!e.shiftKey && document.activeElement === lastEl) { e.preventDefault(); first.focus(); }
  });

  // ---------- menus (the avatar's) ----------
  var menuOpen = null;
  function menuItems(m) { return $$('[role=menuitem]', m); }
  function closeMenu(refocus) {
    if (!menuOpen) return;
    var m = menuOpen.menu, b = menuOpen.btn; menuOpen = null;
    b.setAttribute('aria-expanded', 'false');
    motion.close(m, b).then(function () { if (!menuOpen || menuOpen.menu !== m) m.hidden = true; });
    if (refocus) b.focus();
  }
  function openMenu(b) {
    var m = document.getElementById(b.getAttribute('aria-controls'));
    if (!m) return;
    closeMenu(false);
    m.hidden = false; menuOpen = { menu: m, btn: b }; b.setAttribute('aria-expanded', 'true');
    motion.open(m, b);
    var f = menuItems(m)[0]; if (f) f.focus();
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-lq-menu]');
    if (b) { if (menuOpen && menuOpen.btn === b) closeMenu(true); else openMenu(b); return; }
    if (menuOpen && !menuOpen.menu.contains(e.target)) closeMenu(false);
  });
  document.addEventListener('keydown', function (e) {
    var b = e.target.closest && e.target.closest('[data-lq-menu]');
    if (b && e.key === 'ArrowDown') { e.preventDefault(); openMenu(b); return; }
    if (!menuOpen) return;
    var list = menuItems(menuOpen.menu), i = list.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.preventDefault(); closeMenu(true); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); list[(i + 1) % list.length].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); list[(i - 1 + list.length) % list.length].focus(); }
    else if (e.key === 'Home') { e.preventDefault(); list[0].focus(); }
    else if (e.key === 'End') { e.preventDefault(); list[list.length - 1].focus(); }
    else if (e.key === 'Tab') closeMenu(false);
  });

  // ---------- one card open at a time ----------
  document.addEventListener('click', function (e) {
    var h = e.target.closest('.lq-fold-h');
    if (!h) return;
    var card = h.closest('.lq-fold'), set = card.closest('[data-lq-folds]'), will = !card.classList.contains('is-open');
    if (set && !set.hasAttribute('data-many')) $$('.lq-fold.is-open', set).forEach(function (o) { o.classList.remove('is-open'); $('.lq-fold-h', o).setAttribute('aria-expanded', 'false'); });
    card.classList.toggle('is-open', will); h.setAttribute('aria-expanded', String(will));
  });

  // ---------- the combobox ----------
  var uid = 0;
  Lq.combobox = function (input, o) {
    var list = document.getElementById(input.getAttribute('aria-controls')), items = [], active = -1, shown = false, seq = 0, id = 'lq-o' + (++uid) + '-';
    input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list'); input.setAttribute('aria-expanded', 'false'); input.setAttribute('autocomplete', 'off');
    list.setAttribute('role', 'listbox');
    function setActive(n) {
      active = n;
      $$('[role=option]', list).forEach(function (x, i) { x.setAttribute('aria-selected', String(i === n)); });
      if (n >= 0) { input.setAttribute('aria-activedescendant', id + n); var x = document.getElementById(id + n); if (x && x.scrollIntoView) x.scrollIntoView({ block: 'nearest' }); } else input.removeAttribute('aria-activedescendant');
    }
    function hide() { if (!shown) return; shown = false; list.hidden = true; input.setAttribute('aria-expanded', 'false'); setActive(-1); }
    function draw(r) {
      items = r || [];
      if (!items.length) { hide(); return; }
      list.innerHTML = items.map(function (it, i) { return '<li role="option" id="' + id + i + '" class="lq-opt" aria-selected="false" data-i="' + i + '"><span>' + esc(it.label) + '</span>' + (it.hint ? '<small>' + esc(it.hint) + '</small>' : '') + '</li>'; }).join('');
      var was = shown; shown = true; list.hidden = false; input.setAttribute('aria-expanded', 'true'); setActive(-1);
      if (!was && !reducedQ.matches) list.animate([{ opacity: 0, transform: 'translateY(-0.375rem) scale(.98)' }, { opacity: 1, transform: 'none' }], { duration: t('--lq-t-pop'), easing: css('--lq-ease') });
    }
    function ask() { var n = ++seq; Promise.resolve(o.source(input.value)).then(function (r) { if (n === seq) draw(r); }); }
    function pick(i) { var it = items[i]; if (!it) return; input.value = it.label; hide(); if (o.onPick) o.onPick(it); input.focus(); }      // choosing only sets the box; Search is its own button
    input.addEventListener('input', ask);
    input.addEventListener('focus', function () { if (input.value) ask(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (!shown) ask(); else setActive((active + 1) % items.length); }
      else if (e.key === 'ArrowUp' && shown) { e.preventDefault(); setActive((active - 1 + items.length) % items.length); }
      else if (e.key === 'Enter' && shown && active >= 0) { e.preventDefault(); pick(active); }
      else if (e.key === 'Escape' && shown) { e.preventDefault(); e.stopPropagation(); hide(); }
    });
    list.addEventListener('pointerdown', function (e) { e.preventDefault(); });      // the box keeps focus
    list.addEventListener('click', function (e) { var x = e.target.closest('[role=option]'); if (x) pick(+x.getAttribute('data-i')); });
    document.addEventListener('pointerdown', function (e) { if (shown && !list.contains(e.target) && !input.contains(e.target)) hide(); });
    input.addEventListener('blur', function () { setTimeout(function () { if (document.activeElement !== input) hide(); }, 0); });
  };
  $$('[data-lq-combobox]').forEach(function (input) {
    var opts = [];
    try { opts = JSON.parse(input.getAttribute('data-options') || '[]'); } catch (e) { opts = []; }
    Lq.combobox(input, { source: function (q) {
      q = q.trim().toLowerCase();
      return opts.filter(function (x) { return !q || String(x.label || x).toLowerCase().indexOf(q) >= 0; }).map(function (x) { return typeof x === 'string' ? { label: x } : x; }).slice(0, 6);
    } });
  });

  // ---------- toasts ----------
  var toast = null, toastT = 0;
  function live() { var r = $('.lq-toasts'); if (!r) { r = document.createElement('div'); r.className = 'lq-toasts'; r.setAttribute('role', 'status'); r.setAttribute('aria-live', 'polite'); document.body.appendChild(r); } return r; }
  function hideToast(instant) {
    clearTimeout(toastT);
    var el = toast; if (!el) return; toast = null;
    var gone = function () { if (el.parentNode) el.parentNode.removeChild(el); };
    if (instant) gone(); else motion.close(el, last).then(gone);
  }
  Lq.hideToast = hideToast;
  Lq.toast = function (text, o) {
    o = o || {};
    hideToast(true);
    var el = document.createElement('div');
    el.className = 'lq-toast' + (o.error ? ' is-error' : '');
    el.innerHTML = '<span class="lq-toast-t">' + esc(text) + '</span>' + (o.undo ? '<button type="button">Undo</button>' : '');
    live().appendChild(el); toast = el;
    motion.open(el, last);
    var arm = function () { clearTimeout(toastT); toastT = setTimeout(function () { if (toast === el) hideToast(); }, t(o.undo ? '--lq-t-toast-undo' : '--lq-t-toast')); };
    arm();
    el.addEventListener('pointerenter', function () { clearTimeout(toastT); }); el.addEventListener('pointerleave', arm);
    el.addEventListener('focusin', function () { clearTimeout(toastT); }); el.addEventListener('focusout', arm);
    var b = $('button', el);
    if (b) b.addEventListener('click', function () { hideToast(); o.undo(); });
    return el;
  };
  document.addEventListener('click', function (e) {      // a button that only says it: <button data-lq-toast="Saved" data-undo>
    var b = e.target.closest('[data-lq-toast]');
    if (b) Lq.toast(b.getAttribute('data-lq-toast'), { undo: b.hasAttribute('data-undo') ? function () { Lq.toast('Undone'); } : null, error: b.hasAttribute('data-error') });
  });
  Lq.ready = true;
})();
