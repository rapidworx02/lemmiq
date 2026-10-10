/* LEMMIQ V2.10.6 — additive web helpers */
(()=>{
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  function bindTalkToQ(){
    const btn=$("talkAgentBtn");if(!btn)return;
    btn.addEventListener("click",()=>{
      const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
      if(!SR){window.toast?.("Speech recognition is not available in this browser.",true);return}
      const r=new SR();r.lang=navigator.language||"en-AU";r.interimResults=false;r.maxAlternatives=1;
      btn.disabled=true;btn.textContent="🎙 Listening…";
      r.onresult=e=>{const spoken=e.results?.[0]?.[0]?.transcript?.trim()||"";if(spoken){$("agentQuestion").value=spoken;window.askAgent?.()}};
      r.onerror=e=>window.toast?.(e.error||"Speech recognition failed",true);
      r.onend=()=>{btn.disabled=false;btn.textContent="🎙 Talk to Q"};
      try{r.start()}catch(e){btn.disabled=false;btn.textContent="🎙 Talk to Q";window.toast?.(e.message,true)}
    });
  }

  function renderTodayDetails(){
    const host=$("qTodayDetails");if(!host)return;
    const today=window.lemmiqState?.qHome?.today||{};
    const needs=Array.isArray(today.needs_reply)?today.needs_reply:[];
    const memories=(window.lemmiqState?.socialBrief?.items||[]).filter(x=>["FOLLOW_UP","DEADLINE","PROMISE"].includes(String(x.memory_type||"").toUpperCase()));
    const rows=[];
    needs.forEach(x=>rows.push({title:(typeof x.contact==="object"?x.contact?.display_name:x.contact)||x.display_name||x.name||"Conversation needs reply",detail:x.message||x.text||x.last_message||x.reason||"Open the conversation to review.",chat_id:x.chat_id}));
    memories.forEach(x=>rows.push({title:`${x.memory_type?.replaceAll("_"," ")||"Follow-up"}${x.contact?` · ${x.contact}`:""}`,detail:x.detail||x.title||"Q follow-up",chat_id:x.chat_id}));
    host.innerHTML=rows.length?rows.slice(0,12).map(x=>`<button class="q2106-today-row" ${x.chat_id?`data-today-chat="${Number(x.chat_id)}"`:""}><strong>${esc(x.title)}</strong><small>${esc(x.detail)}</small></button>`).join(""):`<div class="q2106-today-row"><strong>No detailed items right now.</strong><small>The overview can still include counts from recent conversation analysis.</small></div>`;
    host.querySelectorAll("[data-today-chat]").forEach(b=>b.onclick=()=>{window.setView?.("chats");window.openChat?.(Number(b.dataset.todayChat))});
  }

  function bindToday(){
    const btn=$("qTodayDetailsBtn"),host=$("qTodayDetails");if(!btn||!host)return;
    btn.addEventListener("click",()=>{const opening=host.classList.contains("hidden");host.classList.toggle("hidden",!opening);btn.textContent=opening?"Hide details":"View details";if(opening)renderTodayDetails()});
  }

  function bindQThread(){
    $("qThreadRefreshBtn")?.addEventListener("click",async()=>{try{await window.loadQThread?.();window.renderQThread?.();window.renderChats?.()}catch(e){window.toast?.(e.message,true)}});
    if(location.hash==="#q-thread")setTimeout(async()=>{try{window.setView?.("chats");await window.loadChats?.();await window.openQThread?.()}catch(e){window.toast?.(e.message,true)}},180);
  }


  let walletPeriod="TODAY",walletLedger=[];
  function walletInPeriod(x){
    if(walletPeriod==="ALL")return true;
    const d=new Date(x.created_at||0);if(Number.isNaN(d.getTime()))return false;
    const now=new Date(),start=new Date(now);
    if(walletPeriod==="TODAY")start.setHours(0,0,0,0);
    else if(walletPeriod==="WEEK"){start.setDate(now.getDate()-7);start.setHours(0,0,0,0)}
    else if(walletPeriod==="MONTH"){start.setMonth(now.getMonth()-1);start.setHours(0,0,0,0)}
    else if(walletPeriod==="YEAR"){start.setFullYear(now.getFullYear()-1);start.setHours(0,0,0,0)}
    return d>=start&&d<=now;
  }
  function renderWalletLedger(){
    const host=$("q28Ledger");if(!host)return;
    const rows=walletLedger.filter(walletInPeriod);
    const num=v=>Number(v||0).toLocaleString(undefined,{maximumFractionDigits:6});
    host.innerHTML=rows.length?rows.slice(0,150).map(x=>{
      const dir=String(x.direction||"").toUpperCase(),amount=Number(x.amount_q||0),zero=amount===0;
      const label=zero?"0 Q":`${dir==="IN"?"+":"−"}${num(amount)} Q`;
      const title=String(x.feature_key||x.kind||"Q activity").replaceAll("_"," ");
      return `<div class="q2104-activity-row"><div class="body"><strong>${esc(title)}</strong><small>${esc(x.note||x.reference||"")}</small><small>${esc(String(x.created_at||"").replace("T"," ").slice(0,19))}</small></div><span class="${zero?"q2104-q-zero":dir==="IN"?"q2104-q-in":"q2104-q-out"}">${label}</span></div>`;
    }).join(""):`<p class="micro">No Q activity in this period.</p>`;
  }
  async function loadWalletLedger(){
    const token=localStorage.getItem("lemmiq_token")||"";if(!token)return;
    try{const r=await fetch("/v28/wallet/ledger",{headers:{"Authorization":`Bearer ${token}`}});if(!r.ok)throw new Error(`HTTP ${r.status}`);walletLedger=await r.json();renderWalletLedger()}catch(e){window.toast?.(e.message,true)}
  }
  function bindWalletActivity(){
    document.querySelectorAll("[data-q2106-wallet-period]").forEach(b=>b.addEventListener("click",()=>{walletPeriod=b.dataset.q2106WalletPeriod;document.querySelectorAll("[data-q2106-wallet-period]").forEach(x=>x.classList.toggle("active",x===b));if(walletLedger.length)renderWalletLedger();else loadWalletLedger()}));
    $("q28RefreshLedger")?.addEventListener("click",()=>setTimeout(loadWalletLedger,80));
    document.querySelector('[data-q28-tab="wallet"]')?.addEventListener("click",()=>setTimeout(loadWalletLedger,120));
    document.querySelector('[data-view="q-economy"]')?.addEventListener("click",()=>setTimeout(loadWalletLedger,180));
    if(location.hash==="#q-economy")setTimeout(loadWalletLedger,250);
  }

  function install(){bindTalkToQ();bindToday();bindQThread();bindWalletActivity()}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",install);else install();
})();
