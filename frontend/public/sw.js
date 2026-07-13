const CACHE_VERSION = "ibb-portal-static-v1";
const SAFE_ASSETS = ["/offline.html", "/manifest.webmanifest", "/icons/pwa-icon-192.png", "/icons/pwa-icon-512.png", "/icons/pwa-maskable-512.png"];
const PRIVATE_PREFIXES = ["/api/auth", "/api/applications", "/api/documents", "/api/superadmin", "/api/delegations", "/api/partner", "/auth", "/applications", "/documents", "/superadmin", "/delegations", "/partner", "/policies"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(SAFE_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)))));
  self.clients.claim();
});

function isPrivateRequest(requestUrl) {
  return PRIVATE_PREFIXES.some((prefix) => requestUrl.pathname === prefix || requestUrl.pathname.startsWith(`${prefix}/`));
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || isPrivateRequest(url)) {
    event.respondWith(fetch(request));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/offline.html")));
    return;
  }
  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});
