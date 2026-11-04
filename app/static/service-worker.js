/* Погодный оракул — офлайн-оболочка PWA */
const CACHE = "weather-oracle-v17";
const SHELL = [
  "/forecast",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.webmanifest",
  "/static/favicon.svg",
  "/static/fonts/golos-cyrillic.woff2",
  "/static/fonts/golos-latin.woff2",
  "/static/fonts/cormorant-cyrillic.woff2",
  "/static/fonts/cormorant-latin.woff2",
  "/static/images/hero.jpg",
  "/static/images/hero-2.jpg",
  "/static/images/hero-3.jpg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-180.png",
  "/static/icons/favicon-32.png",
  "/artifacts/forecast_vs_fact.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put("/forecast", copy));
          return response;
        })
        .catch(() => caches.match("/forecast"))
    );
    return;
  }

  if (url.pathname === "/api/forecast") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
