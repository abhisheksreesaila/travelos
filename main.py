"""TravelOS — a local-first travel discovery and planning demo.

This intentionally has no live booking, weather, social, map, or identity integrations.
It uses FastHTML for routes and fh-saas' SQLite host/tenant boundary for demo state.
"""

from __future__ import annotations

import html
import os
from pathlib import Path
from urllib.parse import quote

from fasthtml.common import FastHTML, serve
from fh_saas.utils_auth import SessionConfig, create_session_middleware
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse

from data import DEMO_TENANT_ID, DEMO_USER_ID, bootstrap_store, discovery_trips, fork_plan, latest_workspace_trip, public_trip, save_creator_submission

APP_DIR = Path(__file__).parent
ASSETS_DIR = APP_DIR / "assets"
APP_NAME = "TravelOS"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def signed_in(request) -> bool:
    return bool(getattr(request, "session", {}).get("user_id"))


def badge(text: str, tone: str = "sun") -> str:
    return f'<span class="badge badge-{tone}">{esc(text)}</span>'


def icon(name: str, size: int = 18) -> str:
    paths = {
        "plane": '<path d="M3 14.5 21 12 3 9.5l5-2.5 1.5-4L12 8l6.5-1.5L21 8l-5 3 5 3-2.5 1.5L12 14l-2.5 5L8 15Z"/>',
        "search": '<circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/>',
        "arrow": '<path d="M5 12h13M13 6l6 6-6 6"/>',
        "heart": '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.9-8.6a5.5 5.5 0 0 0-.1-7.8Z"/>',
        "pin": '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
        "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
        "spark": '<path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/>',
        "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
        "chevron": '<path d="m9 18 6-6-6-6"/>',
        "check": '<path d="m5 12 4 4L19 6"/>',
        "close": '<path d="M6 6l12 12M18 6 6 18"/>',
        "plus": '<path d="M12 5v14M5 12h14"/>',
        "share": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 10.6 6.8-4.2M8.6 13.4l6.8 4.2"/>',
        "cloud": '<path d="M17.5 19H7a5 5 0 1 1 .8-9.9A6 6 0 0 1 19.5 11 4 4 0 0 1 17.5 19Z"/>',
        "receipt": '<path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3Z"/><path d="M8 8h8M8 12h8"/>',
        "map": '<path d="m9 18-6 3V6l6-3 6 3 6-3v15l-6 3-6-3Z"/><path d="M9 3v15M15 6v15"/>',
        "terminal": '<path d="m5 7 4 4-4 4M12 17h7"/>',
        "bell": '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    }
    return f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'


def logo(dark: bool = False) -> str:
    flavor = " logo-light" if dark else ""
    return f'<a class="logo{flavor}" href="/"><span class="logo-mark">{icon("plane", 19)}</span><span>Travel<span>OS</span></span></a>'


def document(title: str, body: str, page_class: str = "") -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="TravelOS is a vivid local travel discovery and trip-planning demo.">
  <title>{esc(title)} · {APP_NAME}</title>
  <link rel="stylesheet" href="/assets/theme.css">
</head>
<body class="{page_class}">
  <a class="skip-link" href="#main">Skip to content</a>
  {body}
  <div class="toast-region" aria-live="polite" aria-atomic="true"></div>
  <script src="/assets/app.js" defer></script>
</body></html>"""
    )


def public_header(request, active: str = "") -> str:
    signed = signed_in(request)
    workspace_link = "/workspace" if signed else "/signin?next=/workspace"
    account = (
        '<a class="avatar-button" href="/workspace" aria-label="Open Ari’s workspace">AR</a>'
        if signed
        else '<a class="header-signin" href="/signin?next=/workspace">Sign in</a>'
    )
    return f"""<header class="site-header">
 <div class="site-header-inner">
  {logo()}
  <nav class="site-nav" aria-label="Primary">
   <a class="{'is-active' if active == 'discover' else ''}" href="/discover">Discover</a>
   <a class="{'is-active' if active == 'creators' else ''}" href="/creators">For creators</a>
   <a class="{'is-active' if active == 'plans' else ''}" href="/plans/granada-after-dark">Trip plans</a>
  </nav>
  <div class="header-actions"><a class="text-button" href="{workspace_link}">My trips</a>{account}<button class="mobile-menu" data-menu-toggle aria-label="Open navigation">{icon('menu')}</button></div>
 </div>
</header>"""


def search_bar(compact: bool = False, q: str = "") -> str:
    compact_class = " search-compact" if compact else ""
    return f"""<form class="travel-search{compact_class}" action="/discover" method="get">
  <label><span>{icon('pin', 17)}</span><span class="input-label">Where to?</span><input name="q" value="{esc(q)}" placeholder="City, coast, or feeling" autocomplete="off"></label>
  <label class="search-date"><span>{icon('calendar', 17)}</span><span class="input-label">When</span><input name="dates" value="Anytime" aria-label="Travel dates"></label>
  <label class="search-travelers"><span>{icon('users', 17)}</span><span class="input-label">Travelers</span><input name="travelers" value="2 travelers" aria-label="Travelers"></label>
  <button class="search-submit" type="submit"><span class="search-label">Search plans</span>{icon('search')}</button>
</form>"""


def scene(trip: dict, mini: bool = False) -> str:
    title = f"Illustrated {trip['destination']} travel scene"
    return f'<div class="destination-scene scene-{esc(trip["hero"])}{" scene-mini" if mini else ""}" role="img" aria-label="{esc(title)}"><span class="scene-sun"></span><span class="scene-orb orb-one"></span><span class="scene-orb orb-two"></span><span class="scene-hill hill-one"></span><span class="scene-hill hill-two"></span><span class="scene-building building-one"></span><span class="scene-building building-two"></span></div>'


def trip_card(trip: dict) -> str:
    tags = "".join(badge(tag, "paper") for tag in trip["tags"][:2])
    return f"""<article class="trip-card">
  <a class="trip-card-image" href="/plans/{esc(trip['slug'])}" aria-label="Open {esc(trip['title'])}">{scene(trip)}<span class="save-button" aria-hidden="true">{icon('heart', 17)}</span><span class="image-price">from {esc(trip['price'])}</span></a>
  <div class="trip-card-body">
    <div class="card-kicker"><span>{esc(trip['days'])} days · {esc(trip['region'])}</span><span>{icon('heart', 14)} {esc(trip['saves'])}</span></div>
    <h3><a href="/plans/{esc(trip['slug'])}">{esc(trip['title'])}</a></h3>
    <p>{esc(trip['summary'])}</p>
    <div class="card-tags">{tags}</div>
    <div class="creator-line"><span class="creator-avatar">{esc(trip['avatar'])}</span><span><strong>{esc(trip['creator'])}</strong><small>{esc(trip['creator_role'])}</small></span><a href="/plans/{esc(trip['slug'])}" class="round-arrow" aria-label="View {esc(trip['title'])}">{icon('arrow', 16)}</a></div>
  </div>
</article>"""


def landing(request) -> HTMLResponse:
    highlights = "".join(f'<span>{icon("check", 15)} {word}</span>' for word in ("Creator-crafted", "Forkable plans", "No booking pressure"))
    cards = "".join(trip_card(trip) for trip in discovery_trips()[:3])
    body = f"""{public_header(request)}
<main id="main">
 <section class="hero-shell">
  <div class="hero-content">
   <div class="hero-copy">
    <span class="eyebrow eyebrow-light">THE NEW WAY TO ROAM <i></i> LOCAL DEMO</span>
    <h1>Less searching.<br><em>More</em> going.</h1>
    <p>TravelOS brings trusted creator notes, bookable-shaped options, weather, and a living itinerary into one joyful trip canvas.</p>
    <div class="hero-trust">{highlights}</div>
   </div>
   <div class="hero-art" aria-hidden="true"><div class="floating-stamp stamp-top">READY<br>TO ROAM</div><div class="hero-globe"><span class="globe-grid"></span><span class="globe-dot dot-a"></span><span class="globe-dot dot-b"></span><span class="globe-route"></span><span class="globe-plane">{icon('plane', 30)}</span></div><div class="floating-card"><span class="mini-pin">{icon('pin', 14)}</span><strong>Granada</strong><small>4 days · sunlit</small></div><div class="sun-flare"></div></div>
  </div>
  <div class="hero-search-wrap">{search_bar()}</div>
 </section>
 <section class="value-strip"><div><strong>48 hand-built plans</strong><span>made for real trip energy</span></div><div><strong>12,000+ local saves</strong><span>from travelers like you</span></div><div><strong>One shared canvas</strong><span>from sparks to suitcases</span></div><a href="/creators">Share your guide {icon('arrow', 15)}</a></section>
 <section class="content-section featured-section">
  <div class="section-heading"><div><span class="eyebrow">CURATED FOR RIGHT NOW</span><h2>Plans with a pulse.</h2></div><a class="arrow-link" href="/discover">Explore all plans {icon('arrow')}</a></div>
  <div class="trip-grid">{cards}</div>
 </section>
 <section class="split-promo"><div class="promo-visual"><div class="postcard postcard-one"><span>postcard from</span><b>Oaxaca</b><i>☀</i></div><div class="postcard postcard-two"><span>weather-aware<br>by design</span><b>24°</b></div><div class="promo-route"><span></span><i></i><b></b></div></div><div class="promo-copy"><span class="eyebrow">BUILT FOR THE WHOLE TRIP</span><h2>From a saved reel to a plan you can actually use.</h2><p>Fork any public guide, then command your own trip across itinerary, costs, weather, places, and your people—without tab gymnastics.</p><a class="primary-button" href="/plans/granada-after-dark">Try a public plan {icon('arrow')}</a></div></section>
 <section class="creator-band"><div><span class="eyebrow eyebrow-light">FOR PEOPLE WHO SHOW THE WAY</span><h2>Your local knowledge deserves a longer runway.</h2><p>Publish a plan, point travelers to your channels, and turn one great trip into useful momentum.</p></div><a class="cream-button" href="/creators">Meet the creator studio {icon('arrow')}</a></section>
</main>{public_footer()}"""
    return document("Discover travel that fits", body, "marketing-page")


def public_footer() -> str:
    return f"""<footer class="site-footer"><div>{logo(dark=True)}<p>Designed for curious humans, demoed locally.</p></div><div class="footer-links"><a href="/discover">Discover</a><a href="/creators">Creators</a><a href="/signin?next=/workspace">My workspace</a></div><small>TravelOS local demo · Fixture prices, availability, weather, and social reach are illustrative.</small></footer>"""


def discover(request, q: str = "", region: str = "", **_ignored) -> HTMLResponse:
    trips = discovery_trips(q, region)
    results = "".join(trip_card(trip) for trip in trips)
    zero = f"<div class=\"empty-state\">{icon('search', 30)}<h2>No plans match that just yet.</h2><p>Try a place, a mood, or one of the colorful regions below.</p><a class=\"primary-button\" href=\"/discover\">Show all plans</a></div>"
    filters = [("all", "Everywhere"), ("Europe", "Europe"), ("Asia", "Asia"), ("Americas", "Americas"), ("Africa", "Africa")]
    filter_links = "".join(f'<a href="/discover?region={quote(key)}" class="{"is-active" if region.lower() == key.lower() or (not region and key == "all") else ""}">{label}</a>' for key, label in filters)
    intro = f"Results for <strong>“{esc(q)}”</strong>" if q else "Creator-built routes and useful trip ideas"
    body = f"""{public_header(request, 'discover')}<main id="main" class="discovery-page"><section class="discover-top"><div><span class="eyebrow">TRAVEL, BETTER CONNECTED</span><h1>Find the plan that starts your next story.</h1><p>{intro}</p></div>{search_bar(True, q)}</section><nav class="filter-row" aria-label="Filter destinations">{filter_links}</nav><section class="discover-results"><div class="results-meta"><span>{len(trips)} polished fixture plans</span><span>{badge('Local demo data', 'mint')}</span></div><div class="trip-grid">{results or zero}</div></section></main>{public_footer()}"""
    return document("Discover plans", body, "discovery-shell")


def plan_day(day: int, title: str, time: str, copy: str, status: str = "") -> str:
    state = f'<span class="day-status">{esc(status)}</span>' if status else ""
    return f"""<article class="itinerary-row"><span class="timeline-node">{day}</span><div class="itinerary-time">{esc(time)}</div><div><h3>{esc(title)} {state}</h3><p>{esc(copy)}</p><div class="row-actions"><button type="button" data-toast="Saved to your trip notes">{icon('heart', 14)} Save note</button><button type="button" data-toast="Opening local map context">{icon('map', 14)} See nearby</button></div></div></article>"""


def plan_detail(request, slug: str, forked: str = "") -> HTMLResponse:
    trip = public_trip(slug)
    if not trip:
        return document("Plan not found", f"{public_header(request)}<main id=\"main\" class=\"simple-page\"><h1>This route took a different turn.</h1><a class=\"primary-button\" href=\"/discover\">Back to discovery</a></main>{public_footer()}")
    is_signed = signed_in(request)
    fork_action = (
        f'<form action="/plans/{esc(slug)}/fork" method="post"><button class="primary-button large-button" type="submit">{icon("spark")} Fork into my workspace</button></form>'
        if is_signed
        else f'<a class="primary-button large-button" href="/signin?next=/plans/{quote(slug)}">{icon("spark")} Sign in to fork this plan</a>'
    )
    fork_notice = '<div class="fork-notice">' + icon("check") + ' You’re signed in. Fork this plan to make it yours.</div>' if forked == "ready" and is_signed else ""
    itinerary = "".join(
        [
            plan_day(1, "Check in, then let the city lead", "15:00", "Settle near Plaza Nueva. The first evening is intentionally unbooked for a golden-hour wander."),
            plan_day(2, "Alhambra before the crowds", "08:15", "A timed-entry placeholder and a coffee stop leave enough space for the gardens to feel unhurried.", "Creator tip"),
            plan_day(3, "Tapas route through Realejo", "12:30", "Three tiny bars, one viewpoint, and a late flamenco room—each saved as a flexible stop, not a mandate."),
            plan_day(4, "Sacromonte send-off", "10:00", "Take the high path, browse the ceramics, and keep your transfer buffer honest."),
        ]
    )
    body = f"""{public_header(request, 'plans')}<main id="main" class="plan-page">
 <section class="plan-hero"><div class="plan-hero-scene">{scene(trip)}<div class="plan-hero-overlay"></div><a href="/discover" class="back-link">← Discover plans</a><div class="plan-hero-copy"><span>{badge('PUBLIC PLAN', 'sun')} {badge('4 days', 'glass')}</span><h1>{esc(trip['title'])}</h1><p>{icon('pin', 17)} {esc(trip['destination'])} <i></i> {esc(trip['dates'])}</p></div></div><aside class="fork-card"><div class="fork-card-top"><span class="creator-avatar creator-avatar-lg">{esc(trip['avatar'])}</span><div><span class="micro-label">CREATED BY</span><strong>{esc(trip['creator'])}</strong><small>{esc(trip['creator_role'])}</small></div></div><p>Everything Lina wishes she knew before her first long weekend in Granada.</p>{fork_notice}{fork_action}<span class="fork-note">No live reservations are made in this demo.</span><div class="fork-stats"><span><b>{esc(trip['saves'])}</b> saves</span><span><b>94%</b> would go again</span></div></aside></section>
 <section class="plan-summary"><div><span class="eyebrow">THE VIBE</span><h2>Sun-softened days, late little dinners, and no overstuffed schedule.</h2></div><p>{esc(trip['summary'])} This public route is a useful starting point—not a sales funnel disguised as a plan.</p><div class="summary-tags">{''.join(badge(tag, 'mint') for tag in trip['tags'])}</div></section>
 <section class="plan-content-grid"><div class="plan-itinerary"><div class="section-heading"><div><span class="eyebrow">DAY BY DAY</span><h2>Keep the good parts flexible.</h2></div><button class="outline-button" type="button" data-toast="Download is a follow-up integration">{icon('share', 16)} Share plan</button></div>{itinerary}</div><aside class="plan-side"><div class="side-module weather-module"><div class="module-heading"><span>{icon('cloud', 18)} Local forecast</span><small>Fixture data</small></div><strong>22° <small>clear & warm</small></strong><div class="weather-days"><span><b>THU</b>23°</span><span><b>FRI</b>22°</span><span><b>SAT</b>21°</span><span><b>SUN</b>20°</span></div><p>Pack a light layer for the hillside after sunset.</p></div><div class="side-module route-module"><div class="module-heading"><span>{icon('map', 18)} Route at a glance</span><button type="button" data-toast="Map providers are intentionally not connected">Expand</button></div><div class="mini-map"><i class="map-path"></i><b class="map-stop map-stop-a">1</b><b class="map-stop map-stop-b">2</b><b class="map-stop map-stop-c">3</b><span>Albaicín</span><span>Centro</span><span>Sacromonte</span></div><p>Mostly walkable · <strong>4.6 km/day</strong></p></div><div class="side-module booking-module"><span class="eyebrow">BOOKING BOARD</span><h3>Compare when you’re ready.</h3><p>Flights, stays, and activities are shown as local fixture cards in your workspace—not live inventory.</p><a href="/signin?next=/workspace" class="arrow-link">See the board {icon('arrow')}</a></div></aside></section>
 <section class="plan-creator-cta"><div class="creator-cta-portrait">{icon('spark', 43)}<span>local<br>eyes</span></div><div><span class="eyebrow">MAKE YOUR KNOW-HOW USEFUL</span><h2>Have a route travelers should know?</h2><p>Send it to the TravelOS creator studio and keep your YouTube and Instagram presence front and center.</p></div><a class="outline-button dark-outline" href="/creators">For creators {icon('arrow')}</a></section>
</main>{public_footer()}"""
    return document(trip["title"], body, "plan-shell")


def signin(request, next: str = "/workspace") -> HTMLResponse:
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/workspace"
    body = f"""<main id="main" class="signin-page"><a class="signin-logo" href="/">{logo()}</a><section class="signin-card"><div class="signin-visual"><span class="eyebrow eyebrow-light">YOUR TRIP, IN MOTION</span><div class="signin-globe">{icon('plane', 34)}</div><h1>Pick up where curiosity left off.</h1><p>Fork a public plan into your personal workspace, then make every decision in context.</p><div class="signin-mini-list"><span>{icon('check', 15)} Itinerary + bookings together</span><span>{icon('check', 15)} Local weather fixtures, at a glance</span><span>{icon('check', 15)} A shared trip signal, not more tabs</span></div></div><div class="signin-form"><a class="small-back" href="/">← Back to TravelOS</a><span class="eyebrow">LOCAL DEMO ACCESS</span><h2>Welcome, traveler.</h2><p>This polished demo uses a local fixture identity. Production account identity is a planned integration boundary.</p><form action="/signin" method="post"><input type="hidden" name="next" value="{esc(safe_next)}"><button class="primary-button full-button" type="submit"><span class="button-orb">AR</span> Continue as Ari Rivera {icon('arrow')}</button></form><div class="signin-divider"><span>What this does</span></div><p class="fine-print">Creates a signed local session for <strong>traveler@travelos.local</strong> and opens the Weekend Club tenant workspace. No data leaves this machine.</p></div></section></main>"""
    return document("Sign in", body, "signin-shell")


def creators(request, submitted: str = "") -> HTMLResponse:
    confirmation = '<div class="submission-confirmation">' + icon("check") + '<div><strong>Pitch received in the local creator queue.</strong><p>In a production build, this would create a review workflow and channel-aware onboarding.</p></div></div>' if submitted else ""
    body = f"""{public_header(request, 'creators')}<main id="main" class="creator-page"><section class="creator-hero"><div><span class="eyebrow eyebrow-light">TRAVELOS CREATOR STUDIO</span><h1>Turn your <em>point of view</em> into a plan people use.</h1><p>Make your best routes discoverable, useful, and unmistakably yours—without giving up the audience you’ve built.</p><a class="cream-button" href="#submit">Submit a travel story {icon('arrow')}</a></div><div class="creator-hero-visual"><div class="creator-phone"><div class="phone-bar"><i></i><i></i><i></i></div><div class="phone-scene">{scene(public_trip('oaxaca-color-weekend'), True)}<span class="phone-play">▶</span></div><div class="phone-caption"><b>48 hours in Oaxaca</b><small>the market-first route</small></div></div><span class="reach-bubble bubble-youtube"><b>+42%</b><small>YouTube discovery</small></span><span class="reach-bubble bubble-instagram"><b>+18%</b><small>Instagram saves</small></span><div class="creator-sparkle">✦</div></div></section><section class="creator-benefits"><article><span class="benefit-icon">01</span><h2>Keep your voice.</h2><p>Your recommendations, pacing, and channel links travel with every plan—not just a thumbnail.</p></article><article><span class="benefit-icon">02</span><h2>Earn useful reach.</h2><p>Travelers who fork your route see your YouTube and Instagram calls to action at the moment they matter.</p></article><article><span class="benefit-icon">03</span><h2>Help them go.</h2><p>Give followers an itinerary, practical local context, and an easy way to make the trip their own.</p></article></section><section class="creator-proof"><div class="proof-avatar-grid"><span>LM</span><span>NB</span><span>HK</span><span>MS</span></div><blockquote>“It feels like sharing the part of my travel videos people always ask me to make: the actual plan.”<cite>— Lina Morales, city filmmaker</cite></blockquote><div class="fixture-disclaimer">Illustrative fixture metrics only. TravelOS does not access or promise social-platform reach in this demo.</div></section><section id="submit" class="submission-section"><div class="submission-intro"><span class="eyebrow">PITCH YOUR ROUTE</span><h2>Tell us where your story takes travelers.</h2><p>Submit the bones of a guide. It lands in the local demo tenant queue; live publishing and creator-network connections are intentionally follow-up work.</p><div class="submission-callout">{icon('spark', 18)} <span><strong>What helps:</strong> a strong local angle, your favorite pacing, and the channel you want travelers to find.</span></div></div><div>{confirmation}<form class="creator-form" action="/creators/submit" method="post"><label>Your name<input required name="creator_name" placeholder="e.g. Samira Chen"></label><label>Email<input required type="email" name="email" placeholder="you@example.com"></label><div class="form-two"><label>Destination<input required name="destination" placeholder="e.g. Penang, Malaysia"></label><label>Story title<input required name="story_title" placeholder="e.g. Street food at midnight"></label></div><div class="form-two"><label>YouTube (optional)<input name="youtube" placeholder="youtube.com/@yourchannel"></label><label>Instagram (optional)<input name="instagram" placeholder="@yourhandle"></label></div><label>What makes this route special?<textarea required name="note" rows="4" placeholder="Give travelers the useful detail they cannot get from a generic list…"></textarea></label><button class="primary-button" type="submit">Send my local pitch {icon('arrow')}</button><p class="form-note">By sending, you are adding a fixture record to this machine only.</p></form></div></section></main>{public_footer()}"""
    return document("Creator studio", body, "creator-shell")


def workspace_header(trip) -> str:
    return f"""<header class="command-header"><div class="command-brand">{logo(dark=True)}<span class="workspace-divider"></span><button class="trip-switcher" type="button" data-toast="Trip switcher is a local demo control"><span class="trip-dot"></span>{esc(trip.title if trip else 'Weekend Club')} {icon('chevron', 15)}</button></div><div class="command-status"><span class="sync-status"><i></i> All changes saved locally</span><button class="icon-control" type="button" data-command-palette aria-label="Open command palette">⌘ K</button><button class="avatar-stack" type="button" data-toast="Ari and two fixture collaborators are viewing this plan"><i>AR</i><i>LM</i><i>+2</i></button><a class="exit-workspace" href="/">Exit</a></div></header>"""


def command_pane(title: str, icon_name: str, body: str, key: str = "", extra: str = "") -> str:
    shortcut = f'<span class="pane-key">{esc(key)}</span>' if key else ""
    return f'<section class="command-pane {extra}"><header class="pane-header"><h2>{icon(icon_name, 16)} {esc(title)}</h2><div>{shortcut}<button type="button" class="pane-more" data-toast="Pane controls are ready for a future live integration">•••</button></div></header>{body}</section>'


def workspace(request) -> HTMLResponse:
    if not signed_in(request):
        return RedirectResponse("/signin?next=/workspace", status_code=303)
    trip = latest_workspace_trip() or fork_plan("granada-after-dark")
    day_items = "".join(
        f'<button class="day-nav {"is-active" if day == 1 else ""}" data-day="{day}" type="button"><span>D{day}</span><b>{title}</b><small>{date}</small></button>'
        for day, title, date in [(1, "Arrive easy", "APR 12"), (2, "Alhambra early", "APR 13"), (3, "Tapas till late", "APR 14"), (4, "High path home", "APR 15")]
    )
    itinerary = command_pane("Itinerary", "calendar", f"""<div class="command-tabs"><button class="is-active" data-pane-tab="timeline" type="button">Timeline</button><button data-pane-tab="list" type="button">List</button><button data-pane-tab="notes" type="button">Notes</button></div><div class="workspace-timeline"><article><time>08:15</time><div><span class="timeline-kind">TICKETED</span><h3>Alhambra timed entry</h3><p>Generalife gate · walk from the hotel</p><button type="button" class="tiny-action" data-toast="Alhambra marked as ready">{icon('check', 13)} Ready</button></div></article><article><time>12:30</time><div><span class="timeline-kind kind-food">FOOD</span><h3>Realejo tapas loop</h3><p>3 stops · 1.2 km · local favorite notes</p><button type="button" class="tiny-action" data-toast="Added a tapas note">{icon('plus', 13)} Add note</button></div></article><article><time>20:00</time><div><span class="timeline-kind kind-play">EVENING</span><h3>Flamenco, if the mood is right</h3><p>Flexible hold · Sacromonte</p><button type="button" class="tiny-action" data-toast="This flexible hold is on your radar">{icon('bell', 13)} Watch</button></div></article></div><button class="add-row" type="button" data-toast="New itinerary item composer is a follow-up interaction">{icon('plus', 15)} Add an unhurried moment</button>""", "1", "pane-itinerary")
    booking = command_pane("Booking board", "plane", """<div class="booking-tabs"><button class="is-active" type="button" data-booking-tab="stays">Stay</button><button type="button" data-booking-tab="flights">Flight</button><button type="button" data-booking-tab="activities">Do</button></div><article class="booking-card"><div class="booking-thumb hotel-thumb"><span>PLAZA NUEVA</span></div><div><span class="booking-label">TOP FIXTURE MATCH</span><h3>Casa del Laurel</h3><p>4 nights · Old town · 9.1 guest signal</p><div><strong>$512</strong> <small>total / fixture</small><button type="button" data-toast="Saved Casa del Laurel to your local shortlist">Save</button></div></div></article><article class="booking-card booking-muted"><div class="booking-thumb flight-thumb">MAD<br>↔ GRX</div><div><span class="booking-label">FLIGHT SHAPE</span><h3>Morning connection</h3><p>3h 40m · 1 stop · carry-on friendly</p><div><strong>$238</strong> <small>round trip / fixture</small><button type="button" data-toast="Price alerts need a future provider connection">Alert</button></div></div></article><p class="provider-note">No booking providers connected. Cards are local fixtures for planning context.</p>""", "2", "pane-booking")
    map_pane = command_pane("Place context", "map", """<div class="command-map"><span class="map-label label-a">ALBAICÍN</span><span class="map-label label-b">CENTRO</span><span class="map-label label-c">SACROMONTE</span><i class="route-line"></i><button class="route-pin pin-one" type="button" data-toast="Alhambra: 12 min walk from your stay">1</button><button class="route-pin pin-two" type="button" data-toast="Lunch area: reliable vegetarian options">2</button><button class="route-pin pin-three" type="button" data-toast="Tonight: bring a light layer after 21:00">3</button><div class="map-compass">N</div><div class="map-legend"><span><i></i> Today’s route</span><span><i></i> Local note</span></div></div><div class="map-context-copy"><strong>Day 2 stays walkable.</strong><span>3.6 km total · 22 min uphill after lunch</span><button type="button" data-toast="Map routing is intentionally local and illustrative">Open routing cues {icon('arrow', 14)}</button></div>""", "3", "pane-map")
    weather = command_pane("Weather window", "cloud", """<div class="weather-now"><div><span>THU · APR 13</span><strong>22°</strong><p>Clear, soft breeze</p></div><div class="weather-sun">☀</div></div><div class="hourly-weather"><span><b>09</b>19°</span><span><b>12</b>22°</span><span><b>15</b>23°</span><span><b>18</b>20°</span><span><b>21</b>16°</span></div><div class="weather-alert">{icon('spark', 14)} Perfect for your 08:15 garden slot.</div><small class="fixture-label">Local forecast fixture · no weather provider called</small>""", "4", "pane-weather")
    ledger = command_pane("Cost ledger", "receipt", """<div class="ledger-total"><span>Trip total</span><strong>$1,086</strong><small>$214 under your comfort budget</small></div><div class="budget-bar"><i></i></div><div class="ledger-list"><div><span>Stay <small>Saved</small></span><b>$512</b></div><div><span>Flight <small>Watching</small></span><b>$238</b></div><div><span>Food & moments <small>Est.</small></span><b>$336</b></div></div><button class="ledger-action" type="button" data-toast="Ledger detail is ready for your future live booking adapter">Open ledger {icon('arrow', 14)}</button>""", "5", "pane-ledger")
    alerts = """<section class="command-drawer"><button class="drawer-label" type="button" data-drawer-toggle>{icon('bell', 15)} <strong>3 trip signals</strong><span>flight price softening · collaborator online · sunny morning</span>{icon('chevron', 14)}</button><div class="drawer-collaborators"><span class="presence"><i></i> Lina is looking at the tapas loop</span><button type="button" data-toast="Invite links are a follow-up collaboration feature">{icon('users', 14)} Invite</button><button type="button" data-toast="Shared notes are ready for a future realtime adapter">{icon('share', 14)} Share view</button></div></section>"""
    body = f"""{workspace_header(trip)}<main id="main" class="command-center"><aside class="command-sidebar"><div class="sidebar-head"><span class="eyebrow">{esc(trip.destination).upper()}</span><button data-sidebar-toggle type="button" aria-label="Collapse trip days">‹</button></div><h1>{esc(trip.title)}</h1><p>{esc(trip.days)} days · Apr 12–16 · 2 travelers</p><div class="trip-progress"><span><i></i> Planning together</span><b>72%</b></div><nav class="day-nav-list" aria-label="Trip days">{day_items}</nav><div class="sidebar-bottom"><button type="button" data-toast="Packing list added to your local command center">{icon('plus', 15)} Add a list</button><a href="/logout">Sign out</a></div></aside><section class="command-workspace"><div class="command-overview"><div><span class="eyebrow">TRIP COMMAND CENTER</span><h2>Thursday’s rhythm</h2></div><div class="overview-controls"><button class="overview-view is-active" type="button" data-overview="all">All systems</button><button class="overview-view" type="button" data-overview="money">Money</button><button class="overview-view" type="button" data-overview="flow">Flow</button><button class="quick-add" type="button" data-toast="Quick-add composer is ready for a future persistence interaction">{icon('plus', 15)} Add</button></div></div><div class="command-grid">{itinerary}{booking}{map_pane}{weather}{ledger}</div>{alerts}</section></main><div class="command-palette" hidden data-command-dialog><div><button class="palette-close" data-command-close type="button">{icon('close', 18)}</button><span class="eyebrow">COMMAND PALETTE</span><h2>Move through your trip.</h2><input aria-label="Search commands" placeholder="Try “open weather”"><button type="button" data-toast="Weather pane focused">Open weather window <kbd>4</kbd></button><button type="button" data-toast="Booking board focused">Open booking board <kbd>2</kbd></button><button type="button" data-toast="Share link copied locally">Copy trip share link <kbd>⌘</kbd></button></div></div>"""
    return document("Trip command center", body, "command-shell")


def create_app():
    bootstrap_store()
    fast_app = FastHTML(title=APP_NAME, sess_cls=None)

    @fast_app.get("/assets/theme.css")
    def theme_css():
        return FileResponse(ASSETS_DIR / "theme.css", media_type="text/css")

    @fast_app.get("/assets/app.js")
    def app_js():
        return FileResponse(ASSETS_DIR / "app.js", media_type="text/javascript")

    @fast_app.get("/")
    def home(request):
        return landing(request)

    @fast_app.get("/discover")
    def discovery(request, q: str = "", region: str = "", dates: str = "", travelers: str = ""):
        return discover(request, q, region, dates=dates, travelers=travelers)

    @fast_app.get("/plans/{slug}")
    def public_plan(request, slug: str, forked: str = ""):
        return plan_detail(request, slug, forked)

    @fast_app.get("/signin")
    def sign_in_page(request, next: str = "/workspace"):
        return signin(request, next)

    @fast_app.post("/signin")
    async def sign_in(request):
        form = await request.form()
        next_url = str(form.get("next", "/workspace"))
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = "/workspace"
        request.session.update({"user_id": DEMO_USER_ID, "tenant_id": DEMO_TENANT_ID, "display_name": "Ari Rivera"})
        connector = "&" if "?" in next_url else "?"
        if next_url.startswith("/plans/"):
            next_url = f"{next_url}{connector}forked=ready"
        return RedirectResponse(next_url, status_code=303)

    @fast_app.get("/logout")
    def logout(request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    @fast_app.post("/plans/{slug}/fork")
    def fork_public_plan(request, slug: str):
        if not signed_in(request):
            return RedirectResponse(f"/signin?next=/plans/{quote(slug)}", status_code=303)
        try:
            fork_plan(slug, request.session["user_id"])
        except KeyError:
            return RedirectResponse("/discover", status_code=303)
        return RedirectResponse("/workspace", status_code=303)

    @fast_app.get("/workspace")
    def trip_workspace(request):
        return workspace(request)

    @fast_app.get("/creators")
    def creator_studio(request, submitted: str = ""):
        return creators(request, submitted)

    @fast_app.post("/creators/submit")
    async def creator_submit(request):
        form = await request.form()
        required = ("creator_name", "email", "destination", "story_title", "note")
        payload = {key: str(form.get(key, "")) for key in (*required, "youtube", "instagram")}
        if not all(payload[key].strip() for key in required):
            return RedirectResponse("/creators#submit", status_code=303)
        save_creator_submission(payload)
        return RedirectResponse("/creators?submitted=1#submit", status_code=303)

    session_config = SessionConfig(secure=False, max_age=60 * 60 * 8)
    return create_session_middleware(os.getenv("SESSION_SECRET", "travelos-local-demo-change-me"), session_config)(fast_app)


app = create_app()

if __name__ == "__main__":
    serve(appname="main", app_dir=str(APP_DIR), reload_dirs=str(APP_DIR))
