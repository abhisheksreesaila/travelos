"""F-200: what a page looks like to a person, measured in the browser (the sweep in test_direction_a_pages.py uses it).

audit(page) returns, for the page as drawn:
    wide    how far the page scrolls sideways (px; 1 or less is none)
    small   phone tap targets under 48px (only under 720px wide): "name WxH"
    tiny    text under the type scale's floor on the phone: running text (a paragraph, a list item, a label, a button, a field, or anything of
            four words or more) under 16px, fine print (`small`, `.ga-fine`) under 14px, all-caps labels (uppercase, by style or by its letters) and everything else under 13px
    low     text under 4.5:1 against what is painted behind it: "text (ratio, colour on background)"
    glass   elements drawn with a backdrop blur or a blur filter

Contrast reads the text's own colour (with its alpha and the opacity of the element and its ancestors) over what is painted behind the text: the
page is scrolled through and `elementsFromPoint` at the text gives the layers under it (a sliding thumb, a card, the page), composited down to the
first opaque one. Text never seen in the window (inside a box that scrolls by itself) falls back to its ancestors' backgrounds. Text over a picture
or a gradient is skipped (there is no one colour to measure), as is the text of a disabled control. An inline link inside a sentence is not a tap
target of its own (WCAG 2.5.8's inline exception). The audit scrolls the window back to the top and leaves the page as it found it.
"""

