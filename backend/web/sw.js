const CACHE = "lemmiq-v283-shell-1";
const SHELL = [
  "/web/",
  "/web/index.html?v=2.8.3",
  "/web/styles.css?v=2.8.3",
  "/web/app.js?v=2.8.3",
  "/web/v28.js?v=2.8.3",
  "/web/v28.css?v=2.8.3",
  "/web/manifest.webmanifest",
  "/web/icon-192.png",
  "/web/icon-512.png",
  "/web/brand-icon.png"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(()=>{}));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  const apiPrefixes = ["/chats","/agent","/business","/trust","/insights","/media","/users","/login","/register","/download","/v24","/v26","/v27","/v28","/app-config"];
  if (apiPrefixes.some(x => url.pathname.startsWith(x))) return;

  if (url.pathname === "/web/" || url.pathname.endsWith("/index.html") ||
      url.pathname.endsWith("/app.js") || url.pathname.endsWith("/v28.js") || url.pathname.endsWith("/styles.css") || url.pathname.endsWith("/v28.css")) {
    event.respondWith(
      fetch(req).then(res => {
        const copy=res.clone();
        caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});
        return res;
      }).catch(()=>caches.match(req).then(hit=>hit||caches.match("/web/")))
    );
    return;
  }

  event.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res=>{
      const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});return res;
    }))
  );
});
