/* GitAway service worker (F-044): keeps the app shell and the pages a traveler has opened for flaky connections.
   Served at /sw.js (so its scope is the whole site) with __VERSION__ and __SHELL_URLS__ filled in by the server:
   VERSION is a hash of this file and every precached file, so any change installs a new worker and drops old caches.
   Never touches a POST, another origin, or the sign-in / sign-out routes.
   Saved pages are filed per signed-in person (the page's ga-user meta); a signed-out view is never saved. */
const VERSION = "__VERSION__";
const SHELL = `ga-shell-${VERSION}`;
const ASSETS = `ga-assets-${VERSION}`;
const WHO = "ga-who"; // survives version bumps: remembers whose pages are saved
const PAGES_PREFIX = "ga-pages-";
const MAX_PAGES = 30;
const PAGE_TIMEOUT = 3500;
const SHELL_URLS = __SHELL_URLS__;
const AUTH_PATH = /^\/(login|logout|signin|signout|auth)(\/|$)/;

/* What to do with a request: "asset" (cache first), "page" (network first, cache fallback) or "skip" (leave it alone). */
function routeFor(req) {
  if (req.method !== "GET") return "skip";
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return "skip";
  if (AUTH_PATH.test(url.pathname)) return "skip";
  if (url.pathname === "/sw.js" || url.pathname === "/manifest.webmanifest") return "skip";
  if (url.pathname.startsWith("/assets/")) return "asset";
  if (req.mode === "navigate") return "page";
  return "skip";
}

const pagesName = (who) => `${PAGES_PREFIX}${VERSION}-${who}`;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n.startsWith("ga-") && n !== WHO && n !== SHELL && n !== ASSETS && !n.startsWith(PAGES_PREFIX + VERSION + "-")).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

async function getWho() {
  const hit = await (await caches.open(WHO)).match("/__who");
  return hit ? hit.text() : "";
}

async function setWho(who) {
  await (await caches.open(WHO)).put("/__who", new Response(who));
}

/* Versioned (?v=hash) assets never change, so a hit is final; the rest are refreshed in the background. */
async function assetFirst(req) {
  const cache = await caches.open(ASSETS);
  const hit = (await cache.match(req)) || (await (await caches.open(SHELL)).match(req));
  if (hit) {
    if (!new URL(req.url).searchParams.has("v")) fetch(req).then((res) => { if (res.ok) cache.put(req, res); }).catch(() => {});
    return hit;
  }
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

async function trim(cache) {
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - MAX_PAGES))) await cache.delete(k);
}

/* Reads whose pages these are from the HTML, forgets everyone else's, and saves this one under that person's key. */
async function remember(req, res) {
  if (res.status !== 200 || !(res.headers.get("content-type") || "").startsWith("text/html")) return;
  const m = /<meta name="ga-user" content="([0-9a-f]+)">/.exec(await res.clone().text());
  const who = m ? m[1] : "";
  if (who !== (await getWho())) {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.startsWith(PAGES_PREFIX) && n !== pagesName(who)).map((n) => caches.delete(n)));
    await setWho(who);
  }
  if (!who || res.redirected) return;
  const cache = await caches.open(pagesName(who));
  await cache.delete(req);
  await cache.put(req, res.clone());
  /* F-092: the installed app starts at /trip, which redirects to the day view (the browser follows that redirect, so this worker never sees it).
     The last day view opened is kept as /trip too, so an offline start opens the plan instead of the offline page. */
  const url = new URL(req.url);
  if (url.pathname === "/trip/canvas" && /^\?day=\d+(&trip=[0-9a-f]+)?$/.test(url.search)) {
    const start = new URL("/trip", url.origin).href;
    await cache.delete(start);
    await cache.put(start, res.clone());
  }
  await trim(cache);
}

async function pageNetworkFirst(req) {
  const who = await getWho();
  const saved = who ? await (await caches.open(pagesName(who))).match(req) : undefined;
  const network = fetch(req).then(async (res) => { try { await remember(req, res); } catch (e) {} return res; });
  network.catch(() => {});
  if (!saved) return network.catch(async () => (await caches.match("/offline")) || Response.error());
  const slow = new Promise((resolve) => setTimeout(() => resolve(null), PAGE_TIMEOUT));
  try { return (await Promise.race([network, slow])) || saved; } catch (e) { return saved; }
}

/* F-099: a link the finger touched is fetched at once and the copy kept in memory for FRESH_MS, for the person who was signed in then.
   The next navigation to that URL gets it (once), marked `x-ga-prefetch: 1`; otherwise the network-first logic above runs.
   Never a redirect, a non-200, a non-page, another person's page, an auth route or a POST; any POST or auth request drops every held copy. */
const FRESH_MS = 5000;
const MAX_HELD = 8;
const held = new Map();

function startPrefetch(raw) {
  const url = new URL(raw, self.location.origin);
  if (routeFor({ method: "GET", url: url.href, mode: "navigate" }) !== "page") return null;
  const key = url.href;
  const old = held.get(key);
  if (old && Date.now() - old.t < FRESH_MS) return old.done;
  for (const [k, v] of held) if (Date.now() - v.t >= FRESH_MS) held.delete(k);
  while (held.size >= MAX_HELD) held.delete(held.keys().next().value);
  const entry = { t: Date.now(), who: "", done: null };
  entry.done = (async () => {
    const who = await getWho();
    if (!who) return null;
    entry.who = who;
    const req = new Request(key, { credentials: "same-origin", headers: { Accept: "text/html" } });
    const res = await fetch(req);
    const type = res.headers.get("content-type") || "";
    if (res.status !== 200 || res.redirected || !type.startsWith("text/html")) return null;
    const body = await res.clone().arrayBuffer();
    const m = /<meta name="ga-user" content="([0-9a-f]+)">/.exec(new TextDecoder().decode(body));
    if (!m || m[1] !== who) return null;
    try { await remember(req, res.clone()); } catch (e) {}
    return { body, headers: new Headers(res.headers) };
  })().catch(() => null);
  entry.done.then(() => { entry.ready = true; });
  held.set(key, entry);
  return entry.done;
}

