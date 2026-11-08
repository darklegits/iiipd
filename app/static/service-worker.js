/* Погодный оракул — офлайн-оболочка PWA */
const CACHE = "weather-oracle-v19";
const SHELL = [
  "/forecast",
  "/sport",
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

// Один и тот же прогноз кэшируется независимо от ?refresh=true:
// иначе офлайн-запрос без refresh не находит последний успешный ответ.
function apiKey(url) {
  const city = url.searchParams.get("city") || "";
  return `${url.origin}${url.pathname}?city=${encodeURIComponent(city)}`;
}

// cache.put может отклониться (например, для редиректа) — это не должно
// ломать ответ странице.
function cachePut(key, response) {
  caches
    .open(CACHE)
    .then((cache) => cache.put(key, response))
    .catch(() => {});
}

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
    // Офлайн отдаём ту же страницу, которую открывали, и только если её
    // нет в кэше — оболочку прогноза.
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            cachePut(request, copy);
          }
          return response;
        })
        .catch(async () => (await caches.match(request)) || (await caches.match("/forecast")))
    );
    return;
  }

  if (url.pathname === "/api/forecast" || url.pathname === "/api/sport") {
    // Неудачный ответ не должен затирать последний успешный прогноз.
    const key = apiKey(url);
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            cachePut(key, copy);
          }
          return response;
        })
        .catch(async () => (await caches.match(key)) || (await caches.match(request)))
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
            cachePut(request, copy);
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
