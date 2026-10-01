/* GitAway service worker (F-044): keeps the app shell and the pages a traveler has opened for flaky connections.
   Served at /sw.js so its scope is the whole site. Bump VERSION to drop every old cache on the next visit.
   Never touches a POST, another origin, or the sign-in / sign-out routes. */
const VERSION = "v1";
const SHELL = `ga-shell-${VERSION}`;
const ASSETS = `ga-assets-${VERSION}`;
const PAGES = `ga-pages-${VERSION}`;
const MAX_PAGES = 30;
const SHELL_URLS = ["/offline", "/assets/css/tokens.css", "/assets/css/base.css", "/assets/js/pwa.js"];
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

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  const keep = [SHELL, ASSETS, PAGES];
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n.startsWith("ga-") && !keep.includes(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

async function assetFirst(req) {
  const cache = await caches.open(ASSETS);
  const hit = (await caches.match(req)) || (await cache.match(req));
  const refresh = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; });
  if (hit) { refresh.catch(() => {}); return hit; }
  return refresh;
}

async function trim(cache) {
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - MAX_PAGES))) await cache.delete(k);
}

async function pageNetworkFirst(req) {
  const cache = await caches.open(PAGES);
  try {
    const res = await fetch(req);
    if (res.ok && !res.redirected) { await cache.delete(req); await cache.put(req, res.clone()); await trim(cache); }
    return res;
  } catch (err) {
    return (await cache.match(req)) || (await caches.match("/offline")) || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const kind = routeFor(event.request);
  if (kind === "asset") event.respondWith(assetFirst(event.request));
  else if (kind === "page") event.respondWith(pageNetworkFirst(event.request));
});