async function fromPrefetch(req) {
  const entry = held.get(req.url);
  if (!entry || Date.now() - entry.t >= FRESH_MS || req.cache === "reload" || req.cache === "no-cache") return null;
  held.delete(req.url);
  const TIMED_OUT = {};
  const slow = new Promise((resolve) => setTimeout(() => resolve(TIMED_OUT), PAGE_TIMEOUT));
  const got = await Promise.race([entry.done, slow]);
  if (got === TIMED_OUT) {   // a hanging connection: show the saved page now rather than start a second wait
    const who = await getWho();
    return (who && (await (await caches.open(pagesName(who))).match(req))) || null;
  }
  if (!got || entry.who !== (await getWho())) return null;
  const headers = new Headers(got.headers);
  headers.set("x-ga-prefetch", "1");
  return new Response(got.body.slice(0), { status: 200, headers });
}

/* F-116: the tab screens (the day, the week, Family) open at once from the copy saved last time, marked `data-ga-stale` on its <html>, while a fresh copy is fetched
   and saved behind it; the page then brings itself up to date (canvas_core.js revalidates the level, thread.js polls). Anything else stays network first. */
function tabScreen(req) {
  if (req.mode !== "navigate") return false;
  const url = new URL(req.url);
  if (url.pathname === "/trip/family") return /^(\?trip=[0-9a-f]+)?$/.test(url.search);
  return url.pathname === "/trip/canvas" && /^(\?day=\d+(&trip=[0-9a-f]+)?|\?trip=[0-9a-f]+)?$/.test(url.search);
}
async function staleTab(event) {
  const req = event.request;
  if (req.cache === "reload" || req.cache === "no-cache") return null;
  const who = await getWho();
  const saved = who ? await (await caches.open(pagesName(who))).match(req) : undefined;
  if (!saved) return null;
  if (!held.has(req.url)) event.waitUntil(fetch(req).then((res) => remember(req, res)).catch(() => {}));     // (a copy the finger already asked for is saved by the prefetch)
  const html = (await saved.text()).replace(/<html(?=[\s>])/i, '<html data-ga-stale="1"');
  const headers = new Headers(saved.headers);
  headers.delete("content-length");      // (the body is a few bytes longer now)
  return new Response(html, { status: 200, headers });
}

self.addEventListener("message", (event) => {
  const d = event.data;
  if (d && d.type === "prefetch" && typeof d.url === "string") event.waitUntil(Promise.resolve(startPrefetch(d.url)).catch(() => {}));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || AUTH_PATH.test(new URL(req.url).pathname)) {
    held.clear();
    // A copy fetched while the write was still being saved could show the old data: clear again once the write has had time to land.
    event.waitUntil(new Promise((resolve) => setTimeout(resolve, 2000)).then(() => held.clear()));
  }
  const kind = routeFor(req);
  if (kind === "asset") event.respondWith(assetFirst(req));
  else if (kind === "page") {
    const ready = held.get(req.url);      // F-116: a fresh copy the finger already brought wins; one still on its way does not hold up a tab screen that has a saved copy
    const first = ready && ready.ready ? fromPrefetch(req) : tabScreen(req) ? staleTab(event) : Promise.resolve(null);
    event.respondWith(first.catch(() => null).then((hit) => hit || fromPrefetch(req)).then((hit) => hit || pageNetworkFirst(req)));
  }
});

/* The morning plan push (F-066) and the family thread push (F-070, tag "family-thread", url /trip/family). A push is always shown (iOS requires it);
   a tap opens the page the push names on this site (Today by default), focusing a GitAway window if one is open. */
const NOTICE_ICON = "/assets/icons/icon-192.png";

/* The notification for a push payload {title, body, url}. Pure, so it can be checked without a browser push. */
function noticeFor(data) {
  const d = data || {};
  const url = new URL(typeof d.url === "string" ? d.url : "/trip", self.location.origin);
  return { title: d.title || "GitAway", options: { body: d.body || "", icon: NOTICE_ICON, badge: NOTICE_ICON, tag: typeof d.tag === "string" && /^[a-z-]{1,32}$/.test(d.tag) ? d.tag : "morning-plan", data: { url: url.origin === self.location.origin ? url.pathname + url.search : "/trip" } } };
}

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) {}
  const n = noticeFor(data);
  event.waitUntil(self.registration.showNotification(n.title, n.options));
});

async function openToday(path) {
  let target = new URL(path, self.location.origin);
  if (target.origin !== self.location.origin) target = new URL("/trip", self.location.origin);
  const url = target.href;
  const open = (await self.clients.matchAll({ type: "window", includeUncontrolled: true })).find((c) => new URL(c.url).origin === self.location.origin);
  if (!open) return self.clients.openWindow(url);
  try { await open.focus(); if ("navigate" in open) await open.navigate(url); } catch (e) {}
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(openToday((event.notification.data && event.notification.data.url) || "/trip"));
});
