const CACHE = "lemmiq-v212-shell-1";
const SHELL = [
  "/web/",
  "/web/index.html?v=2.10.11",
  "/web/styles.css?v=2.10.7",
  "/web/app.js?v=2.10.7",
  "/web/v28.js?v=2.10.7",
  "/web/v29.js?v=2.10.7",
  "/web/v2104.js?v=2.10.7",
  "/web/v2105.js?v=2.10.7",
  "/web/v2106.js?v=2.10.7",
  "/web/v21071_admin.js?v=2.10.7.1",
  "/web/v21072_q_usage.js?v=2.10.7.2",
  "/web/v21073_wallets.js?v=2.10.7.3",
  "/web/v21074_q_economy.js?v=2.10.7.4",
  "/web/v21011.css?v=2.10.11",
  "/web/v21011.js?v=2.10.11",
  "/web/v212_image_gen.js?v=2.12.0",
  "/web/v212_image_gen.css?v=2.12.0",
  "/web/manifest.webmanifest",
  "/web/icon-192.png",
  "/web/icon-512.png",
  "/web/brand-icon.png"
];

self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).catch(()=>{}));self.skipWaiting()});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim()});

self.addEventListener("fetch",event=>{
  const req=event.request;if(req.method!=="GET")return;const url=new URL(req.url);
  const apiPrefixes=["/chats","/agent","/business","/trust","/insights","/media","/users","/login","/register","/download","/push","/v24","/v26","/v27","/v28","/v29","/v210","/v2104","/v2105","/v2106","/v21072","/v21074","/app-config"];
  if(apiPrefixes.some(x=>url.pathname.startsWith(x)))return;
  const isHtml=url.pathname==="/web/"||url.pathname.endsWith("/index.html");
  const versioned=/\.(js|css|png|webmanifest)$/.test(url.pathname);
  if(isHtml){event.respondWith(fetch(req).then(res=>{const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});return res}).catch(()=>caches.match(req).then(x=>x||caches.match("/web/"))));return}
  if(versioned){event.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(res=>{const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy)).catch(()=>{});return res})));}
});

function payloadFrom(event){
  try{const j=event.data?.json?.()||{};return j.data||j.notification||j}catch{}
  try{return {body:event.data?.text?.()||"New LEMMIQ activity"}}catch{return {}}
}
function targetFor(d){
  if(d.chat_id)return `/web/#chat-${encodeURIComponent(d.chat_id)}`;
  if(d.group_id)return `/web/#group-${encodeURIComponent(d.group_id)}`;
  if(String(d.type||"").includes("call"))return "/web/#calls";
  if(String(d.type||"").startsWith("q_predict"))return "/web/#q-predict";
  if(String(d.type||"").startsWith("q_"))return "/web/#q-economy";
  return "/web/#chats";
}
self.addEventListener("push",event=>{
  const d=payloadFrom(event),type=String(d.type||"");
  const title=d.sender_name||d.group_name||(type.includes("call")?"LEMMIQ Call":"LEMMIQ");
  const body=d.body||(type.includes("call")?"Incoming call":"New activity");
  event.waitUntil(self.registration.showNotification(title,{body,icon:"/web/icon-192.png",badge:"/web/icon-192.png",tag:d.call_id?`call-${d.call_id}`:d.chat_id?`chat-${d.chat_id}`:d.group_id?`group-${d.group_id}`:undefined,data:{url:targetFor(d)},renotify:false}));
});
self.addEventListener("notificationclick",event=>{
  event.notification.close();const url=new URL(event.notification.data?.url||"/web/#chats",self.location.origin).href;
  event.waitUntil(self.clients.matchAll({type:"window",includeUncontrolled:true}).then(list=>{for(const c of list){if("focus" in c){c.navigate(url);return c.focus()}}return self.clients.openWindow?self.clients.openWindow(url):undefined}));
});
