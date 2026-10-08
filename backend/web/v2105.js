/* LEMMIQ V2.10.5 — Q Predict main-Q-wallet compatibility layer */
(()=>{
  const token=()=>localStorage.getItem("lemmiq_token")||"";
  const headers=()=>token()?{"Authorization":`Bearer ${token()}`}:{};
  const fmt=v=>Number(v||0).toLocaleString(undefined,{maximumFractionDigits:6});

  async function getJson(url){
    const r=await fetch(url,{headers:headers()});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    return await r.json();
  }

  function normalizeText(root){
    if(!root)return;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    const nodes=[]; while(walker.nextNode())nodes.push(walker.currentNode);
    for(const n of nodes){
      const before=n.nodeValue||"";
      let after=before
        .replace(/Predict Credits?/gi,"Q")
        .replace(/\bPC\b/g,"Q")
        .replace(/test-credit/gi,"Q")
        .replace(/test credits/gi,"Q");
      if(after!==before)n.nodeValue=after;
    }
    root.querySelectorAll?.("button").forEach(b=>{
      const t=(b.textContent||"").toLowerCase();
      if(t.includes("reset") && (t.includes("predict")||t.includes("credit"))) b.style.display="none";
    });
  }

  async function syncPredictQ(){
    const view=document.getElementById("view-q-predict");
    if(!view)return;
    try{
      const [home,wallet]=await Promise.all([
        getJson("/v29/predict/home?category=TRENDING"),
        getJson("/v28/wallet")
      ]);
      const bal=document.getElementById("v29PcBalance");
      if(bal)bal.textContent=`${fmt(wallet.balance_q ?? home.wallet?.balance_q ?? 0)} Q`;
      const notice=document.getElementById("v29PredictNotice");
      if(notice)notice.textContent=home.notice||"Q Predict uses your LEMMIQ Q wallet.";
      normalizeText(view);
    }catch(_e){ normalizeText(view); }
  }

  function install(){
    const original=window.loadQPredict;
    if(typeof original==="function" && !original.__v2105Wrapped){
      const wrapped=async function(...args){
        const out=await original.apply(this,args);
        await syncPredictQ();
        return out;
      };
      wrapped.__v2105Wrapped=true;
      window.loadQPredict=wrapped;
    }

    document.querySelector('[data-view="q-predict"]')?.addEventListener("click",()=>setTimeout(syncPredictQ,80));
    [document.getElementById("view-q-predict"),document.getElementById("view-q-admin")].filter(Boolean).forEach(target=>{
      const mo=new MutationObserver(()=>normalizeText(target));
      mo.observe(target,{childList:true,subtree:true,characterData:true});
      normalizeText(target);
    });
    if(location.hash==="#q-predict")setTimeout(syncPredictQ,100);
  }

  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",install); else install();
})();
