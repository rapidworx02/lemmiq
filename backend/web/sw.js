const CACHE = "lemmiq-v21074-q-economy-1";
const SHELL = [
  "/web/",
  "/web/index.html?v=2.10.7",
  "/web/styles.css?v=2.10.7",
  "/web/app.js?v=2.10.7",
  "/web/v28.js?v=2.10.7",
  "/web/v28.css?v=2.10.7",
  "/web/v29.js?v=2.10.7",
  "/web/v29.css?v=2.10.7",
  "/web/v210.css?v=2.10.7",
  "/web/v2103.css?v=2.10.7",
  "/web/v2104.css?v=2.10.7",
  "/web/v2104.js?v=2.10.7",
  "/web/v2105.css?v=2.10.7",
  "/web/v2105.js?v=2.10.7",
  "/web/v2106.css?v=2.10.7",
  "/web/v2106.js?v=2.10.7",
  "/web/v2107.css?v=2.10.7",
  "/web/v21071_admin.css?v=2.10.7.1",
  "/web/v21071_admin.js?v=2.10.7.1",
  "/web/v21072_q_usage.css?v=2.10.7.2",
  "/web/v21072_q_usage.js?v=2.10.7.2",
  "/web/v21073_wallets.css?v=2.10.7.3",
  "/web/v21073_wallets.js?v=2.10.7.3",
  "/web/v21074_q_economy.css?v=2.10.7.4",
  "/web/v21074_q_economy.js?v=2.10.7.4",
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

  const apiPrefixes = ["/chats","/agent","/business","/trust","/insights","/media","/users","/login","/register","/download","/v24","/v26","/v27","/v28","/v29","/v210","/v2104","/v2105","/v2106","/v21074","/app-config"];
  if (apiPrefixes.some(x => url.pathname.startsWith(x))) return;

  if (url.pathname === "/web/" || url.pathname.endsWith("/index.html") ||
      url.pathname.endsWith("/app.js") || url.pathname.endsWith("/v28.js") || url.pathname.endsWith("/v29.js") || url.pathname.endsWith("/styles.css") || url.pathname.endsWith("/v28.css") || url.pathname.endsWith("/v29.css") || url.pathname.endsWith("/v210.css") || url.pathname.endsWith("/v2103.css") || url.pathname.endsWith("/v2104.css") || url.pathname.endsWith("/v2104.js") || url.pathname.endsWith("/v2105.css") || url.pathname.endsWith("/v2105.js") || url.pathname.endsWith("/v2106.css") || url.pathname.endsWith("/v2106.js") || url.pathname.endsWith("/v2107.css") || url.pathname.endsWith("/v21071_admin.css") || url.pathname.endsWith("/v21071_admin.js") || url.pathname.endsWith("/v21072_q_usage.css") || url.pathname.endsWith("/v21072_q_usage.js") || url.pathname.endsWith("/v21073_wallets.css") || url.pathname.endsWith("/v21073_wallets.js") || url.pathname.endsWith("/v21074_q_economy.css") || url.pathname.endsWith("/v21074_q_economy.js")) {
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
