const CACHE = "lemmiq-v21010-shell-1";
const SHELL = [
  "/web/",
  "/web/index.html?v=2.10.10",
  "/web/styles.css?v=2.10.7",
  "/web/app.js?v=2.10.10",
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
  "/web/v21010.css?v=2.10.10",
  "/web/v21010.js?v=2.10.10",
  "/web/manifest.webmanifest",
  "/web/icon-192.png",
  "/web/icon-512.png",
  "/web/brand-icon.png"
];

self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).catch(()=>{}));
  self.skipWaiting();
});
self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));
  self.clients.claim();
});

const API_PREFIXES=["/chats","/agent","/business","/trust","/insights","/media","/users","/login","/register","/download","/push","/v24","/v26","/v27","/v28","/v29","/v210","/app-config"];
function isStaticAsset(url){
  return url.pathname.startsWith("/web/") && /\.(css|js|png|jpg|jpeg|webp|svg|woff2?|webmanifest)$/i.test(url.pathname);
}
self.addEventListener("fetch",event=>{
  const req=event.request;if(req.method!=="GET")return;
  const url=new URL(req.url);
  if(API_PREFIXES.some(x=>url.pathname.startsWith(x)))return;

  // HTML/navigation: network first, old shell only as offline fallback.
  if(req.mode==="navigate"||url.pathname==="/web/"||url.pathname.endsWith("/index.html")){
    event.respondWith(fetch(req).then(res=>{
      const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});return res;
    }).catch(()=>caches.match(req).then(hit=>hit||caches.match("/web/"))));
    return;
  }

  // Versioned/static assets: cache first for speed.
  if(isStaticAsset(url)){
    event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(res=>{
      const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});return res;
    })));
  }
});

/* Optional Firebase Web Push.
   The config script is dynamically served by the LEMMIQ backend and contains
   only the public Firebase web-app config. */
try{
  importScripts("/push/firebase-config.js");
  if(self.__LEMMIQ_FIREBASE_CONFIG__?.apiKey){
    importScripts("https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js");
    importScripts("https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js");
    firebase.initializeApp(self.__LEMMIQ_FIREBASE_CONFIG__);
    const messaging=firebase.messaging();
    messaging.onBackgroundMessage(payload=>{
      const data=payload?.data||{};
      const title=data.title||data.sender_name||"LEMMIQ";
      const options={
        body:data.body||"You have a new LEMMIQ update",
        icon:"/web/icon-192.png",badge:"/web/icon-192.png",
        tag:data.type==="chat"&&data.chat_id?`chat-${data.chat_id}`:`lemmiq-${data.type||"event"}`,
        data:{url:data.url||"/web/#chats"},
        renotify:true
      };
      self.registration.showNotification(title,options);
    });
  }
}catch(_e){}

self.addEventListener("notificationclick",event=>{
  event.notification.close();
  const target=event.notification?.data?.url||"/web/#chats";
  event.waitUntil(clients.matchAll({type:"window",includeUncontrolled:true}).then(list=>{
    for(const client of list){
      if("focus" in client){
        client.navigate(target).catch(()=>{});
        return client.focus();
      }
    }
    return clients.openWindow?clients.openWindow(target):null;
  }));
});
