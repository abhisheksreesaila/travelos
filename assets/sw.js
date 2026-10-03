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

self.addEventListener("fetch", (event) => {
  const kind = routeFor(event.request);
  if (kind === "asset") event.respondWith(assetFirst(event.request));
  else if (kind === "page") event.respondWith(pageNetworkFirst(event.request));
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
