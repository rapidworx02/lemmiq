const CACHE = "lemmiq-v24-shell-1";
const SHELL = [
  "/web/",
  "/web/index.html",
  "/web/styles.css",
  "/web/app.js",
  "/web/manifest.webmanifest",
  "/web/icon-192.png",
  "/web/icon-512.png",
  "/web/brand-icon.png"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Never cache API or media responses.
  if (url.pathname.startsWith("/chats") ||
      url.pathname.startsWith("/agent") ||
      url.pathname.startsWith("/business") ||
      url.pathname.startsWith("/trust") ||
      url.pathname.startsWith("/insights") ||
      url.pathname.startsWith("/media") ||
      url.pathname.startsWith("/users") ||
      url.pathname.startsWith("/login") ||
      url.pathname.startsWith("/register")) {
    return;
  }

  event.respondWith(
    caches.match(req).then(hit => hit || fetch(req).catch(() => caches.match("/web/")))
  );
});
