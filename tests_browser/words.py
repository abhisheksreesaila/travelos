"""Shared by the contrast sweeps (F-260, kept by F-296 when the moods went): the words on a page and a pixel's luminance. The method: hide the words, photograph, compare each word with the median pixel where it sits."""

WORDS_JS = """() => [...document.querySelectorAll('.v2-top *, #main *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return {t: e.textContent.trim().slice(0, 30), x: r.left, y: r.top, w: r.width, h: r.height, c: s.color, shown: r.width > 2 && r.height > 2 && s.visibility === 'visible' && +s.opacity > 0 && r.top >= 0 && r.bottom <= innerHeight,
  closed: !!((d) => d && !d.open && !e.closest('summary'))(e.closest('details'))};      // F-281: the words of a closed popover are laid out but never painted (the Early preview note)
}).filter(w => w.shown && !w.closed)"""


def lum(c):
    v = [x / 255 for x in c[:3]]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