AUDIT = r"""async () => {
  const phone = innerWidth < 720, doc = document.documentElement;
  const out = {wide: doc.scrollWidth - doc.clientWidth, small: [], tiny: [], low: [], glass: []};
  const cv = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const parse = c => {
    let m = c.match(/^rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)$/);
    if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
    m = c.match(/^color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.e-]+))?\)$/);
    if (m) return [m[1] * 255, m[2] * 255, m[3] * 255, m[4] === undefined ? 1 : +m[4]];
    cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1);
    const d = cv.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const over = (top, under) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + under[i] * (1 - a)).concat(1); };
  const lum = c => { const l = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = c => '#' + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
  const base = (() => { const h = parse(getComputedStyle(doc).backgroundColor); return h[3] > 0 ? over(h, [255, 255, 255, 1]) : [255, 255, 255, 1]; })();
  const PICTURE = new Set(['IMG', 'VIDEO', 'CANVAS', 'IFRAME', 'OBJECT', 'EMBED', 'PICTURE']);
  const pseudo = (e, which, pt) => {                // a ::before or ::after that paints a fill under the text (a sliding thumb): [colour, painted under the element's own fill]
    const p = getComputedStyle(e, which);
    if (p.content === 'none' || p.display === 'none' || p.visibility !== 'visible') return null;
    const c = parse(p.backgroundColor), img = p.backgroundImage && p.backgroundImage !== 'none';
    if (c[3] === 0 && !img) return null;
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    let box = null;
    if ((p.position === 'absolute' || p.position === 'fixed') && /px$/.test(p.width) && /px$/.test(p.height)) {
      const x = r.left + parseFloat(s.borderLeftWidth) + (parseFloat(p.left) || 0), y = r.top + parseFloat(s.borderTopWidth) + (parseFloat(p.top) || 0);
      box = [x, y, parseFloat(p.width), parseFloat(p.height)];
    }
    const covers = pt && box ? (pt[0] >= box[0] && pt[0] <= box[0] + box[2] && pt[1] >= box[1] && pt[1] <= box[1] + box[3])
                             : parseFloat(p.width) >= r.width * 0.9 && parseFloat(p.height) >= r.height * 0.9;
    if (!covers) return null;
    return img ? [null, false] : [c, parseInt(p.zIndex, 10) < 0];
  };
  const flatten = (layers, pt) => {                       // the layers from the text down: composite them onto the first opaque one (or the page)
    const stack = [];
    for (const e of layers) {
      if (PICTURE.has(e.tagName)) return null;
      const s = getComputedStyle(e);
      if (s.backgroundImage && s.backgroundImage !== 'none') return null;
      const own = parse(s.backgroundColor), marks = [pseudo(e, '::after', pt), pseudo(e, '::before', pt)].filter(Boolean);
      if (marks.some(m => m[0] === null)) return null;
      const fills = [...marks.filter(m => !m[1]).map(m => m[0]), own, ...marks.filter(m => m[1]).map(m => m[0])];
      let opaque = false;
      for (const c of fills) {
        if (c[3] > 0) stack.push(c);
        if (c[3] >= 1) { opaque = true; break; }
      }
      if (opaque) break;
    }
    let bg = stack.length && stack[stack.length - 1][3] >= 1 ? stack.pop() : base;
    while (stack.length) bg = over(stack.pop(), bg);
    return bg;
  };
  const ancestors = el => { const a = []; for (let e = el; e && e.nodeType === 1; e = e.parentElement) a.push(e); return a; };
  const shown = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return null;
    const s = getComputedStyle(el);
    if (s.visibility !== 'visible' || s.clip === 'rect(0px, 0px, 0px, 0px)' || s.clipPath === 'inset(50%)') return null;
    if (r.bottom + scrollY < 0 || r.right + scrollX < 0) return null;
    return r;
  };
  const fade = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const name = el => ((el.getAttribute('aria-label') || el.value || el.textContent || el.id || el.tagName).replace(/\s+/g, ' ').trim()).slice(0, 48);
  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'TITLE', 'OPTION', 'OPTGROUP']);
  const FIELD = 'input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=range]):not([type=file]):not([type=color]):not([type=submit]):not([type=button]), textarea, select';
  const RUNNING = new Set(['P', 'LI', 'DD', 'BLOCKQUOTE', 'FIGCAPTION', 'LABEL', 'TD', 'TH', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT']);

  const items = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (SKIP.has(el.tagName) || el instanceof SVGElement) continue;
    const s = getComputedStyle(el);
    if ((s.backdropFilter && s.backdropFilter !== 'none') || (s.webkitBackdropFilter && s.webkitBackdropFilter !== 'none') || /blur\(/.test(s.filter || '')) out.glass.push(name(el));
    const field = el.matches(FIELD);
    const node = field ? null : [...el.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
    const text = field ? (el.tagName === 'SELECT' ? (el.selectedOptions[0] || {}).text || '' : el.value) : node ? [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ') : '';
    if (!text.trim() || !shown(el) || el.closest('[disabled], [aria-disabled="true"]') || fade(el) < 0.05) continue;     // a see-through (opacity 0) part is not on screen
    const size = parseFloat(s.fontSize), words = text.trim().split(/\s+/).length;
    if (phone) {
      const fine = el.closest('small, .ga-fine'), label = s.textTransform === 'uppercase' || (/[A-Z]/.test(text) && text === text.toUpperCase());
      const min = label ? 13 : fine ? 14 : (RUNNING.has(el.tagName) || words >= 4) ? 16 : 13;
      if (size < min - 0.05) out.tiny.push(`${text.trim().slice(0, 40)} (${size}px < ${min})`);
    }
    if (parse(s.color)[3] > 0) items.push({el, node, text: text.trim()});
  }

  const point = it => {                             // the middle of the text's first line, in the window
    if (!it.node) { const r = it.el.getBoundingClientRect(); return [r.left + Math.min(12, r.width / 2), r.top + r.height / 2]; }
    const range = document.createRange(); range.selectNodeContents(it.node);
    const r = [...range.getClientRects()].find(q => q.width > 0 && q.height > 0);
    return r ? [r.left + r.width / 2, r.top + r.height / 2] : null;
  };
  const free = document.createElement('style');
  free.textContent = '*, *::before, *::after { pointer-events: auto !important; scroll-behavior: auto !important; }';   // so a decorative layer (a thumb) is found under the text
  document.head.appendChild(free);
  const look = it => {                              // what is painted under the text where it sits now, or undefined when it is out of the window or covered
    const p = point(it);
    if (!p || p[0] < 1 || p[1] < 1 || p[0] > innerWidth - 1 || p[1] > innerHeight - 1) return undefined;
    const stack = document.elementsFromPoint(p[0], p[1]);
    const i = stack.indexOf(it.el);
    if (i < 0) return undefined;
    const covered = stack.slice(0, i).some(e => !it.el.contains(e) && !e.contains(it.el) && (PICTURE.has(e.tagName) || parse(getComputedStyle(e).backgroundColor)[3] >= 1));
    return covered ? undefined : flatten(stack.slice(i), p);   // covered: something opaque sits over the text here (a sticky bar)
  };
  const scrolled = [...document.querySelectorAll('*')].filter(e => e.scrollHeight > e.clientHeight || e.scrollWidth > e.clientWidth).map(e => [e, e.scrollLeft, e.scrollTop]);
  const done = new Map(), top0 = scrollY, left0 = scrollX, step = Math.max(200, innerHeight / 2);
  const span = Math.max(0, doc.scrollHeight - innerHeight);
  for (let y = 0; ; y = Math.min(span, y + step)) {
    scrollTo(left0, y);
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    for (const it of items) {
      if (done.has(it)) continue;
      const bg = look(it);
      if (bg !== undefined) done.set(it, bg);
    }
    if (y >= span) break;
  }
  for (const it of items) {                         // text inside a box that scrolls by itself (a row of cards, a panel): bring it into view once
    if (done.has(it)) continue;
    it.el.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});
    const bg = look(it);
    if (bg !== undefined) done.set(it, bg);
  }
  for (const [e, x, y] of scrolled) { e.scrollLeft = x; e.scrollTop = y; }
  scrollTo(left0, top0);
  free.remove();
  for (const it of items) {
    const bg = done.has(it) ? done.get(it) : flatten(ancestors(it.el));
    if (!bg) continue;
    const s = getComputedStyle(it.el);
    let fg = over(parse(s.color), bg);
    const o = fade(it.el);
    if (o < 1) fg = over([fg[0], fg[1], fg[2], o], bg);
    const k = ratio(fg, bg);
    if (k < 4.5) out.low.push(`${it.text.slice(0, 40)} (${k.toFixed(2)}, ${hex(fg)} on ${hex(bg)})`);
  }

  if (phone) {
    const TAPS = 'a[href], button, summary, select, textarea, input:not([type=hidden]):not([type=checkbox]):not([type=radio]), [role=button], [role=tab], [role=link], label:has(> input[type=checkbox]), label:has(> input[type=radio])';
    for (const el of document.body.querySelectorAll(TAPS)) {
      const r = shown(el);
      if (!r || r.width <= 4 || r.height <= 4) continue;
      const s = getComputedStyle(el);
      if (s.display === 'inline' && el.parentElement && [...el.parentElement.childNodes].some(n => n !== el && n.nodeType === 3 && n.textContent.trim())) continue;
      if (Math.min(r.width, r.height) < 47.5) out.small.push(`${name(el)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
  }
  return out;
}"""


def audit(page):
    """The page's measures (see the module doc)."""
    return page.evaluate(AUDIT)
