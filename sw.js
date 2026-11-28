/* Lightweight Service Worker for instant zero-reload navigation & cached static assets.
   Never caches /api/* requests so live multiplayer polling always stays real-time. */
const CACHE = "agn-v8";
const SHELL = [
  "/festival.css", "/i18n.js", "/theme.js", "/juice.js",
  "/avatars.js", "/backguard.js", "/chat.js", "/pranks.js",
  "/roombar.js", "/howto.js",
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  // Static JS, CSS, images, icons, sounds: Stale-While-Revalidate (0ms cache hit + fresh background update)
  const isAsset = /\.(js|css|jpg|webp|png|mp3|ogg|wav|webmanifest)$/.test(url.pathname);
  if (isAsset) {
    e.respondWith(
      caches.open(CACHE).then(cache =>
        cache.match(req).then(cached => {
          const fresh = fetch(req).then(res => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          }).catch(() => cached);
          return cached || fresh;
        })
      )
    );
    return;
  }

  // HTML pages without ?room=: Cache-first with fast background refresh for instant SPA-like page switches
  if (req.mode === "navigate" && !url.searchParams.has("room")) {
    e.respondWith(
      caches.open(CACHE).then(cache =>
        cache.match(req).then(cached => {
          const fresh = fetch(req).then(res => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          }).catch(() => cached);
          return cached || fresh;
        })
      )
    );
  }
});
