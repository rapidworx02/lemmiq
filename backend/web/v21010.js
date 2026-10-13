/* LEMMIQ V2.10.10 — appearance + optional PWA push */
(()=>{
  const $id=id=>document.getElementById(id);

  function currentTheme(){return document.documentElement.dataset.theme||"light"}
  function applyTheme(theme){
    const t=theme==="dark"?"dark":"light";
    document.documentElement.dataset.theme=t;
    try{localStorage.setItem("lemmiq_theme",t)}catch{}
    const dark=t==="dark";
    document.querySelectorAll(".theme-toggle").forEach(b=>{
      b.textContent=dark?"☀ Light":"☾ Dark";
      b.title=dark?"Switch to light mode":"Switch to dark mode";
    });
    const meta=document.querySelector('meta[name="theme-color"]');
    if(meta)meta.content=dark?"#080b18":"#f7f6fb";
  }
  function toggleTheme(){applyTheme(currentTheme()==="dark"?"light":"dark")}

  async function loadScript(src,id){
    if(id&&document.getElementById(id))return;
    await new Promise((resolve,reject)=>{
      const s=document.createElement("script");if(id)s.id=id;s.src=src;s.onload=resolve;s.onerror=reject;document.head.appendChild(s);
    });
  }

  async function pushStatus(){
    const label=$id("pwaNotifyStatus");
    if(!label)return;
    if(!("Notification" in window)||!("serviceWorker" in navigator)){
      label.textContent="Not supported by this browser";return;
    }
    try{
      const [cfg,status]=await Promise.all([
        fetch("/push/web-config").then(r=>r.json()),
        window.lemmiqState?.token ? api("/push/status") : Promise.resolve({})
      ]);
      if(!cfg.configured){label.textContent="Server setup required";return}
      if(Notification.permission==="granted"&&Number(status.registered_web_devices||0)>0){
        label.textContent="On · tap to refresh";
      }else if(Notification.permission==="denied"){
        label.textContent="Blocked in browser settings";
      }else{
        label.textContent="Off · tap to enable";
      }
    }catch{label.textContent="Tap to configure"}
  }

  async function enablePwaPush(){
    const label=$id("pwaNotifyStatus");
    try{
      if(!window.lemmiqState?.token)throw new Error("Sign in first");
      if(!("Notification" in window)||!("serviceWorker" in navigator))throw new Error("Notifications are not supported by this browser");
      const cfg=await fetch("/push/web-config").then(r=>r.json());
      if(!cfg.configured)throw new Error("PWA notifications are not configured on the server yet");
      const permission=await Notification.requestPermission();
      if(permission!=="granted")throw new Error("Notification permission was not granted");

      await loadScript("https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js","lemmiq-firebase-app");
      await loadScript("https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js","lemmiq-firebase-msg");
      if(!firebase.apps.length)firebase.initializeApp(cfg.firebase_config);
      const registration=await navigator.serviceWorker.ready;
      const token=await firebase.messaging().getToken({vapidKey:cfg.vapid_key,serviceWorkerRegistration:registration});
      if(!token)throw new Error("Browser did not return a push token");
      await api("/push/register",{method:"POST",body:JSON.stringify({token,platform:"WEB"})});
      if(label)label.textContent="On · notifications enabled";
      toast("Browser notifications enabled");
    }catch(err){
      if(label)label.textContent=err.message||"Could not enable";
      toast(err.message||String(err),true);
    }
  }

  document.addEventListener("DOMContentLoaded",()=>{
    applyTheme(currentTheme());
    $id("themeTogglePublic")?.addEventListener("click",toggleTheme);
    $id("themeToggleApp")?.addEventListener("click",toggleTheme);
    $id("pwaNotifyCard")?.addEventListener("click",enablePwaPush);
    pushStatus();
  });

  window.addEventListener("hashchange",()=>{if(location.hash==="#more")setTimeout(pushStatus,50)});
})();