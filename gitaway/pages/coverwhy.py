"""F-299: "Why another travel site?", the cover's six cards (docs/design/cover-why/flip.html, round 2; Stage look). F-301 made it static: only GitAway's faces, no flip, no script.

Each card keeps the old way as one struck line people can read ("Elsewhere: $189 a night*": a thin, light strike in a softened signal colour, the words at readable contrast).

Every claim is true today: flights say Soon while `liteapi.flights_live()` is false and the wallet pass says Soon until `walletpass` has an Apple or Google credential; the prices, hotels and counts are samples and say so (NOTE, D-270, D-383).
"""
from fasthtml.common import Div, H2, NotStr, P, Section, Span

from gitaway import liteapi, walletpass

NOTE = "The prices, hotels, reviews and counts on these cards are samples, to show how it works."


def _i(path):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'


ICONS = {
    "catch": _i('<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v4M12 17.5v.01"/>'),
    "reviews": _i('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'),
    "grid": _i('<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>'),
    "book": _i('<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 10h18"/>'),
    "plan": _i('<rect x="3" y="4" width="18" height="17" rx="2.5"/><path d="M3 9h18M8 2v4M16 2v4"/>'),
    "today": _i('<rect x="6" y="2" width="12" height="20" rx="3"/>'),
}
SEARCH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>'


def _dots():
    """The last 100 reviews as dots: mostly good, a few mixed (amber), six that mention parking (orange squares)."""
    mixed, parking = {3, 12, 19, 28, 47, 61, 77, 90}, {8, 35, 52, 66, 83, 95}
    return "".join(f'<i class="{"wy-p" if n in parking else "wy-m" if n in mixed else ""}"></i>' for n in range(100))


def _sample():
    return '<span class="wy-smp">Sample</span>'


def _wallet_words():
    """Which wallet works, from walletpass: both "In Apple and Google Wallet."; one "<that> Wallet today, <the other> Wallet soon." (the Soon tag on the other); neither "Wallet pass Soon"."""
    apple, google = walletpass.apple_configured(), walletpass.google_configured()
    if apple and google:
        return "In Apple and Google Wallet."
    if google:
        return f"Google Wallet today, Apple Wallet {_soon()}"
    if apple:
        return f"Apple Wallet today, Google Wallet {_soon()}"
    return f"Wallet pass {_soon()}"


def _soon():
    return '<span class="wy-soon">Soon</span>'


def _book_words():
    """"Book here": stays today; flights are said to be Soon while liteapi.flights_live() is false (D-980)."""
    return "Paid through Nuitée, the travel company behind it. " + ("Stays and flights." if liteapi.flights_live() else f"Stays today, flights {_soon()}")


def cards():
    """(key, tile colour, the old way (struck), GitAway's label, headline and body)."""
    return (
        ("catch", "var(--sig)", "$189 a night*", "The catch, up front", "We show what the others hide.",
         "<p>Fees paid at the hotel, parking, refund rules, your landing against the check-in time. Flagged before you pick, from the hotel's own data.</p>"
         '<div class="wy-vis"><div class="wy-price"><b>$189</b><span>a night, and here\'s the rest</span>' + _sample() + '</div>'
         '<div class="wy-chips"><span>$45 resort fee</span><span>Parking $38 a night</span><span>Lands 7 h before check-in</span><span class="wy-ok">Free cancel to Dec 10</span></div></div>'),
        ("reviews", "var(--pl-la)", "★ 8.7 · 4,182 reviews", "Reviews, read for you", "The last 100, and what they really say.",
         "<p>A trend you see at a glance, an AI reading of what guests love and warn about, and a box to ask the reviews anything.</p>"
         f'<div class="wy-vis"><div class="wy-dots" aria-hidden="true">{_dots()}</div>'
         f'<div class="wy-ask">{SEARCH}parking<em>6 of 100 mention it</em></div>{_sample()}</div>'),
        ("grid", "var(--pl-sd)", "Two tabs and a spreadsheet", "One grid", "Flights and stay, one number.",
         '<p>Places down, days across. Each square is the whole trip, and the best one lights up.</p>'
         '<div class="wy-vis"><div class="wy-mini" aria-hidden="true"><span></span><span>Fri</span><span>Sat</span><span>Sun</span><span>Mon</span>'
         '<span>Tahoe</span><span class="wy-sq">$1,412</span><span class="wy-sq wy-best">$1,276</span><span class="wy-sq">$1,350</span><span class="wy-sq">$1,498</span>'
         '<span>Truckee</span><span class="wy-sq">$1,388</span><span class="wy-sq">$1,301</span><span class="wy-sq">$1,342</span><span class="wy-sq">$1,455</span></div>' + _sample() + '</div>'),
        ("book", "var(--pc-brand);--tile-on:var(--pc-on-brand)", "Off to a site you've never heard of", "Book here", "One place. One tap.",
         f"<p>{_book_words()}</p>" '<div class="wy-vis"><div class="wy-pay"><span>Book this trip</span><span>$1,276</span></div>' + _sample() + '</div>'),
        ("plan", "var(--pl-lt)", "The group chat", "Plan together", "One calendar, bookings already in.",
         "<p>Your people add the zoo and the tacos. What you booked is already on the calendar, locked in.</p>"
         '<div class="wy-vis"><div class="wy-cal" aria-hidden="true"><div>Fri<i style="--c:var(--pl-sd)"></i><i style="--c:var(--pc-brand)"></i></div><div>Sat<i style="--c:var(--pl-lt)"></i></div>'
         '<div>Sun<i style="--c:var(--pl-sun)"></i><i style="--c:var(--pl-lt)"></i></div><div>Mon<i style="--c:var(--pl-la)"></i></div><div>Tue<i style="--c:var(--pl-sd)"></i></div></div>'
         '<div class="wy-faces" aria-hidden="true"><span style="--c:var(--pl-sd)">A</span><span style="--c:var(--pl-pink)">M</span><span style="--c:var(--pl-lt)">L</span></div></div>'),
        ("today", "var(--pl-sun)", "Searching the inbox at the gate", "Today", "What's next, in one place.",
         f"<p>When to leave, your bookings and a ride to the door. {_wallet_words()}</p>"
         '<div class="wy-vis"><div class="wy-today" aria-hidden="true"><span class="wy-lead">Leave by <span>7:40</span></span><div><span>Flight · SFO 9:05</span><span>Your booking</span></div><div><span>Check-in 4 pm</span><span>Get a ride →</span></div></div>' + _sample() + '</div>'),
    )


def _card(c):
    key, tile, old, glab, ghead, gbody = c
    return Div(
        NotStr(f'<span class="wy-lab"><b aria-hidden="true">{ICONS[key]}</b>{glab}</span>'
               f'<span class="wy-was">Elsewhere: <s>{old}</s></span><h3>{ghead}</h3>{gbody}'),
        cls="wy-card", data_card=key, style=f"--pc:{tile}")


def section():
    return Section(
        Div(Span(NotStr("<i></i>"), "Fair question", cls="wy-kick"), H2(NotStr("Why another<br><em>travel site?</em>"), id="why-h"),
            P("Because you know what the others feel like. Here's what changes.", cls="wy-lede"), cls="wy-top"),
        Div(*[_card(c) for c in cards()], cls="wy-grid"),
        P(NOTE, cls="wy-note"),
        id="why", cls="wy", aria_labelledby="why-h")
