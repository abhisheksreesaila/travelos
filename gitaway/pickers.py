"""The GitAway pickers (F-051): one stylesheet and one script that dress the page's real date, time and select fields.

A form keeps its native `<input type="date|time">` and `<select>`: it works without JavaScript and the server still validates.
pickers.js hides the native control (clipped, not removed, so it still submits) and puts a themed one in front. Every select, date and
time field on a page that loads `HEAD` is dressed; a field can opt in to a different look with data attributes:

    select data-ga="chips"         a rounded chip grid (kids' ages)
    select data-ga="stepper"       a - n + stepper, with data-ga-label and data-ga-hint (adults, kids)
    date   data-ga-range="trip"    two date inputs with the same name become one range; the one with data-ga-end is "Come home"
    any    data-ga-label="..."     the name shown in the picker and read out by screen readers
    date   min="YYYY-MM-DD"        earlier days are disabled (the server's today, so the visitor's clock cannot disagree)
"""
from fasthtml.common import Link, Script

HEAD = (Link(rel="stylesheet", href="/assets/css/pickers.css"), Script(src="/assets/js/pickers.js", defer=True))
