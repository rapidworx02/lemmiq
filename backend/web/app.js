const state = {
  token: localStorage.getItem("lemmiq_token") || "",
  user: JSON.parse(localStorage.getItem("lemmiq_user") || "null"),
  chats: [],
  groups: [],
  activeChat: null,
  activeGroup: null,
  messages: [],
  groupMessages: [],
  chatCalls: [],
  chatFilterMode: "ALL",
  statuses: [],
  statusStoryIds: [],
  statusIndex: -1,
  statusBlobUrl: null,
  trustHistory: [],
  socialBrief: null,
  qHome: null,
  qCoordination: {inbox:[],outbox:[]},
  qThread: {unread_count:0,items:[]},
  vision: [],
  visionBlobUrl: null,
  replyTo: null,
  socket: null,
  installPrompt: null,
  mediaRecorder: null,
  voiceChunks: [],
  voiceStartedAt: 0,
  voiceTarget: "direct",
  callRoom: null,
  callId: null,
  callPhase: "idle",
  callTimerHandle: null,
  callTimeoutHandle: null,
  callSeconds: 0,
  callType: "VOICE",
  cameraFacing: "user",
  ringAudio: null,
  appConfig:{android_download_url:"",android_play_url:"",android_install_url:"/download/android",android_download_configured:false,web_install_enabled:true}
};

window.lemmiqState=state;

const $ = id => document.getElementById(id);
const qsa = s => [...document.querySelectorAll(s)];
const escapeHtml = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = cents => new Intl.NumberFormat(undefined,{style:"currency",currency:"AUD"}).format((cents||0)/100);
const initials = s => (s||"?").trim().split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase();

const timeOnly = iso => { try{return new Date(iso).toLocaleTimeString([],{hour:"numeric",minute:"2-digit"})}catch{return ""} };
const formatDuration = sec => `${String(Math.floor((sec||0)/60)).padStart(2,"0")}:${String((sec||0)%60).padStart(2,"0")}`;
function friendlyDay(iso){
  try{
    const d=new Date(iso),now=new Date();
    const a=new Date(d.getFullYear(),d.getMonth(),d.getDate());
    const b=new Date(now.getFullYear(),now.getMonth(),now.getDate());
    const diff=Math.round((b-a)/86400000);
    if(diff===0)return "Today";
    if(diff===1)return "Yesterday";
    if(diff>1&&diff<7)return d.toLocaleDateString([],{weekday:"long"});
    return d.toLocaleDateString([],{day:"numeric",month:"long",year:"numeric"});
  }catch{return ""}
}
function avatarHtml(u){
  if(u?.avatar_url)return `<span class="avatar"><img src="${escapeHtml(u.avatar_url)}" alt=""></span>`;
  return `<span class="avatar">${escapeHtml(initials(u?.display_name||"?"))}</span>`;
}
function renderMeAvatar(){
  if(!$("meAvatar"))return;
  $("meAvatar").innerHTML=state.user?.avatar_url?`<img src="${escapeHtml(state.user.avatar_url)}" alt="">`:`<span>${escapeHtml(initials(state.user?.display_name||"?"))}</span>`;
}


function toast(msg, error=false){
  const t=$("toast"); t.textContent=msg; t.className="toast"+(error?" error":"");
  clearTimeout(window.__toast); window.__toast=setTimeout(()=>t.classList.add("hidden"),3500);
}
function authHeaders(extra={}) {
  return {...extra, ...(state.token ? {"Authorization":`Bearer ${state.token}`} : {})};
}
async function api(path, opts={}){
  const headers = authHeaders(opts.headers || {});
  if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) headers["Content-Type"]="application/json";
  const r = await fetch(path,{...opts,headers});
  if (r.status===401){ logout(); throw new Error("Session expired"); }
  let body=null;
  const ct=r.headers.get("content-type")||"";
  if(ct.includes("application/json")) body=await r.json(); else body=await r.text();
  if(!r.ok){
    const raw=body?.detail ?? body?.message ?? body ?? `HTTP ${r.status}`;
    let message;
    if(typeof raw==="string") message=raw;
    else if(Array.isArray(raw)) message=raw.map(x=>x?.msg||x?.message||JSON.stringify(x)).join(" · ");
    else {
      try{ message=JSON.stringify(raw); }
      catch{ message=String(raw); }
    }
    throw new Error(message||`HTTP ${r.status}`);
  }
  return body;
}
function saveSession(data){
  state.token=data.token; state.user=data.user;
  localStorage.setItem("lemmiq_token",state.token);
  localStorage.setItem("lemmiq_user",JSON.stringify(state.user));
}
function logout(){
  localStorage.removeItem("lemmiq_token");localStorage.removeItem("lemmiq_user");
  state.token="";state.user=null;
  if(state.socket) try{state.socket.close()}catch{}
  $("appView").classList.add("hidden");$("authView").classList.remove("hidden");
}
function showApp(){
  $("authView").classList.add("hidden");$("appView").classList.remove("hidden");
  $("meName").textContent=state.user?.display_name||"LEMMIQ User";
  $("meUsername").textContent="@"+(state.user?.username||"");
  renderMeAvatar();
  connectSocket();
  const requested=(location.hash||"").replace(/^#/,"");
  const directViews = new Set(["chats","updates","agent","q-economy","q-predict","calls","more","trust","business","activity","money","me","q-admin"]);
  if((requested==="admin" || requested==="q-admin") && window.openQAdminStable) {
    window.openQAdminStable(false);
  } else if(requested==="admin") {
    setView("q-admin");
  } else if(directViews.has(requested)) {
    setView(requested);
  } else {
    refreshCurrent();
  }
  if(window.refreshV28Access) window.refreshV28Access();
}
function chatsHome(pushHistory=false){
  state.activeChat=null;state.activeGroup=null;state.replyTo=null;
  $("globalQOrb")?.classList.remove("q2106-hide-orb");
  const layout=document.querySelector(".chat-layout");if(layout)layout.classList.remove("open-chat");
  if($("activeQThread"))$("activeQThread").classList.add("hidden");
  if($("activeChat"))$("activeChat").classList.add("hidden");
  if($("activeGroup"))$("activeGroup").classList.add("hidden");
  if($("emptyChat"))$("emptyChat").classList.remove("hidden");
  if($("conversationList"))$("conversationList").scrollTop=0;
  window.scrollTo({top:0,behavior:"instant"});
  renderChats();
  loadChats().catch(()=>{});
  if(pushHistory)history.pushState({view:"chats"},"","#chats");
}

function setView(name){
  qsa(".view").forEach(v=>v.classList.remove("active"));
  if(name!=="chats")$("globalQOrb")?.classList.remove("q2106-hide-orb");
  const target=$(`view-${name}`);if(!target)return;
  target.classList.add("active");
  const secondary=["trust","business","activity","money","me","q-admin"];
  const navName=secondary.includes(name)?"more":name;
  qsa("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.view===navName));
  const meta={
    chats:["Chats","Search conversations or ask Q."],
    updates:["Updates","LEMMIQ Status — text, photo and video for 24 hours."],
    agent:["Q","Ask across chats, groups, voice-note transcripts and Social IQ memory."],
    calls:["Calls","Voice and video call history."],
    more:["More","Account and utilities."],
    trust:["LEMMIQ Trust","Fact / Scam Check with saved history."],
    business:["Business Agent","Teach LEMMIQ how your business operates."],
    activity:["Activity","Detected phone activity synced by your Android companion."],
    money:["Money","Review and correct notification-derived payment insights."],
    me:["Me","Your profile photo, account and LEMMIQ access."],
    "q-economy":["Q Economy","Wallet, mining, subscriptions, referrals and Q Market."],
    "q-predict":["Q Predict","Prediction markets using your LEMMIQ Q wallet."],
    "q-admin":["Q Admin","Treasury, Q Predict, USDT payments, marketplace and economy controls."]
  }[name]||["LEMMIQ","Messaging with social IQ."];
  $("pageTitle").textContent=meta[0];$("pageSub").textContent=meta[1];
  refreshView(name);
}
async function refreshView(name){
  try{
    if(name==="chats") await loadChats();
    if(name==="updates") await loadStatuses();
    if(name==="agent") await loadAgentV24();
    if(name==="calls") await loadCalls();
    if(name==="trust") await loadTrustHistory();
    if(name==="business") await loadBusiness();
    if(name==="activity") await loadActivity();
    if(name==="money") await loadMoney();
    if(name==="me") renderMeAvatar();
    if(name==="q-economy" && window.loadQEconomy) await window.loadQEconomy();
    if(name==="q-predict" && window.loadQPredict) await window.loadQPredict();
    if(name==="q-admin") {
      if(window.loadQAdminStable) await window.loadQAdminStable();
      else {
        if(window.loadQAdmin) await window.loadQAdmin();
        if(window.loadV29Admin) await window.loadV29Admin();
        if(window.loadV2108Admin) await window.loadV2108Admin();
      }
    }
  }catch(e){toast(e.message,true)}
}
function refreshCurrent(){
  const active=document.querySelector(".view.active")?.id?.replace("view-","")||"chats";
  refreshView(active);
}

function connectSocket(){
  if(!state.token)return;
  if(state.socket)try{state.socket.close()}catch{}
  const proto=location.protocol==="https:"?"wss":"ws";
  const ws=new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(state.token)}`);
  state.socket=ws;
  ws.onopen=()=>{$("socketDot").classList.add("on");$("socketText").textContent="connected";ws.send("hello")};
  ws.onclose=()=>{$("socketDot").classList.remove("on");$("socketText").textContent="offline";setTimeout(()=>{if(state.token)connectSocket()},4500)};
  ws.onerror=()=>{};
  ws.onmessage=async ev=>{
    try{
      const p=JSON.parse(ev.data);
      if(p.type==="message"){
        await loadChats();
        if(state.activeChat&&p.data?.chat_id===state.activeChat.id)await openChat(state.activeChat.id,false);
      }else if(p.type==="message_update"){
        if(state.activeChat&&p.data?.chat_id===state.activeChat.id){
          state.messages=state.messages.map(m=>m.id===p.data.id?p.data:m);renderMessages();
        }
        await loadChats();
      }else if(p.type==="group_message"){
        await loadChats();
        if(state.activeGroup&&p.group_id===state.activeGroup.id)await openGroup(state.activeGroup.id,false);
      }else if(["q_coordination_request","q_coordination_response","q_coordination_closed"].includes(p.type)){
        await loadQThread();
        if(!$("activeQThread")?.classList.contains("hidden"))renderQThread();
        await loadAgentV24().catch(()=>{});
      }else if(p.type==="incoming_call"){
        showIncomingCall(p);
      }else if(p.type==="call_answered"&&state.callId===p.call_id){
        onRemoteAnswered();
      }else if((p.type==="call_declined"||p.type==="call_ended")&&state.callId===p.call_id){
        stopRing();clearInterval(state.callTimerHandle);clearTimeout(state.callTimeoutHandle);
        $("callState").textContent=p.type==="call_declined"?"Declined":"Call ended";
        setTimeout(()=>endVoiceCall(false),700);
      }
    }catch{}
  };
  window.__wsPing&&clearInterval(window.__wsPing);
  window.__wsPing=setInterval(()=>{if(ws.readyState===1)ws.send("ping")},20000);
}

async function loadQThread(){
  state.qThread=await api("/v2106/q/thread").catch(()=>({unread_count:0,items:[]}));
  return state.qThread;
}
async function loadChats(){
  const [chats,groups,qThread]=await Promise.all([api("/chats"),api("/v24/groups"),loadQThread()]);
  state.chats=chats;state.groups=groups;state.qThread=qThread||state.qThread;renderChats();
}
function renderChats(){
  const query=($("chatFilter")?.value||"").toLowerCase().trim();
  let rows=[
    ...state.chats.map(c=>({kind:"chat",data:c,updated:c.updated_at||"",unread:c.unread||0,pinned:!!c.pinned,
      hay:`${c.other_user.display_name} ${c.other_user.username} ${c.last_message||""} ${c.draft_text||""}`.toLowerCase()})),
    ...state.groups.map(g=>({kind:"group",data:g,updated:g.updated_at||"",unread:g.unread||0,pinned:false,
      hay:`${g.name} ${g.last_message||""} ${(g.members||[]).map(m=>m.username).join(" ")}`.toLowerCase()}))
  ];
  rows=rows.filter(r=>r.hay.includes(query));
  if(state.chatFilterMode==="UNREAD")rows=rows.filter(r=>r.unread>0);
  if(state.chatFilterMode==="GROUPS")rows=rows.filter(r=>r.kind==="group");
  rows.sort((a,b)=>(Number(b.pinned)-Number(a.pinned))||(new Date(b.updated)-new Date(a.updated)));
  const el=$("conversationList");if(!el)return;
  const qp=(state.qThread?.items||[])[0];
  const qHay=`q lemmiq assistant ${qp?.title||""} ${qp?.body||""}`.toLowerCase();
  const qVisible=state.chatFilterMode!=="GROUPS" && (state.chatFilterMode!=="UNREAD" || Number(state.qThread?.unread_count||0)>0) && qHay.includes(query);
  const qRow=qVisible?`<button class="chat-row q-thread-row" onclick="openQThread()"><span class="avatar q-thread-avatar">Q</span><span class="body"><strong>Q · LEMMIQ Assistant</strong><small>${escapeHtml(qp?.body||"Q requests, results and coordination updates")}</small></span>${state.qThread?.unread_count?`<span class="badge">${state.qThread.unread_count}</span>`:""}</button>`:"";
  const normalRows=rows.length?rows.map(r=>{
    if(r.kind==="group"){
      const g=r.data;
      const av=g.photo_url?`<span class="avatar"><img src="${escapeHtml(g.photo_url)}" alt=""></span>`:`<span class="avatar">${escapeHtml(initials(g.name))}</span>`;
      return `<button class="chat-row ${state.activeGroup?.id===g.id?"active":""}" onclick="openGroup(${g.id})">${av}
        <span class="body"><strong>${escapeHtml(g.name)}</strong><small>${g.member_count} members · ${escapeHtml(g.last_message||"New group")}</small></span>
        ${g.unread?`<span class="badge">${g.unread}</span>`:""}</button>`;
    }
    const c=r.data,draft=c.draft_text?`Draft: ${c.draft_text}`:(c.last_message||"Start chatting");
    return `<button class="chat-row ${state.activeChat?.id===c.id?"active":""}" onclick="openChat(${c.id})">${avatarHtml(c.other_user)}
      <span class="body"><strong>${c.pinned?"📌 ":""}${c.favourite?"⭐ ":""}${escapeHtml(c.other_user.display_name)}</strong><small>${escapeHtml(draft)}</small></span>
      ${c.unread?`<span class="badge">${c.unread}</span>`:""}</button>`;
  }).join(""):``;
  el.innerHTML=qRow+normalRows || `<div class="empty-state"><p>No matching conversations.</p></div>`;
}
async function openQThread(){
  state.activeChat=null;state.activeGroup=null;state.replyTo=null;
  $("globalQOrb")?.classList.add("q2106-hide-orb");
  await loadQThread();
  $("emptyChat").classList.add("hidden");$("activeChat").classList.add("hidden");$("activeGroup").classList.add("hidden");$("activeQThread").classList.remove("hidden");
  document.querySelector(".chat-layout")?.classList.add("open-chat");
  renderQThread();
  await api("/v2106/q/thread/read",{method:"POST"}).catch(()=>{});
  state.qThread.unread_count=0;renderChats();
  if(location.hash!=="#q-thread")history.pushState({view:"chats",qThread:true},"","#q-thread");
}
function renderQThread(){
  const host=$("qThreadList");if(!host)return;
  const rows=state.qThread?.items||[];
  host.innerHTML=rows.length?rows.map(item=>{
    const options=(item.options||[]).slice(0,4);
    const status=item.can_respond?"Needs your response":item.mine&&item.status==="PENDING"?`Waiting for ${escapeHtml(item.other_user?.display_name||"contact")}`:item.status==="RESPONDED"?(item.mine?"Response received":"You responded"):item.status==="CLOSED"?"Closed":item.status;
    return `<div class="q-thread-card ${item.can_respond?"needs-response":""}"><div class="q-thread-card-head"><strong>Q ↔ Q</strong><span>${escapeHtml(status)}</span></div><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(item.body)}</p>${item.can_respond?`<div class="q-thread-options">${options.map(o=>`<button class="ghost" data-qthread-choice="${item.request_id}" data-choice="${escapeHtml(o)}">${escapeHtml(o)}</button>`).join("")}</div><div class="q-thread-reply"><input data-qthread-input="${item.request_id}" placeholder="Reply to Q…"><button class="primary" data-qthread-send="${item.request_id}">Send</button></div>`:""}${item.can_cancel?`<button class="mini" data-qthread-cancel="${escapeHtml(item.request_key||"")}">Cancel request</button>`:""}<small>${escapeHtml(String(item.created_at||"").replace("T"," ").slice(0,19))}</small></div>`;
  }).join(""):`<div class="empty-state"><h3>Q</h3><p>No Q updates yet.</p></div>`;
  host.querySelectorAll("[data-qthread-choice]").forEach(b=>b.onclick=()=>respondQThread(Number(b.dataset.qthreadChoice),b.dataset.choice||""));
  host.querySelectorAll("[data-qthread-send]").forEach(b=>b.onclick=()=>{const id=Number(b.dataset.qthreadSend),inp=host.querySelector(`[data-qthread-input="${id}"]`);const val=(inp?.value||"").trim();if(val)respondQThread(id,val)});
  host.querySelectorAll("[data-qthread-cancel]").forEach(b=>b.onclick=()=>cancelQThread(b.dataset.qthreadCancel||""));
  setTimeout(()=>host.scrollTop=host.scrollHeight,20);
}
async function respondQThread(id,choice){
  try{await api(`/v27/q/coordination/${id}/respond`,{method:"POST",body:JSON.stringify({choice,note:""})});await loadQThread();renderQThread();renderChats();toast("Response sent to Q")}
  catch(e){toast(e.message,true)}
}
async function cancelQThread(key){
  if(!key)return;try{await api(`/v27/q/coordination/${encodeURIComponent(key)}`,{method:"DELETE"});await loadQThread();renderQThread();renderChats();toast("Q-to-Q request cancelled")}
  catch(e){toast(e.message,true)}
}
async function openChat(cid,mark=true){
  let chat=state.chats.find(x=>x.id===cid);
  if(!chat){await loadChats();chat=state.chats.find(x=>x.id===cid)}
  if(!chat)return;
  state.activeGroup=null;state.activeChat=chat;state.replyTo=null;
  $("globalQOrb")?.classList.add("q2106-hide-orb");
  const [messages,calls]=await Promise.all([api(`/chats/${cid}/messages`),api(`/v24/chats/${cid}/calls`).catch(()=>[])]);
  state.messages=messages;state.chatCalls=calls;
  if(mark)api(`/chats/${cid}/read`,{method:"POST"}).catch(()=>{});
  $("emptyChat").classList.add("hidden");$("activeQThread")?.classList.add("hidden");$("activeGroup").classList.add("hidden");$("activeChat").classList.remove("hidden");
  $("chatName").textContent=chat.other_user.display_name;
  $("chatMeta").textContent=`@${chat.other_user.username} · ${chat.category} · AI ${chat.ai_mode}`;
  $("chatAvatar").innerHTML=chat.other_user.avatar_url?`<img src="${escapeHtml(chat.other_user.avatar_url)}" alt="">`:escapeHtml(initials(chat.other_user.display_name));
  $("assistBar").classList.toggle("hidden",chat.ai_mode!=="ASSIST");
  $("messageInput").value=chat.draft_text||"";
  clearReplyPreview();
  document.querySelector(".chat-layout").classList.add("open-chat");
  renderMessages();renderChats();
  if(mark&&location.hash!==`#chat-${cid}`)history.pushState({view:"chats",chatId:cid},"",`#chat-${cid}`);
}
function renderMessages(){
  const me=state.user?.id,items=[];
  (state.messages||[]).forEach(m=>items.push({type:"message",at:m.created_at,m}));
  (state.chatCalls||[]).forEach(c=>items.push({type:"call",at:c.started_at,c}));
  items.sort((a,b)=>new Date(a.at)-new Date(b.at));
  let lastDay="",html="";
  for(const item of items){
    const day=friendlyDay(item.at);
    if(day!==lastDay){html+=`<div class="date-separator"><span>${escapeHtml(day)}</span></div>`;lastDay=day}
    if(item.type==="call"){
      const c=item.c;
      const kind=String(c.call_type||"VOICE").toUpperCase()==="VIDEO"?"video call":"voice call";
      const label=c.status==="MISSED"?`Missed ${kind}`:c.status==="DECLINED"?`${kind[0].toUpperCase()+kind.slice(1)} · declined`:c.status==="RINGING"?`${kind[0].toUpperCase()+kind.slice(1)} · no answer`:(kind[0].toUpperCase()+kind.slice(1));
      const detail=c.duration_seconds?`${formatDuration(c.duration_seconds)} · ${timeOnly(c.started_at)}`:timeOnly(c.started_at);
      html+=`<div class="msg call-event"><strong>📞 ${label}</strong><div class="micro">${detail}</div></div>`;
      continue;
    }
    const m=item.m,mine=m.sender_id===me,a=m.attachment;let attach="";
    if(a?.kind==="CONTACT")attach=`<div class="answer-box">👤 <strong>${escapeHtml(a.contact_name)}</strong><br><small>${escapeHtml(a.contact_phone)}</small></div>`;
    else if(a?.kind==="VOICE")attach=`<div class="voice-note"><button class="mini" onclick="loadVoice(${m.id},false,this)">▶ ${Math.round((a.duration_ms||0)/1000)}s</button><button class="mini" onclick="voiceAI(${m.id})">Q</button></div>${a.transcript?`<div class="micro">Transcript: ${escapeHtml(a.transcript)}</div>`:""}`;
    else if(a?.media_id)attach=`<button class="mini" onclick="downloadMedia(${m.id},'${escapeHtml((a.name||"file").replace(/'/g,""))}')">📎 ${escapeHtml(a.name||a.kind)}</button>`;
    const quote=m.reply_to?`<div class="reply-quote">${escapeHtml(m.reply_to.text||"")}</div>`:"";
    const reactions=(m.reactions||[]).map(r=>`<button class="reaction-pill" onclick="reactMessage(${m.id},'${escapeHtml(r.emoji)}')">${escapeHtml(r.emoji)} ${r.count}</button>`).join("");
    html+=`<div class="msg ${mine?"mine":"theirs"}" data-mid="${m.id}">
      <button class="mini msg-action-trigger message-menu" onclick="openMessageMenu(${m.id})">⋯</button>
      ${m.ai_generated?`<div class="micro">✨ AI generated</div>`:""}${quote}
      <div>${escapeHtml(m.text).replace(/\n/g,"<br>")}${m.edited_at?`<span class="edited-tag"> edited</span>`:""}</div>
      ${attach}${reactions?`<div class="reaction-strip">${reactions}</div>`:""}
      ${!mine&&!m.deleted_for_everyone?`<div class="msg-actions"><button class="mini" onclick="checkMessage(${m.id})">🛡 Fact / Scam Check</button></div>`:""}
      <div class="meta"><span>${timeOnly(m.created_at)}</span>${mine?`<span>${m.read_at?"✓✓":"✓"}</span>`:""}</div>
    </div>`;
  }
  $("messageList").innerHTML=html;
  setTimeout(()=>$("messageList").scrollTop=$("messageList").scrollHeight,30);
}
async function sendMessage(){
  const text=$("messageInput").value.trim();if(!state.activeChat||!text)return;
  $("messageInput").value="";
  try{
    if(state.replyTo)await api(`/v24/chats/${state.activeChat.id}/reply`,{method:"POST",body:JSON.stringify({text,reply_to_message_id:state.replyTo.id})});
    else await api(`/chats/${state.activeChat.id}/messages`,{method:"POST",body:JSON.stringify({text})});
    clearReplyPreview();
    await saveDraft("");
    await openChat(state.activeChat.id,false);
  }catch(e){toast(e.message,true)}
}

async function suggestReply(){
  if(!state.activeChat)return;
  try{
    const r=await api(`/chats/${state.activeChat.id}/suggest`,{method:"POST"});
    showSuggestion(r.reply);
  }catch(e){toast(e.message,true)}
}
function showSuggestion(reply){
  const el=$("suggestionCard");
  el.classList.remove("hidden");
  el.innerHTML=`<strong>Q suggested reply</strong><p class="suggestion-text"></p><div class="suggestion-actions"><button class="ghost" data-action="discard">Discard</button><button class="ghost" data-action="edit">Edit</button><button class="primary" data-action="send">Send</button></div>`;
  el.querySelector(".suggestion-text").textContent=reply;
  el.querySelector('[data-action="discard"]').addEventListener("click",()=>discardSuggestion());
  el.querySelector('[data-action="edit"]').addEventListener("click",()=>{$("messageInput").value=reply;discardSuggestion();$("messageInput").focus();saveDraft(reply)});
  el.querySelector('[data-action="send"]').addEventListener("click",async()=>{discardSuggestion();try{await api(`/chats/${state.activeChat.id}/messages`,{method:"POST",body:JSON.stringify({text:reply})});await openChat(state.activeChat.id,false)}catch(e){toast(e.message,true)}})
}
function discardSuggestion(){$("suggestionCard").classList.add("hidden");$("suggestionCard").innerHTML=""}

async function checkMessage(id){
  const m=state.messages.find(x=>x.id===id); if(!m)return;
  await runTrust(m.text);
}
async function runTrust(text){
  $("trustResult").classList.remove("hidden");
  $("trustResult").innerHTML="<h3>🛡 Checking…</h3><p>Analysing scam signals and available evidence.</p>";
  try{
    const r=await api("/trust/check",{method:"POST",body:JSON.stringify({text})});
    const sources=(r.sources||[]).map(s=>`<a class="source" target="_blank" rel="noopener" href="${escapeHtml(s.url)}">↗ ${escapeHtml(s.title||s.url)}</a>`).join("");
    $("trustResult").innerHTML=`
      <span class="status">${escapeHtml(r.status||"UNVERIFIED")}</span>
      <h3>${escapeHtml(r.summary||"Trust result")}</h3>
      <p><strong>Evidence confidence: ${Number(r.confidence||0)}%</strong></p>
      ${(r.reasons||[]).map(x=>`<p>• ${escapeHtml(x)}</p>`).join("")}
      ${sources}
      ${r.advice?`<p><strong>Advice:</strong> ${escapeHtml(r.advice)}</p>`:""}
      <p class="micro">Confidence reflects available evidence, not certainty.</p>`;
    setView("trust");
  }catch(e){$("trustResult").innerHTML=`<h3>Could not complete check</h3><p>${escapeHtml(e.message)}</p>`}
}
window.checkMessage=checkMessage;

async function downloadMedia(id,name){
  try{
    const r=await fetch(`/media/${id}`,{headers:authHeaders()});
    if(!r.ok)throw new Error(`Download failed (${r.status})`);
    const blob=await r.blob(); const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download=name||"lemmiq-file";document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){toast(e.message,true)}
}
window.downloadMedia=downloadMedia;

async function uploadAttachment(file){
  if(!state.activeChat||!file)return;
  const fd=new FormData();fd.append("file",file);
  try{toast("Uploading…");await api(`/chats/${state.activeChat.id}/attachments`,{method:"POST",body:fd});await openChat(state.activeChat.id,false);toast("Sent")}
  catch(e){toast(e.message,true)}
}
async function showNewChat(){
  openModal(`<h3>Start a new chat</h3><input id="userSearch" placeholder="Search username or name"><div id="userResults" class="modal-results"></div>`);
  $("userSearch").oninput=async e=>{
    const q=e.target.value.trim();
    if(q.length<2){$("userResults").innerHTML="";return}
    try{
      const rows=await api(`/users/search?q=${encodeURIComponent(q)}`);
      $("userResults").innerHTML=rows.map(u=>`<div class="user-result"><div><strong>${escapeHtml(u.display_name)}</strong><small> @${escapeHtml(u.username)}</small></div><button class="primary" onclick="startChat(${u.id})">Chat</button></div>`).join("");
    }catch(e){toast(e.message,true)}
  };
}
async function startChat(uid){
  try{
    const c=await api("/chats/direct",{method:"POST",body:JSON.stringify({user_id:uid})});
    closeModal();await loadChats();await openChat(c.id);
  }catch(e){toast(e.message,true)}
}
window.startChat=startChat;

async function loadAgent(){
  const [brief,profile]=await Promise.all([api("/agent/brief"),api("/agent/profile?days=30")]);
  $("briefText").textContent=brief.summary||"";
  $("briefStats").innerHTML=`<div class="stat"><strong>${brief.unread_total||0}</strong><span>Unread</span></div><div class="stat"><strong>${brief.needs_reply_count||0}</strong><span>Needs reply</span></div>`;
  $("styleSummary").textContent=profile.summary||"Not enough messages yet.";
  $("styleSignals").innerHTML=(profile.signals||[]).map(x=>`<span>${escapeHtml(x)}</span>`).join("");
}
async function askAgent(){
  const q=$("agentQuestion").value.trim();if(!q)return;
  $("agentAnswer").innerHTML="<div class='answer-box'>Q is thinking…</div>";
  try{
    const r=await api("/agent/ask",{method:"POST",body:JSON.stringify({question:q,days:30,external_context:[]})});
    $("agentAnswer").innerHTML=`<div class="answer-box"><strong>Q</strong><p>${escapeHtml(r.answer||"")}</p>${(r.references||[]).map(x=>`<p class="micro">• ${escapeHtml(x.contact||"")}: ${escapeHtml(x.text||"")}</p>`).join("")}</div>`;
  }catch(e){$("agentAnswer").innerHTML=`<div class="answer-box">${escapeHtml(e.message)}</div>`}
}
async function chatSummary(){
  if(!state.activeChat)return;
  openModal("<h3>🧠 Chat Summary</h3><p>Generating…</p>");
  try{
    const r=await api(`/agent/chats/${state.activeChat.id}/summary`);
    $("modalContent").innerHTML=`<h3>🧠 Chat Summary</h3><p>${escapeHtml(r.summary||"")}</p>
    ${(r.key_points||[]).length?`<h4>Key points</h4>${r.key_points.map(x=>`<p>• ${escapeHtml(x)}</p>`).join("")}`:""}
    ${(r.follow_ups||[]).length?`<h4>Possible follow-ups</h4>${r.follow_ups.map(x=>`<p>• ${escapeHtml(x)}</p>`).join("")}`:""}`;
  }catch(e){$("modalContent").innerHTML=`<h3>Summary failed</h3><p>${escapeHtml(e.message)}</p>`}
}

async function loadBusiness(){
  const [p,k]=await Promise.all([api("/business/profile"),api("/business/knowledge")]);
  $("bizEnabled").checked=!!p.enabled;$("bizName").value=p.business_name||"";$("bizType").value=p.business_type||"";
  $("bizDescription").value=p.description||"";$("bizWebsite").value=p.website||"";$("bizPhone").value=p.phone||"";
  $("bizEmail").value=p.email||"";$("bizHours").value=p.hours||"";$("bizArea").value=p.service_area||"";
  $("bizTone").value=p.tone||"Professional";$("bizCurrency").value=p.currency||"AUD";$("bizThreshold").value=p.auto_threshold||90;
  renderKnowledge(k);
}
function renderKnowledge(rows){
  $("knowledgeList").innerHTML=rows.length?rows.map(k=>`<div class="kb"><div class="kb-head"><div><span class="tag">${escapeHtml(k.category)}</span><strong> ${escapeHtml(k.title)}</strong></div><button class="mini" onclick="deleteKb(${k.id})">Delete</button></div><p>${escapeHtml(k.content)}</p><small class="micro">${escapeHtml(k.source||"Manual")}</small></div>`).join(""):"<p class='micro'>No approved knowledge yet.</p>";
}
async function saveBusiness(){
  const body={
    enabled:$("bizEnabled").checked,business_name:$("bizName").value,business_type:$("bizType").value,
    description:$("bizDescription").value,website:$("bizWebsite").value,phone:$("bizPhone").value,email:$("bizEmail").value,
    hours:$("bizHours").value,service_area:$("bizArea").value,tone:$("bizTone").value,currency:$("bizCurrency").value,
    auto_threshold:Number($("bizThreshold").value||90)
  };
  try{await api("/business/profile",{method:"PUT",body:JSON.stringify(body)});toast("Business Agent saved")}
  catch(e){toast(e.message,true)}
}
async function addKnowledge(){
  const body={category:$("kbCategory").value,title:$("kbTitle").value.trim(),content:$("kbContent").value.trim(),source:"Web dashboard",approved:true,active:true};
  if(!body.title||!body.content)return toast("Add a title and content",true);
  try{await api("/business/knowledge",{method:"POST",body:JSON.stringify(body)});$("kbTitle").value="";$("kbContent").value="";await loadBusiness();toast("Knowledge added")}
  catch(e){toast(e.message,true)}
}
async function deleteKb(id){
  if(!confirm("Delete this knowledge item?"))return;
  try{await api(`/business/knowledge/${id}`,{method:"DELETE"});await loadBusiness()}catch(e){toast(e.message,true)}
}
window.deleteKb=deleteKb;
async function uploadBizDoc(file){
  if(!file)return;const fd=new FormData();fd.append("file",file);
  try{toast("Reading business document…");await api("/business/knowledge/upload",{method:"POST",body:fd});await loadBusiness();toast("Document added to knowledge")}
  catch(e){toast(e.message,true)}
}


async function personalChatSettings(){
  if(!state.activeChat)return;
  const c=state.activeChat;
  const categories=["PARTNER","DATING","BESTIE","FRIEND","FAMILY","WORK","CUSTOMER","SALES","STUDY","CUSTOM"];
  const tones=["Natural","Warm","Casual","Professional","Direct","Playful","Respectful"];
  openModal(`<h3>⚙ Chat Intelligence — ${escapeHtml(c.other_user.display_name)}</h3>
    <div class="settings-grid">
      <label>AI mode
        <select id="personalAiMode">
          ${["OFF","ASSIST","AUTO"].map(x=>`<option ${c.ai_mode===x?"selected":""}>${x}</option>`).join("")}
        </select>
      </label>
      <label>Relationship / category
        <select id="personalCategory">
          ${categories.map(x=>`<option ${c.category===x?"selected":""}>${x}</option>`).join("")}
        </select>
      </label>
      <label class="wide">Tone
        <select id="personalTone">${tones.map(x=>`<option ${c.tone===x?"selected":""}>${x}</option>`).join("")}</select>
      </label>
    </div>
    <div class="answer-box" style="margin-top:14px">
      <strong>How it works</strong>
      <p class="micro"><b>ASSIST</b> drafts replies for you. <b>AUTO</b> can reply server-side even when you are using Safari/iPhone. If the Business Agent is enabled for this customer chat, Business AUTO takes priority over Personal AUTO.</p>
    </div>
    <div class="suggestion-actions"><button id="savePersonalAi" class="primary">Save Chat Intelligence</button></div>`);
  $("savePersonalAi").onclick=async()=>{
    try{
      const updated=await api(`/chats/${c.id}/settings`,{
        method:"PUT",
        body:JSON.stringify({
          category:$("personalCategory").value,
          ai_mode:$("personalAiMode").value,
          tone:$("personalTone").value
        })
      });
      state.activeChat=updated;
      state.chats=state.chats.map(x=>x.id===updated.id?updated:x);
      $("chatMeta").textContent=`@${updated.other_user.username} · ${updated.category} · AI ${updated.ai_mode}`;
      renderChats();closeModal();toast("Chat Intelligence saved");
    }catch(e){toast(e.message,true)}
  };
}

async function businessChatSettings(){
  if(!state.activeChat)return;
  let data;
  try{data=await api(`/business/chats/${state.activeChat.id}`)}catch(e){return toast(e.message,true)}
  const s=data.setting,m=data.memory;
  openModal(`<h3>💼 Business Agent — ${escapeHtml(state.activeChat.other_user.display_name)}</h3>
    <label class="switch-row">Enable Business Agent <input id="bcEnabled" type="checkbox" ${s.enabled?"checked":""}></label>
    <label>Mode<select id="bcMode"><option ${s.mode==="OFF"?"selected":""}>OFF</option><option ${s.mode==="ASSIST"?"selected":""}>ASSIST</option><option ${s.mode==="AUTO"?"selected":""}>AUTO</option></select></label>
    <label>Customer label<input id="bcLabel" value="${escapeHtml(s.customer_label||"")}"></label>
    <label>Customer notes<textarea id="bcNotes">${escapeHtml(m.notes||"")}</textarea></label>
    <label>Tags<input id="bcTags" value="${escapeHtml(m.tags||"")}"></label>
    <div class="suggestion-actions"><button id="bcSave" class="primary">Save</button><button id="bcSuggest" class="ghost">Generate business reply</button></div>
    <p class="micro">AUTO still follows the Business Agent's confidence threshold and high-risk safeguards.</p>`);
  $("bcSave").onclick=async()=>{
    try{
      await api(`/business/chats/${state.activeChat.id}`,{method:"PUT",body:JSON.stringify({enabled:$("bcEnabled").checked,mode:$("bcMode").value,customer_label:$("bcLabel").value})});
      await api(`/business/chats/${state.activeChat.id}/memory`,{method:"PUT",body:JSON.stringify({notes:$("bcNotes").value,tags:$("bcTags").value})});
      toast("Business chat settings saved");closeModal();
    }catch(e){toast(e.message,true)}
  };
  $("bcSuggest").onclick=async()=>{
    try{const r=await api(`/business/chats/${state.activeChat.id}/suggest`,{method:"POST"});closeModal();showBusinessSuggestion(r)}
    catch(e){toast(e.message,true)}
  };
}
function showBusinessSuggestion(r){
  const src=(r.sources||[]).map(x=>x.title).join(", ");
  const reply=r.reply||"";
  const el=$("suggestionCard");el.classList.remove("hidden");
  el.innerHTML=`<strong>💼 Business Agent · ${Number(r.confidence||0)}% grounded</strong>
  <p class="suggestion-text"></p><p class="micro">${escapeHtml(r.reason||"")}${src?`<br>Sources: ${escapeHtml(src)}`:""}</p>
  <div class="suggestion-actions"><button class="ghost" data-action="discard">Discard</button><button class="ghost" data-action="edit">Edit</button><button class="primary" data-action="send">Send</button></div>`;
  el.querySelector(".suggestion-text").textContent=reply;
  el.querySelector('[data-action="discard"]').addEventListener("click",discardSuggestion);
  el.querySelector('[data-action="edit"]').addEventListener("click",()=>{$("messageInput").value=reply;discardSuggestion();$("messageInput").focus();saveDraft(reply)});
  el.querySelector('[data-action="send"]').addEventListener("click",async()=>{discardSuggestion();try{await api(`/chats/${state.activeChat.id}/messages`,{method:"POST",body:JSON.stringify({text:reply})});await openChat(state.activeChat.id,false)}catch(e){toast(e.message,true)}});
}


let lastInsightBrief=null;

function eventHtml(e){
  const amount=e.amount_cents==null?"":`${e.direction==="IN"?"+":e.direction==="OUT"?"−":""}${money(e.amount_cents)}`;
  return `<div class="event">
    <div>
      <strong>${escapeHtml(e.title)}</strong>
      <small>${escapeHtml(e.source)} · ${escapeHtml(e.category)} · ${new Date(e.occurred_at).toLocaleString()}</small>
      <small>${escapeHtml(e.detail||"")}</small>
      <div class="event-actions"><button class="mini" onclick="manageInsightEvent(${Number(e.id)})">Edit / manage</button></div>
    </div>
    ${amount?`<div class="money">${amount}</div>`:""}
  </div>`;
}

async function fetchInsights(){
  lastInsightBrief=await api("/insights/brief?days=30");
  return lastInsightBrief;
}

async function loadActivity(){
  const r=await fetchInsights();
  $("spendingValue").textContent=money(r.spending_cents);
  $("activityStats").innerHTML=`<div class="stat"><strong>${r.detected_count||0}</strong><span>Detected events</span></div><div class="stat"><strong>${r.transactions||0}</strong><span>Transactions</span></div><div class="stat"><strong>${money(r.incoming_cents)}</strong><span>Detected incoming</span></div>`;
  $("activityList").innerHTML=(r.events||[]).length?(r.events||[]).map(eventHtml).join(""):"<p class='micro'>No synced notification activity yet.</p>";
}

async function loadMoney(){
  const r=await fetchInsights();
  $("moneySpendValue").textContent=money(r.spending_cents);
  const payments=(r.events||[]).filter(x=>x.category==="MONEY");
  $("moneyStats").innerHTML=`<div class="stat"><strong>${money(r.incoming_cents)}</strong><span>Detected income</span></div><div class="stat"><strong>${payments.length}</strong><span>Payment alerts shown</span></div>`;
  $("moneyEventList").innerHTML=payments.length?payments.map(eventHtml).join(""):"<p class='micro'>No synced Money events yet.</p>";
}

async function manageInsightEvent(id){
  if(!lastInsightBrief)await fetchInsights();
  const e=(lastInsightBrief.events||[]).find(x=>Number(x.id)===Number(id));
  if(!e)return toast("Event is no longer available",true);
  const amount=e.amount_cents==null?"":(e.amount_cents/100).toFixed(2);
  const cats=["MONEY","BILL","DELIVERY","WORK","TRAVEL","TRUST","GENERAL"];
  const dirs=["OUT","IN","UNKNOWN"];
  openModal(`<h3>Manage detected event</h3>
    <p class="micro">Correct notification-derived data or remove incorrect/duplicate events. Totals recalculate automatically.</p>
    <div class="settings-grid">
      <label>Category<select id="eventCategory">${cats.map(x=>`<option ${e.category===x?"selected":""}>${x}</option>`).join("")}</select></label>
      <label>Direction<select id="eventDirection">${dirs.map(x=>`<option ${e.direction===x?"selected":""}>${x}</option>`).join("")}</select></label>
      <label class="wide">Title<input id="eventTitle" value="${escapeHtml(e.title)}"></label>
      <label>Source<input id="eventSource" value="${escapeHtml(e.source)}"></label>
      <label>Amount AUD<input id="eventAmount" value="${escapeHtml(amount)}" placeholder="Blank if none"></label>
      <label class="wide">Description<textarea id="eventDetail">${escapeHtml(e.detail||"")}</textarea></label>
      <label class="wide">Date/time<input id="eventOccurred" value="${escapeHtml(e.occurred_at)}"></label>
    </div>
    <div class="suggestion-actions">
      <button id="deleteEventBtn" class="danger">Delete / duplicate / incorrect</button>
      <button id="saveEventBtn" class="primary">Save changes</button>
    </div>`);
  $("saveEventBtn").onclick=async()=>{
    const raw=$("eventAmount").value.trim().replace(/,/g,"");
    const amountCents=raw===""?null:Math.round(Number(raw)*100);
    if(raw!=="" && !Number.isFinite(amountCents))return toast("Enter a valid amount",true);
    try{
      await api(`/insights/events/${id}`,{
        method:"PUT",
        body:JSON.stringify({
          category:$("eventCategory").value,
          source:$("eventSource").value,
          title:$("eventTitle").value,
          detail:$("eventDetail").value,
          amount_cents:amountCents,
          direction:$("eventDirection").value,
          occurred_at:$("eventOccurred").value
        })
      });
      closeModal();toast("Detected event updated");await refreshInsightViews();
    }catch(err){toast(err.message,true)}
  };
  $("deleteEventBtn").onclick=async()=>{
    if(!confirm("Remove this event from detected data and totals?"))return;
    try{await api(`/insights/events/${id}`,{method:"DELETE"});closeModal();toast("Detected event removed");await refreshInsightViews()}
    catch(err){toast(err.message,true)}
  };
}
window.manageInsightEvent=manageInsightEvent;

async function resetInsights(scope){
  const label=scope==="MONEY"?"Money data":scope==="ACTIVITY"?"Activity data":"all detected data";
  if(!confirm(`Reset ${label}? This cannot be undone.`))return;
  try{
    await api(`/insights/events?scope=${encodeURIComponent(scope)}`,{method:"DELETE"});
    toast(`${label} reset`);
    await refreshInsightViews();
  }catch(e){toast(e.message,true)}
}
async function refreshInsightViews(){
  lastInsightBrief=null;
  const current=document.querySelector("#nav button.active")?.dataset.view;
  if(current==="money")await loadMoney(); else if(current==="activity")await loadActivity();
}

function openModal(html){$("modalContent").innerHTML=html;$("modal").showModal()}
function closeModal(){$("modal").close()}

async function loadAppConfig(){
  try{
    state.appConfig=await api("/app-config");
    const configured=!!state.appConfig.android_download_configured;
    $("androidBtnTop")?.classList.remove("hidden");
    if($("androidInstallHint")){
      $("androidInstallHint").textContent=state.appConfig.android_play_url
        ? "Google Play internal testing is active. Tap the button to open the tester install page."
        : configured
          ? "Android download is active. Tap the button to install the native LEMMIQ app."
          : "Android install is not configured yet. Add the Play internal-testing URL on Render.";
    }
    const playLabel=state.appConfig.android_play_url?"📱 Get LEMMIQ on Google Play":"📱 Get LEMMIQ for Android";
    if($("androidDownloadPublicBtn"))$("androidDownloadPublicBtn").textContent=playLabel;
    if($("androidBtnTop"))$("androidBtnTop").textContent=playLabel;
  }catch(e){console.warn("App config unavailable",e)}
}
function installAndroidApp(){
  if(state.appConfig?.android_download_configured){
    window.location.href=state.appConfig.android_install_url||"/download/android";
    return;
  }
  openModal(`<h3>📱 Android download setup</h3>
    <p>The LEMMIQ button is wired to <strong>/download/android</strong>, but no APK/Play destination is configured on the server yet.</p>
    <p>Publish your V2.8 app bundle to Google Play and set <strong>ANDROID_APK_URL</strong>/<strong>ANDROID_PLAY_URL</strong>, or place a built APK at <strong>backend/web/downloads/LEMMIQ.apk</strong> and redeploy.</p>
    <p class="micro">After Render redeploys, this same button becomes a direct user download link—no website code change is required.</p>`);
}

async function installHelp(){
  if(state.installPrompt){
    state.installPrompt.prompt();
    await state.installPrompt.userChoice;
    state.installPrompt=null;$("installBtn").classList.add("hidden");
  }else{
    openModal(`<h3>🌐 Install LEMMIQ Web App</h3><p>This installs the browser/PWA version, not the native Android APK.</p><p><strong>Android / Chrome:</strong> browser menu → <em>Install app</em> or <em>Add to Home screen</em>.</p><p><strong>iPhone / iPad:</strong> Safari → Share → <em>Add to Home Screen</em>.</p><p class="micro">The installed PWA uses the same cloud account. Android's native companion app is still required for cross-app notification intelligence.</p>`);
  }
}


// ---------------- LEMMIQ V2.4 Messenger + Social IQ ----------------

function setReplyPreview(m){
  state.replyTo=m;const el=$("replyPreview");el.classList.remove("hidden");
  el.innerHTML=`<div class="body"><strong>Replying</strong><p>${escapeHtml(m.text||"")}</p></div><button class="mini" id="cancelReply">×</button>`;
  $("cancelReply").onclick=clearReplyPreview;$("messageInput").focus();
}
function clearReplyPreview(){state.replyTo=null;if($("replyPreview")){$("replyPreview").classList.add("hidden");$("replyPreview").innerHTML=""}}
async function reactMessage(id,emoji){try{await api(`/v24/messages/${id}/reaction`,{method:"POST",body:JSON.stringify({emoji})});await openChat(state.activeChat.id,false)}catch(e){toast(e.message,true)}}
async function openMessageMenu(id){
  const m=state.messages.find(x=>x.id===id);if(!m)return;const mine=m.sender_id===state.user?.id;
  openModal(`<h3>Message actions</h3><div class="modal-actions">
    <button id="maReply" class="ghost">↩ Reply</button><button id="maReact" class="ghost">❤️ React</button><button id="maForward" class="ghost">↗ Forward</button>
    ${mine&&!m.deleted_for_everyone?`<button id="maEdit" class="ghost">✏ Edit</button><button id="maDeleteAll" class="danger">🗑 Delete for everyone</button>`:""}
    <button id="maDeleteMe" class="danger">Delete for me</button></div>`);
  $("maReply").onclick=()=>{closeModal();setReplyPreview(m)};
  $("maReact").onclick=()=>{closeModal();openModal(`<h3>React</h3><div class="reaction-picker">${["👍","❤️","😂","😮","😢","🙏"].map(x=>`<button class="ghost" data-react="${x}">${x}</button>`).join("")}</div>`);qsa("[data-react]").forEach(b=>b.onclick=async()=>{await reactMessage(id,b.dataset.react);closeModal()})};
  $("maForward").onclick=()=>{closeModal();openForwardDialog(m)};
  if($("maEdit"))$("maEdit").onclick=async()=>{const text=prompt("Edit message",m.text||"");if(text?.trim()){try{await api(`/v24/messages/${id}`,{method:"PUT",body:JSON.stringify({text:text.trim()})});closeModal();await openChat(state.activeChat.id,false)}catch(e){toast(e.message,true)}}};
  if($("maDeleteAll"))$("maDeleteAll").onclick=async()=>{if(confirm("Delete this message for everyone?")){await api(`/v24/messages/${id}?scope=everyone`,{method:"DELETE"});closeModal();await openChat(state.activeChat.id,false)}};
  $("maDeleteMe").onclick=async()=>{await api(`/v24/messages/${id}?scope=me`,{method:"DELETE"});closeModal();await openChat(state.activeChat.id,false)};
}
async function openForwardDialog(m){
  openModal(`<h3>Forward message</h3><p>${escapeHtml(m.text||"")}</p><div id="forwardTargets"></div><button id="forwardNow" class="primary full">Forward</button>`);
  const selected=new Set();
  $("forwardTargets").innerHTML=state.chats.map(c=>`<label class="check-row"><input type="checkbox" data-fwd="${c.id}"> ${escapeHtml(c.other_user.display_name)}</label>`).join("");
  qsa("[data-fwd]").forEach(x=>x.onchange=()=>x.checked?selected.add(Number(x.dataset.fwd)):selected.delete(Number(x.dataset.fwd)));
  $("forwardNow").onclick=async()=>{if(!selected.size)return toast("Choose at least one chat",true);await api(`/v24/messages/${m.id}/forward`,{method:"POST",body:JSON.stringify({chat_ids:[...selected]})});closeModal();toast("Message forwarded")};
}
async function saveDraft(text){
  if(!state.activeChat)return;
  try{
    await api(`/v24/chats/${state.activeChat.id}/preferences`,{method:"PUT",body:JSON.stringify({draft_text:text})});
    const c=state.chats.find(x=>x.id===state.activeChat.id);if(c)c.draft_text=text;renderChats();
  }catch{}
}
async function openChatSearch(){
  if(!state.activeChat)return;
  openModal(`<h3>Search this chat</h3><input id="insideSearch" placeholder="Search messages"><div id="insideResults"></div>`);
  $("insideSearch").oninput=async e=>{
    const q=e.target.value.trim();if(q.length<2){$("insideResults").innerHTML="";return}
    const rows=await api(`/v24/chats/${state.activeChat.id}/search?q=${encodeURIComponent(q)}`);
    $("insideResults").innerHTML=rows.map(m=>`<div class="history-item"><p>${escapeHtml(m.text)}</p><span class="micro">${new Date(m.created_at).toLocaleString()}</span></div>`).join("")||`<p class="micro">No matches.</p>`;
  };
}
async function openChatMore(){
  const c=state.activeChat;if(!c)return;const p=await api(`/v24/chats/${c.id}/preferences`);
  openModal(`<h3>${escapeHtml(c.other_user.display_name)}</h3><div class="modal-actions">
    <button id="togglePin" class="ghost">${p.pinned?"Unpin":"📌 Pin"} chat</button>
    <button id="toggleFav" class="ghost">${p.favourite?"Remove favourite":"⭐ Favourite"}</button>
    <button id="toggleArchive" class="ghost">${p.archived?"Unarchive":"Archive"}</button>
    <button id="mute8h" class="ghost">🔕 Mute 8 hours</button>
    <button id="blockUser" class="danger">Block user</button><button id="reportUser" class="danger">Report</button></div>`);
  const update=async payload=>{await api(`/v24/chats/${c.id}/preferences`,{method:"PUT",body:JSON.stringify(payload)});closeModal();await loadChats()};
  $("togglePin").onclick=()=>update({pinned:!p.pinned});$("toggleFav").onclick=()=>update({favourite:!p.favourite});$("toggleArchive").onclick=()=>update({archived:!p.archived});$("mute8h").onclick=()=>update({muted_minutes:480});
  $("blockUser").onclick=async()=>{if(confirm("Block this user?")){await api(`/v24/users/${c.other_user.id}/block`,{method:"POST"});closeModal();toast("User blocked")}};
  $("reportUser").onclick=async()=>{const details=prompt("Optional report details","")||"";await api(`/v24/users/${c.other_user.id}/report`,{method:"POST",body:JSON.stringify({reason:"OTHER",details})});closeModal();toast("Report submitted")};
}
window.openMessageMenu=openMessageMenu;window.reactMessage=reactMessage;

async function showNewGroup(){
  openModal(`<h3>👥 New LEMMIQ group</h3><label>Group name<input id="ngName" placeholder="Weekend Crew"></label><label>Search usernames<input id="ngSearch" placeholder="Username or display name"></label><div id="ngResults"></div><div id="ngSelected" class="chips"></div><button id="ngCreate" class="primary full">Create group</button>`);
  const chosen=new Map();
  const redraw=()=>{$("ngSelected").innerHTML=[...chosen.values()].map(u=>`<span>@${escapeHtml(u.username)} <button class="mini" data-unpick="${u.id}">×</button></span>`).join("");qsa("[data-unpick]").forEach(b=>b.onclick=()=>{chosen.delete(Number(b.dataset.unpick));redraw()})};
  $("ngSearch").oninput=async e=>{const q=e.target.value.trim();if(q.length<2){$("ngResults").innerHTML="";return}const rows=await api(`/users/search?q=${encodeURIComponent(q)}`);$("ngResults").innerHTML=rows.map(u=>`<div class="user-result"><span>${escapeHtml(u.display_name)} @${escapeHtml(u.username)}</span><button class="mini" data-pick="${u.id}">Add</button></div>`).join("");qsa("[data-pick]").forEach(b=>b.onclick=()=>{const u=rows.find(x=>x.id===Number(b.dataset.pick));if(u){chosen.set(u.id,u);redraw()}})};
  $("ngCreate").onclick=async()=>{const name=$("ngName").value.trim();if(!name||!chosen.size)return toast("Add a group name and at least one member",true);const g=await api("/v24/groups",{method:"POST",body:JSON.stringify({name,member_ids:[...chosen.keys()]})});closeModal();await loadChats();await openGroup(g.id)};
}
async function openGroup(gid,pushHistory=true){
  state.activeChat=null;state.replyTo=null;
  $("globalQOrb")?.classList.add("q2106-hide-orb");
  const g=await api(`/v24/groups/${gid}`);state.activeGroup=g;state.groupMessages=await api(`/v24/groups/${gid}/messages`);await api(`/v24/groups/${gid}/read`,{method:"POST"}).catch(()=>{});
  $("emptyChat").classList.add("hidden");$("activeQThread")?.classList.add("hidden");$("activeChat").classList.add("hidden");$("activeGroup").classList.remove("hidden");
  $("groupName").textContent=g.name;$("groupMeta").textContent=`${g.member_count} members · Q ${g.ai_mode}`;
  $("groupAvatar").innerHTML=g.photo_url?`<img src="${escapeHtml(g.photo_url)}" alt="">`:escapeHtml(initials(g.name));
  $("groupAssistBar").classList.toggle("hidden",g.ai_mode!=="ASSIST");renderGroupMessages();renderChats();
  document.querySelector(".chat-layout").classList.add("open-chat");
  if(pushHistory&&location.hash!==`#group-${gid}`)history.pushState({view:"chats",groupId:gid},"",`#group-${gid}`);
}
function renderGroupMessages(){
  let day="",html="";const me=state.user?.id;
  for(const m of state.groupMessages){
    const d=friendlyDay(m.created_at);if(d!==day){html+=`<div class="date-separator"><span>${escapeHtml(d)}</span></div>`;day=d}
    const mine=m.sender_id===me,a=m.attachment;let attach="";
    if(a?.kind==="VOICE")attach=`<div class="voice-note"><button class="mini" onclick="loadVoice(${m.id},true,this)">▶ ${Math.round((a.duration_ms||0)/1000)}s</button></div>${a.transcript?`<div class="micro">Transcript: ${escapeHtml(a.transcript)}</div>`:""}`;
    else if(a?.media_id)attach=`<button class="mini" onclick="downloadGroupMedia(${m.id},'${escapeHtml((a.name||"file").replace(/'/g,""))}')">📎 ${escapeHtml(a.name||a.kind)}</button>`;
    html+=`<div class="msg ${mine?"mine":"theirs"}"><div class="micro">${escapeHtml(m.sender?.display_name||"Member")}</div><div>${escapeHtml(m.text)}</div>${attach}<div class="meta"><span>${timeOnly(m.created_at)}</span></div></div>`;
  }
  $("groupMessageList").innerHTML=html;setTimeout(()=>$("groupMessageList").scrollTop=$("groupMessageList").scrollHeight,20);
}
async function sendGroupMessage(){const text=$("groupMessageInput").value.trim();if(!text||!state.activeGroup)return;$("groupMessageInput").value="";await api(`/v24/groups/${state.activeGroup.id}/messages`,{method:"POST",body:JSON.stringify({text})});await openGroup(state.activeGroup.id)}
async function groupSuggestReply(){
  if(!state.activeGroup)return;const r=await api(`/v24/groups/${state.activeGroup.id}/suggest`,{method:"POST"});const el=$("groupSuggestionCard");
  el.classList.remove("hidden");el.innerHTML=`<strong>Q group suggestion</strong><p></p><div class="suggestion-actions"><button class="ghost" data-a="d">Discard</button><button class="ghost" data-a="e">Edit</button><button class="primary" data-a="s">Send</button></div>`;el.querySelector("p").textContent=r.reply;
  el.querySelector('[data-a="d"]').onclick=()=>el.classList.add("hidden");el.querySelector('[data-a="e"]').onclick=()=>{$("groupMessageInput").value=r.reply;el.classList.add("hidden")};el.querySelector('[data-a="s"]').onclick=async()=>{await api(`/v24/groups/${state.activeGroup.id}/messages`,{method:"POST",body:JSON.stringify({text:r.reply})});el.classList.add("hidden");await openGroup(state.activeGroup.id)};
}
async function groupCatchup(){try{const r=await api(`/v24/groups/${state.activeGroup.id}/summary`,{method:"POST"});openModal(`<h3>🧠 Catch me up</h3><p>${escapeHtml(r.summary||"")}</p>${(r.decisions||[]).map(x=>`<p>✓ ${escapeHtml(x)}</p>`).join("")}${(r.actions||[]).map(x=>`<p>→ ${escapeHtml(x)}</p>`).join("")}`)}catch(e){toast(e.message,true)}}
async function groupAsk(){openModal(`<h3>Q · ${escapeHtml(state.activeGroup.name)}</h3><textarea id="gqText" placeholder="What did everyone decide?"></textarea><button id="gqGo" class="primary full">Ask Q</button><div id="gqAns"></div>`);$("gqGo").onclick=async()=>{try{const r=await api(`/v24/groups/${state.activeGroup.id}/ask`,{method:"POST",body:JSON.stringify({question:$("gqText").value})});$("gqAns").innerHTML=`<div class="answer-box">${escapeHtml(r.answer)}</div>`}catch(e){$("gqAns").textContent=e.message}}}
async function groupSettings(){
  const g=state.activeGroup;
  openModal(`<h3>👥 ${escapeHtml(g.name)}</h3><label>AI mode<select id="gMode"><option>OFF</option><option>ASSIST</option><option>SUMMARY</option></select></label><label>Tone<input id="gTone" value="${escapeHtml(g.tone)}"></label>
  ${g.role==="ADMIN"?`<label class="upload">🖼 Change group photo<input id="gPhoto" type="file" accept="image/*" hidden></label><label>Add member<input id="gAdd" placeholder="Search username"></label><div id="gAddResults"></div>`:""}
  <button id="gSave" class="primary">Save</button><div class="group-member-list">${g.members.map(m=>`<div class="group-member"><span>${avatarHtml(m)} ${escapeHtml(m.display_name)} @${escapeHtml(m.username)}</span><span><strong>${m.role}</strong>${g.role==="ADMIN"&&m.id!==state.user.id&&m.id!==g.created_by?` <button class="mini" data-role="${m.id}">${m.role==="ADMIN"?"Make member":"Make admin"}</button><button class="mini" data-remove="${m.id}">Remove</button>`:""}</span></div>`).join("")}</div><p class="micro">AUTO replies are disabled for groups.</p>`);
  $("gMode").value=g.ai_mode;
  $("gSave").onclick=async()=>{await api(`/v24/groups/${g.id}/settings`,{method:"PUT",body:JSON.stringify({ai_mode:$("gMode").value,tone:$("gTone").value})});closeModal();await openGroup(g.id)};
  if(g.role==="ADMIN"){
    $("gPhoto").onchange=async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append("file",f);await api(`/v24/groups/${g.id}/photo`,{method:"POST",body:fd});closeModal();await openGroup(g.id);toast("Group photo updated")};
    $("gAdd").oninput=async e=>{const q=e.target.value.trim();if(q.length<2){$("gAddResults").innerHTML="";return}const rows=await api(`/users/search?q=${encodeURIComponent(q)}`);$("gAddResults").innerHTML=rows.filter(u=>!g.members.some(m=>m.id===u.id)).map(u=>`<div class="user-result"><span>${escapeHtml(u.display_name)} @${escapeHtml(u.username)}</span><button class="mini" data-add="${u.id}">Add</button></div>`).join("");qsa("[data-add]").forEach(b=>b.onclick=async()=>{await api(`/v24/groups/${g.id}/members`,{method:"POST",body:JSON.stringify({user_id:Number(b.dataset.add)})});closeModal();await openGroup(g.id);groupSettings()})};
    qsa("[data-role]").forEach(b=>b.onclick=async()=>{const uid=Number(b.dataset.role),m=g.members.find(x=>x.id===uid);await api(`/v24/groups/${g.id}/members/${uid}`,{method:"PUT",body:JSON.stringify({role:m.role==="ADMIN"?"MEMBER":"ADMIN"})});closeModal();await openGroup(g.id);groupSettings()});
    qsa("[data-remove]").forEach(b=>b.onclick=async()=>{if(!confirm("Remove this member?"))return;await api(`/v24/groups/${g.id}/members/${Number(b.dataset.remove)}`,{method:"DELETE"});closeModal();await openGroup(g.id);groupSettings()});
  }
}
window.openGroup=openGroup;

async function toggleVoice(target="direct"){
  if(state.mediaRecorder&&state.mediaRecorder.state==="recording"){state.mediaRecorder.stop();return}
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});state.voiceChunks=[];state.voiceStartedAt=Date.now();state.voiceTarget=target;
    const mime=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":"audio/webm";
    const rec=new MediaRecorder(stream,{mimeType:mime});state.mediaRecorder=rec;const btn=target==="group"?$("groupVoiceBtn"):$("voiceBtn");btn.classList.add("recording");btn.textContent="■";
    rec.ondataavailable=e=>{if(e.data.size)state.voiceChunks.push(e.data)};
    rec.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());btn.classList.remove("recording");btn.textContent="🎙";const blob=new Blob(state.voiceChunks,{type:mime}),fd=new FormData();fd.append("file",blob,"voice-note.webm");fd.append("duration_ms",String(Date.now()-state.voiceStartedAt));
      try{toast("Transcribing and sending voice note…");if(target==="group"&&state.activeGroup){await api(`/v24/groups/${state.activeGroup.id}/voice`,{method:"POST",body:fd});await openGroup(state.activeGroup.id)}else if(state.activeChat){await api(`/v24/chats/${state.activeChat.id}/voice`,{method:"POST",body:fd});await openChat(state.activeChat.id,false)}}catch(e){toast(e.message,true)}state.mediaRecorder=null};
    rec.start(250);
  }catch(e){toast("Microphone unavailable: "+e.message,true)}
}
async function loadVoice(id,isGroup,button){
  try{const url=isGroup?`/v24/group-media/${id}`:`/media/${id}`;const r=await fetch(url,{headers:authHeaders()});if(!r.ok)throw new Error(`Audio HTTP ${r.status}`);const blob=await r.blob(),src=URL.createObjectURL(blob),audio=document.createElement("audio");audio.controls=true;audio.src=src;
    const speed=document.createElement("button");speed.className="mini";speed.textContent="1×";speed.onclick=()=>{audio.playbackRate=audio.playbackRate===1?1.5:audio.playbackRate===1.5?2:1;speed.textContent=audio.playbackRate+"×"};button.replaceWith(audio);audio.parentElement?.appendChild(speed);audio.play().catch(()=>{})}
  catch(e){toast(e.message,true)}
}
async function voiceAI(id){try{const r=await api(`/v24/voice/${id}/ai`,{method:"POST"});openModal(`<h3>Q · Voice note</h3><p><strong>Transcript</strong></p><p>${escapeHtml(r.transcript)}</p><p><strong>Summary</strong></p><p>${escapeHtml(r.summary)}</p>${r.suggested_reply?`<div class="answer-box">${escapeHtml(r.suggested_reply)}</div><button id="vUse" class="primary">Use reply</button>`:""}`);if($("vUse"))$("vUse").onclick=()=>{$("messageInput").value=r.suggested_reply;closeModal();saveDraft(r.suggested_reply)}}catch(e){toast(e.message,true)}}
async function downloadGroupMedia(id,name){try{const r=await fetch(`/v24/group-media/${id}`,{headers:authHeaders()});if(!r.ok)throw new Error("Download failed");const b=await r.blob(),u=URL.createObjectURL(b),a=document.createElement("a");a.href=u;a.download=name||"group-file";a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}catch(e){toast(e.message,true)}}
window.downloadGroupMedia=downloadGroupMedia;window.loadVoice=loadVoice;window.voiceAI=voiceAI;

function startTone(kind){
  stopRing();
  try{
    const AC=window.AudioContext||window.webkitAudioContext,ctx=new AC();
    state.ringAudio={ctx,timer:null};
    const beep=()=>{const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=kind==="incoming"?740:440;g.gain.value=.035;o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.22)};
    beep();state.ringAudio.timer=setInterval(beep,kind==="incoming"?900:1600);
  }catch{}
}
function stopRing(){
  if(state.ringAudio){
    clearInterval(state.ringAudio.timer);
    try{state.ringAudio.ctx.close()}catch{}
    state.ringAudio=null;
  }
}
function cleanupRemoteAudio(){
  const host=$("remoteAudio");if(!host)return;
  [...host.querySelectorAll("audio,video")].forEach(el=>{
    try{el.pause()}catch{}
    try{el.srcObject=null}catch{}
    try{el.removeAttribute("src")}catch{}
    el.remove();
  });
  host.innerHTML="";
  clearVideoHost("remoteVideo");clearVideoHost("localVideo");
}
function startCallTimer(){
  clearInterval(state.callTimerHandle);state.callSeconds=0;$("callTimer").textContent="00:00";
  state.callTimerHandle=setInterval(()=>{$("callTimer").textContent=formatDuration(++state.callSeconds)},1000);
}
async function beginCall(chatId,person,callType="VOICE"){
  if(state.callPhase!=="idle"){
    toast("You already have a call in progress.",true);return;
  }
  state.callPhase="starting";state.callType=String(callType||"VOICE").toUpperCase();state.cameraFacing="user";
  try{
    const join=await api("/v24/calls/start",{method:"POST",body:JSON.stringify({chat_id:chatId,call_type:state.callType})});
    state.callType=String(join.call?.call_type||state.callType).toUpperCase();
    state.callPhase="ringing";prepareCallUi(person||state.activeChat?.other_user||{},"Ringing…");
    startTone("outgoing");
    await connectCallRoom(join,(person||state.activeChat?.other_user||{}).display_name||"LEMMIQ user",false);
    clearTimeout(state.callTimeoutHandle);
    state.callTimeoutHandle=setTimeout(()=>{
      if(state.callPhase==="ringing"){
        toast("No answer");
        endVoiceCall(true);
      }
    },45000);
  }catch(e){
    state.callPhase="idle";state.callId=null;cleanupRemoteAudio();stopRing();
    $("callOverlay")?.classList.add("hidden");
    toast(e.message||"Could not start call",true);
  }
}
async function beginVoiceCall(chatId,person){return beginCall(chatId,person,"VOICE")}
async function beginVideoCall(chatId,person){return beginCall(chatId,person,"VIDEO")}
async function startVoiceCall(){if(state.activeChat)await beginVoiceCall(state.activeChat.id,state.activeChat.other_user)}
async function startVideoCall(){if(state.activeChat)await beginVideoCall(state.activeChat.id,state.activeChat.other_user)}
function prepareCallUi(user,stateText="Ringing…"){
  const video=state.callType==="VIDEO";
  $("callState").textContent=stateText;$("callTimer").textContent="";
  $("callOverlay").classList.remove("hidden");
  $("callPerson").textContent=user?.display_name||"LEMMIQ user";
  $("callAvatar").innerHTML=user?.avatar_url?`<img src="${escapeHtml(user.avatar_url)}">`:escapeHtml(initials(user?.display_name||"LEMMIQ"));
  $("callEyebrow").textContent=video?"LEMMIQ VIDEO":"LEMMIQ VOICE";
  $("callFoot").textContent=`${video?"Video":"Voice"} call · LiveKit/WebRTC`;
  $("callVideoStage").classList.toggle("hidden",!video);
  $("callAvatar").classList.toggle("hidden",video);
  $("cameraCallBtn").classList.toggle("hidden",!video);
  $("flipCameraBtn").classList.toggle("hidden",!video);
}
async function loadCalls(){
  const rows=await api("/v24/calls");
  state.callHistory=rows;
  const el=$("callsList");if(!el)return;
  el.innerHTML=rows.length?rows.map(c=>{
    const status=(c.status||"").toUpperCase(),video=String(c.call_type||"VOICE").toUpperCase()==="VIDEO";
    const cls=status==="MISSED"?"missed":status==="RINGING"?"noanswer":"completed";
    const kind=video?"video call":"voice call";
    const label=status==="MISSED"?`Missed ${kind}`:status==="RINGING"?`No answer · ${kind}`:status==="DECLINED"?`Declined ${kind}`:(kind[0].toUpperCase()+kind.slice(1));
    const detail=c.duration_seconds?`${formatDuration(c.duration_seconds)} · ${new Date(c.started_at).toLocaleString()}`:new Date(c.started_at).toLocaleString();
    return `<div class="call-history-row">${avatarHtml(c.other_user)}
      <div class="body"><strong>${escapeHtml(c.other_user?.display_name||"LEMMIQ user")}</strong><small class="call-status ${cls}">${escapeHtml(label)} · ${escapeHtml(detail)}</small></div>
      <button class="ghost" data-callback="${c.chat_id}" data-call-type="${video?"VIDEO":"VOICE"}">${video?"🎥":"📞"} Call back</button></div>`;
  }).join(""):`<p class="micro">No LEMMIQ calls yet.</p>`;
  qsa("[data-callback]").forEach(b=>b.onclick=()=>{
    const c=rows.find(x=>x.chat_id===Number(b.dataset.callback));
    if(c)beginCall(c.chat_id,c.other_user,b.dataset.callType||c.call_type||"VOICE");
  });
}
function clearVideoHost(id){
  const host=$(id);if(!host)return;
  [...host.querySelectorAll("video")].forEach(el=>{try{el.pause()}catch{};try{el.srcObject=null}catch{};el.remove()});host.innerHTML="";
}
function attachVideoTrack(track,hostId,muted=false){
  const host=$(hostId);if(!host||!track)return;
  clearVideoHost(hostId);
  const el=track.attach();el.autoplay=true;el.playsInline=true;el.muted=muted;host.appendChild(el);
}
async function syncLocalVideoPreview(){
  if(state.callType!=="VIDEO"||!state.callRoom)return;
  const {Track}=LivekitClient;
  const pub=state.callRoom.localParticipant.getTrackPublication(Track.Source.Camera);
  const track=pub?.videoTrack||pub?.track;
  if(track)attachVideoTrack(track,"localVideo",true);else clearVideoHost("localVideo");
  $("cameraCallBtn").textContent=state.callRoom.localParticipant.isCameraEnabled?"📷":"🚫";
}
async function connectCallRoom(join,person,incoming){
  if(!window.LivekitClient)throw new Error("LiveKit client unavailable");
  if(state.callRoom){
    try{await state.callRoom.localParticipant?.setCameraEnabled(false)}catch{}
    try{await state.callRoom.localParticipant?.setMicrophoneEnabled(false)}catch{}
    try{state.callRoom.disconnect()}catch{}
    cleanupRemoteAudio();
  }
  state.callType=String(join.call?.call_type||state.callType||"VOICE").toUpperCase();
  const {Room,RoomEvent,Track}=LivekitClient,room=new Room();
  state.callRoom=room;state.callId=join.call.id;$("callPerson").textContent=person;
  room.on(RoomEvent.ParticipantConnected,()=>onRemoteAnswered());
  room.on(RoomEvent.TrackSubscribed,track=>{
    if(track.kind===Track.Kind.Audio){
      const el=track.attach();el.autoplay=true;el.dataset.callId=state.callId||"";$("remoteAudio").appendChild(el);
    }else if(track.kind===Track.Kind.Video){attachVideoTrack(track,"remoteVideo",false);onRemoteAnswered()}
  });
  if(RoomEvent.TrackUnsubscribed)room.on(RoomEvent.TrackUnsubscribed,track=>{try{track.detach().forEach?.(x=>x.remove())}catch{}});
  room.on(RoomEvent.Disconnected,()=>{
    if(state.callRoom!==room)return;
    if(state.callPhase==="connected"||state.callPhase==="connecting"){
      $("callState").textContent="Call ended";setTimeout(()=>endVoiceCall(false),300);
    }
  });
  await room.connect(join.ws_url,join.token);
  if(state.callRoom!==room){try{room.disconnect()}catch{};return}
  await room.localParticipant.setMicrophoneEnabled(true);
  if(state.callType==="VIDEO"){
    try{await room.localParticipant.setCameraEnabled(true);await syncLocalVideoPreview()}
    catch(e){toast("Camera unavailable. Continuing with camera off.",true)}
    const remote=[...(room.remoteParticipants?.values?.()||[])][0];
    const pub=remote?.getTrackPublication?.(Track.Source.Camera);const vt=pub?.videoTrack||pub?.track;if(vt)attachVideoTrack(vt,"remoteVideo",false);
  }
  if(incoming||room.remoteParticipants?.size>0)onRemoteAnswered();
}
function onRemoteAnswered(){
  if(state.callPhase==="connected")return;
  stopRing();clearTimeout(state.callTimeoutHandle);
  state.callPhase="connected";$("callState").textContent="Connected";$("callTimer").textContent="00:00";startCallTimer();
}
function showIncomingCall(p){
  if(state.callPhase!=="idle"){
    api(`/v24/calls/${p.call_id}/decline`,{method:"POST"}).catch(()=>{});toast("Incoming call declined because you are already in a call.");return;
  }
  state.callPhase="incoming";state.callId=p.call_id;state.callType=String(p.call_type||"VOICE").toUpperCase();
  const video=state.callType==="VIDEO";
  openModal(`<h3>${video?"🎥":"📞"} Incoming LEMMIQ ${video?"video":"voice"} call</h3><p><strong>${escapeHtml(p.caller_name||"LEMMIQ user")}</strong> is calling.</p><div class="suggestion-actions"><button id="incDecline" class="danger">Decline</button><button id="incAnswer" class="primary">${video?"Answer video":"Answer"}</button></div>`);
  startTone("incoming");
  $("incDecline").onclick=async()=>{
    const id=p.call_id;stopRing();state.callPhase="ending";
    try{await api(`/v24/calls/${id}/decline`,{method:"POST"})}catch(e){toast(e.message,true)}
    finally{state.callId=null;state.callPhase="idle";closeModal();cleanupRemoteAudio()}
  };
  $("incAnswer").onclick=async()=>{
    stopRing();
    try{
      const join=await api(`/v24/calls/${p.call_id}/join`,{method:"POST"});
      closeModal();state.callPhase="connecting";prepareCallUi({display_name:p.caller_name||"LEMMIQ user",avatar_url:p.caller_avatar_url},"Connecting…");
      await connectCallRoom(join,p.caller_name||"LEMMIQ user",true);
    }catch(e){state.callId=null;state.callPhase="idle";closeModal();$("callOverlay")?.classList.add("hidden");toast(e.message,true)}
  };
}
async function endVoiceCall(notify=true){
  if(state.callPhase==="idle")return;
  const id=state.callId,room=state.callRoom;state.callPhase="ending";
  stopRing();clearInterval(state.callTimerHandle);clearTimeout(state.callTimeoutHandle);state.callTimerHandle=null;state.callTimeoutHandle=null;
  try{await room?.localParticipant?.setCameraEnabled(false)}catch{}
  try{await room?.localParticipant?.setMicrophoneEnabled(false)}catch{}
  try{room?.removeAllListeners?.()}catch{};try{room?.disconnect()}catch{}
  cleanupRemoteAudio();state.callRoom=null;
  if(notify&&id)try{await api(`/v24/calls/${id}/end`,{method:"POST"})}catch{}
  state.callId=null;state.callPhase="idle";state.callSeconds=0;state.callType="VOICE";
  $("callOverlay").classList.add("hidden");
  if(state.activeChat)openChat(state.activeChat.id,false).catch(()=>{});
}
async function toggleCallMute(){
  if(!state.callRoom)return;
  const enabled=state.callRoom.localParticipant.isMicrophoneEnabled;
  await state.callRoom.localParticipant.setMicrophoneEnabled(!enabled);$("muteCallBtn").textContent=enabled?"🔇":"🎙";
}
async function toggleCallCamera(){
  if(!state.callRoom||state.callType!=="VIDEO")return;
  try{await state.callRoom.localParticipant.setCameraEnabled(!state.callRoom.localParticipant.isCameraEnabled);await syncLocalVideoPreview()}
  catch(e){toast(e.message||"Could not change camera",true)}
}
async function flipCallCamera(){
  if(!state.callRoom||state.callType!=="VIDEO")return;
  try{
    const {Track}=LivekitClient,pub=state.callRoom.localParticipant.getTrackPublication(Track.Source.Camera),track=pub?.videoTrack||pub?.track;
    if(!track)return toast("Turn the camera on first.");
    state.cameraFacing=state.cameraFacing==="user"?"environment":"user";
    await track.restartTrack({facingMode:state.cameraFacing});await syncLocalVideoPreview();
  }catch(e){toast(e.message||"Could not switch camera",true)}
}

async function loadStatuses(){
  state.statuses=await api("/v24/status");
  renderStatuses();
}
function latestByUser(rows){
  const m=new Map();
  [...rows].sort((a,b)=>new Date(b.created_at)-new Date(a.created_at)).forEach(s=>{if(!m.has(s.user.id))m.set(s.user.id,s)});
  return [...m.values()];
}
function statusStoryTile(s,mine=false){
  const ring=s.viewed&&!mine?" viewed":"";
  return `<button class="status-story" data-status-id="${s.id}">
    <span class="status-story-ring${ring}">${avatarHtml(s.user)}</span>
    <span class="status-story-name">${escapeHtml(mine?"My status":s.user.display_name)}</span>
  </button>`;
}
function renderStatuses(){
  const mine=state.statuses.filter(s=>s.user.id===state.user.id).sort((a,b)=>new Date(b.created_at)-new Date(a.created_at));
  const other=latestByUser(state.statuses.filter(s=>s.user.id!==state.user.id));
  state.statusStoryIds=[...(mine[0]?[mine[0].id]:[]),...other.map(s=>s.id)];

  $("statusStories").innerHTML=`<button class="status-story add-story" id="addStatusStory">
      <span class="status-story-ring add">${avatarHtml(state.user)}<b>＋</b></span>
      <span class="status-story-name">Add status</span>
    </button>`+
    (mine[0]?statusStoryTile(mine[0],true):"")+
    other.map(s=>statusStoryTile(s,false)).join("");

  $("myStatusList").innerHTML=mine.length?mine.map(s=>`<button class="status-list-row" data-status-id="${s.id}">
      <span class="status-list-avatar">${avatarHtml(s.user)}</span>
      <span class="body"><strong>${escapeHtml(s.text||s.kind)}</strong><small>${timeOnly(s.created_at)} · ${s.view_count||0} views</small></span>
      <span>›</span>
    </button>`).join(""):`<p class="micro">No active status.</p>`;

  $("statusList").innerHTML=other.length?other.map(s=>`<button class="status-list-row" data-status-id="${s.id}">
      <span class="status-story-ring mini${s.viewed?" viewed":""}">${avatarHtml(s.user)}</span>
      <span class="body"><strong>${escapeHtml(s.user.display_name)}</strong><small>${s.viewed?"Viewed":"New"} · ${timeOnly(s.created_at)}</small></span>
      <span>›</span>
    </button>`).join(""):`<p class="micro">No recent updates.</p>`;

  $("addStatusStory").onclick=showStatusCreator;
  qsa("[data-status-id]").forEach(el=>el.onclick=()=>openStatus(Number(el.dataset.statusId)));
}
function showStatusCreator(){
  openModal(`<h3>Add status</h3><textarea id="stText" maxlength="1500" placeholder="Type a status…"></textarea>
    <p class="micro">Status disappears automatically after 24 hours.</p>
    <div class="suggestion-actions"><button id="stCancel" class="ghost">Cancel</button><button id="stPost" class="primary">Post text</button></div>`);
  $("stCancel").onclick=closeModal;
  $("stPost").onclick=async()=>{
    const text=$("stText").value.trim();if(!text)return;
    await api("/v24/status/text",{method:"POST",body:JSON.stringify({text})});
    closeModal();await loadStatuses();
  };
}
async function addTextStatus(){showStatusCreator()}
async function uploadStatusMedia(file){
  if(!file)return;
  const fd=new FormData();fd.append("file",file);fd.append("caption","");
  try{toast("Posting status…");await api("/v24/status/media",{method:"POST",body:fd});await loadStatuses();toast("Status posted")}
  catch(e){toast(e.message,true)}
}
function closeStatusViewer(){
  if(state.statusBlobUrl){URL.revokeObjectURL(state.statusBlobUrl);state.statusBlobUrl=null}
  $("statusViewer").classList.add("hidden");$("statusViewer").setAttribute("aria-hidden","true");
  $("statusViewerBody").innerHTML="";state.statusIndex=-1;
}
async function showStatusAt(index){
  if(!state.statusStoryIds.length)return;
  const i=Math.max(0,Math.min(index,state.statusStoryIds.length-1));
  const id=state.statusStoryIds[i];
  let s=state.statuses.find(x=>x.id===id);if(!s)return;
  state.statusIndex=i;
  try{s=await api(`/v24/status/${id}/view`,{method:"POST"});state.statuses=state.statuses.map(x=>x.id===id?s:x)}
  catch(e){toast(e.message,true);return}
  renderStatuses();

  if(state.statusBlobUrl){URL.revokeObjectURL(state.statusBlobUrl);state.statusBlobUrl=null}
  $("statusViewer").classList.remove("hidden");$("statusViewer").setAttribute("aria-hidden","false");
  $("statusViewerAvatar").innerHTML=s.user.avatar_url?`<img src="${escapeHtml(s.user.avatar_url)}" alt="">`:escapeHtml(initials(s.user.display_name));
  $("statusViewerName").textContent=s.user.display_name;
  $("statusViewerTime").textContent=timeOnly(s.created_at);
  $("statusDeleteBtn").classList.toggle("hidden",s.user.id!==state.user.id);
  $("statusReplyBtn").classList.toggle("hidden",s.user.id===state.user.id);
  $("statusPrevBtn").disabled=i===0;$("statusNextBtn").disabled=i===state.statusStoryIds.length-1;
  $("statusProgressBar").style.width="100%";

  let body="";
  if(s.media_url){
    try{
      const r=await fetch(s.media_url,{headers:authHeaders()});
      if(!r.ok)throw new Error("Could not load status media");
      const blob=await r.blob();state.statusBlobUrl=URL.createObjectURL(blob);
      body=s.kind==="VIDEO"
        ?`<video class="status-full-media" src="${state.statusBlobUrl}" controls autoplay playsinline></video>`
        :`<img class="status-full-media" src="${state.statusBlobUrl}" alt="Status">`;
    }catch(e){body=`<p class="status-error">${escapeHtml(e.message)}</p>`}
  }else{
    body=`<div class="status-text-story">${escapeHtml(s.text||"Status")}</div>`;
  }
  if(s.media_url&&s.text)body+=`<div class="status-caption">${escapeHtml(s.text)}</div>`;
  $("statusViewerBody").innerHTML=body;

  $("statusDeleteBtn").onclick=async()=>{await api(`/v24/status/${s.id}`,{method:"DELETE"});closeStatusViewer();await loadStatuses()};
  $("statusReplyBtn").onclick=async()=>{
    const c=await api("/chats/direct",{method:"POST",body:JSON.stringify({user_id:s.user.id})});
    closeStatusViewer();setView("chats");await loadChats();await openChat(c.id);
    $("messageInput").value=`Replied to your status: ${s.text||s.kind}`;await saveDraft($("messageInput").value);
  };
}
async function openStatus(id){
  let index=state.statusStoryIds.indexOf(id);
  if(index<0){state.statusStoryIds=[id,...state.statusStoryIds.filter(x=>x!==id)];index=0}
  await showStatusAt(index);
}
window.openStatus=openStatus;

async function runTrust(text,refresh=false){
  $("trustResult").classList.remove("hidden");$("trustResult").innerHTML="<h3>🛡 Checking…</h3><p>Analysing scam signals and available evidence.</p>";
  try{const r=await api(`/trust/check${refresh?"?refresh=true":""}`,{method:"POST",body:JSON.stringify({text})});renderTrustResult(r);await loadTrustHistory();setView("trust")}
  catch(e){$("trustResult").innerHTML=`<h3>Could not complete check</h3><p>${escapeHtml(e.message)}</p>`}
}
function renderTrustResult(r){
  const sources=(r.sources||[]).map(s=>`<a class="source" target="_blank" rel="noopener" href="${escapeHtml(s.url)}">↗ ${escapeHtml(s.title||s.url)}</a>`).join("");
  $("trustResult").innerHTML=`<span class="status">${escapeHtml(r.status||"UNVERIFIED")}</span><h3>${escapeHtml(r.summary||"Trust result")}</h3><p><strong>Evidence confidence: ${Number(r.confidence||0)}%</strong></p>${(r.reasons||[]).map(x=>`<p>• ${escapeHtml(x)}</p>`).join("")}${sources}${r.advice?`<p><strong>Advice:</strong> ${escapeHtml(r.advice)}</p>`:""}<p class="micro">${r.checked_at?`Checked ${new Date(r.checked_at).toLocaleString()} · `:""}${r.cached?"Saved result reused. ":""}Confidence reflects evidence strength, not certainty.</p>${r.checked_text?`<button id="refreshTrustResult" class="ghost">↻ Refresh check</button>`:""}`;
  if($("refreshTrustResult"))$("refreshTrustResult").onclick=()=>runTrust(r.checked_text,true);
}
async function loadTrustHistory(){
  const q=($("trustHistorySearch")?.value||"").trim();state.trustHistory=await api(`/trust/history${q?`?q=${encodeURIComponent(q)}`:""}`);
  $("trustHistoryList").innerHTML=state.trustHistory.length?state.trustHistory.map(h=>`<div class="history-item"><strong>${escapeHtml(h.status.replaceAll("_"," "))}</strong><p>${escapeHtml(h.checked_text).slice(0,240)}</p><p class="micro">${new Date(h.checked_at).toLocaleString()} · ${h.confidence}% evidence strength</p><button class="mini" onclick="openTrustHistory(${h.id})">Open</button><button class="mini" onclick="deleteTrustHistory(${h.id})">Delete</button></div>`).join(""):`<p class="micro">No saved Trust checks yet.</p>`;
}
function openTrustHistory(id){const h=state.trustHistory.find(x=>x.id===id);if(h)renderTrustResult(h)}
async function deleteTrustHistory(id){await api(`/trust/history/${id}`,{method:"DELETE"});await loadTrustHistory()}
window.openTrustHistory=openTrustHistory;window.deleteTrustHistory=deleteTrustHistory;

function runQStarter(prompt){
  setView("agent");
  $("agentQuestion").value=prompt;
  setTimeout(()=>askAgent(),30);
}
function askQFromChatSearch(){
  const q=$("chatFilter").value.trim();
  if(!q){setView("agent");$("agentQuestion").focus();return}
  runQStarter(q);
}

async function loadAgentV24(){
  try{
    const [home,vision,coord,social]=await Promise.all([
      api("/v27/q/home"),
      api("/v27/vision"),
      api("/v27/q/coordination"),
      api("/v24/social-iq/brief").catch(()=>({count:0,promises:0,follow_ups:0,items:[]}))
    ]);
    state.qHome=home;
    state.vision=vision;
    state.qCoordination=coord;
    state.socialBrief=social;
    renderQHome();
  }catch(e){toast(e.message,true)}
}
function renderQHome(){
  const h=state.qHome||{today:{},memory:{},q_to_q:{}};
  const t=h.today||{},m=h.memory||{},qq=h.q_to_q||{};
  if($("qTodayTitle")){
    const bits=[];
    if(t.needs_reply_count)bits.push(`${t.needs_reply_count} need reply`);
    if(t.follow_ups)bits.push(`${t.follow_ups} follow-up${t.follow_ups===1?"":"s"}`);
    if(t.promises)bits.push(`${t.promises} promise${t.promises===1?"":"s"}`);
    $("qTodayTitle").textContent=bits.length?bits.join(" · "):"You're caught up ✓";
    $("qTodayMeta").textContent=t.summary||"";
  }
  if($("qToQSummary"))$("qToQSummary").textContent=(qq.pending_count||0)?`${qq.pending_count} active plan${qq.pending_count===1?"":"s"}`:"No active plans";
  if($("qMemorySummary"))$("qMemorySummary").textContent=`${m.count||0} conversation memories`;
  const vc=m.vision_count||state.vision.length||0;
  if($("qVisionSummary"))$("qVisionSummary").textContent=`${vc} saved scan${vc===1?"":"s"}`;
  renderQPlans();
  renderVisionRecent();
}
function renderQPlans(){
  const card=$("qToQPlansCard"),host=$("qToQPlans");
  if(!card||!host)return;
  const groups=new Map();
  for(const r of (state.qCoordination?.outbox||[])){
    if(!["PENDING","RESPONDED"].includes(r.status))continue;
    if(!groups.has(r.request_key))groups.set(r.request_key,[]);
    groups.get(r.request_key).push(r);
  }
  const rows=[...groups.values()];
  card.classList.toggle("hidden",!rows.length);
  host.innerHTML=rows.map(g=>{
    const first=g[0];
    const names=[...new Set(g.map(x=>x.target?.display_name).filter(Boolean))].join(", ");
    const replied=g.filter(x=>x.status==="RESPONDED").length;
    const humanStatus=replied===0?`Waiting for ${names||"response"}`:replied<g.length?`${replied} replied · waiting for ${g.length-replied}`:"All responses received";
    return `<div class="q27-plan"><div><strong>${escapeHtml(first.prompt)}</strong><small>${escapeHtml(humanStatus)}</small></div><button class="mini" onclick="cancelQPlan('${escapeHtml(first.request_key)}')">Cancel</button></div>`;
  }).join("");
}
async function cancelQPlan(key){
  try{
    await api(`/v27/q/coordination/${encodeURIComponent(key)}`,{method:"DELETE"});
    await loadAgentV24();
    toast("Q-to-Q plan cancelled");
  }catch(e){toast(e.message,true)}
}
window.cancelQPlan=cancelQPlan;

function renderVisionRecent(){
  const card=$("qVisionRecentCard"),host=$("qVisionRecent");
  if(!card||!host)return;
  const rows=(state.vision||[]).slice(0,6);
  card.classList.toggle("hidden",!rows.length);
  host.innerHTML=rows.map(v=>`<button class="vision-row" onclick="openVisionMemory(${v.id})"><span>${escapeHtml(v.category||"PHOTO")}</span><strong>${escapeHtml(v.title||"Vision scan")}</strong><small>${escapeHtml(v.summary||"")}</small></button>`).join("");
}
async function uploadQVision(file){
  if(!file)return;
  const fd=new FormData();
  fd.append("file",file);
  fd.append("question",($("agentQuestion")?.value||"").trim()||"What is in this image? Give me the useful details.");
  fd.append("save","true");
  try{
    toast("Q Vision is analysing…");
    const v=await api("/v27/vision",{method:"POST",body:fd});
    await loadAgentV24();
    await openVisionMemory(v.id);
  }catch(e){toast(e.message,true)}
}
async function openVisionMemory(id){
  const v=(state.vision||[]).find(x=>x.id===Number(id))||await api(`/v27/vision/${id}`);
  if(state.visionBlobUrl){URL.revokeObjectURL(state.visionBlobUrl);state.visionBlobUrl=null}
  let imageHtml="";
  try{
    const r=await fetch(`/v27/vision/${v.id}/media`,{headers:authHeaders()});
    if(r.ok){
      const blob=await r.blob();
      state.visionBlobUrl=URL.createObjectURL(blob);
      imageHtml=`<img class="vision-preview" src="${state.visionBlobUrl}" alt="Q Vision image">`;
    }
  }catch{}
  const history=(v.history||[]).slice(-6).map(h=>`<p class="micro"><strong>${h.role==="q"?"Q":"You"}:</strong> ${escapeHtml(h.text)}</p>`).join("");
  openModal(`<h3>📷 ${escapeHtml(v.title||"Q Vision")}</h3>${imageHtml}<span class="tag">${escapeHtml(v.category||"OTHER")}</span><p>${escapeHtml(v.summary||"")}</p>${v.extracted_text?`<h4>Extracted text</h4><p class="vision-extracted">${escapeHtml(v.extracted_text)}</p>`:""}${history?`<h4>Conversation</h4>${history}`:""}<textarea id="visionFollow" placeholder="Ask another question about this image…"></textarea><div class="suggestion-actions"><button id="visionDelete" class="danger">Delete</button><button id="visionAsk" class="primary">Ask Q Vision</button></div>`);
  $("visionAsk").onclick=async()=>{
    const q=$("visionFollow").value.trim();
    if(!q)return;
    try{
      $("visionAsk").disabled=true;
      $("visionAsk").textContent="Analysing…";
      const updated=await api(`/v27/vision/${v.id}/ask`,{method:"POST",body:JSON.stringify({question:q})});
      state.vision=state.vision.map(x=>x.id===updated.id?updated:x);
      closeModal();
      await openVisionMemory(updated.id);
    }catch(e){toast(e.message,true)}
  };
  $("visionDelete").onclick=async()=>{
    if(confirm("Delete this Vision memory?")){
      await api(`/v27/vision/${v.id}`,{method:"DELETE"});
      closeModal();
      await loadAgentV24();
    }
  };
}
window.openVisionMemory=openVisionMemory;

function showVisionHistory(){
  const rows=state.vision||[];
  openModal(`<h3>Q Vision memory</h3><p class="micro">Saved scans can be reopened and questioned again without rescanning.</p><div class="vision-list">${rows.length?rows.map(v=>`<button class="vision-row" onclick="closeModal();openVisionMemory(${v.id})"><span>${escapeHtml(v.category||"PHOTO")}</span><strong>${escapeHtml(v.title||"Vision scan")}</strong><small>${escapeHtml(v.summary||"")}</small></button>`).join(""):"<p>No saved scans yet.</p>"}</div>`);
}

async function startQToQ(){
  const selected=new Map();
  openModal("<h3>Q-to-Q coordination</h3><p class='micro'>Only use this for shared plans, availability or polls. Private Q memory is not shared.</p><div id='qtqSelected' class='qtq-selected'></div><input id='qtqSearch' placeholder='Search and add contacts'><p class='micro'>Select a contact, then search again to add more.</p><div id='qtqUsers' class='modal-results'></div><textarea id='qtqPrompt' placeholder='What should Q coordinate?'></textarea><textarea id='qtqOptions' placeholder='Options / times — one per line'></textarea><button id='qtqSend' class='primary full'>Send Q request</button>");
  const renderSelected=()=>{
    const el=$("qtqSelected");
    if(!el)return;
    if(!selected.size){el.innerHTML="<p class='micro'>No contacts selected yet.</p>";return}
    el.innerHTML=`<div class="qtq-selected-head"><strong>${selected.size} selected</strong></div>${[...selected.values()].map(u=>`<span class="qtq-chip">${escapeHtml(u.display_name)} @${escapeHtml(u.username)} <button type="button" data-remove-uid="${u.id}" aria-label="Remove">×</button></span>`).join("")}`;
    qsa("#qtqSelected [data-remove-uid]").forEach(b=>b.onclick=()=>{selected.delete(Number(b.dataset.removeUid));renderSelected()});
  };
  renderSelected();
  $("qtqSearch").oninput=async()=>{
    const q=$("qtqSearch").value.trim();
    if(q.length<2){$("qtqUsers").innerHTML="";return}
    try{
      const users=await api(`/users/search?q=${encodeURIComponent(q)}`);
      $("qtqUsers").innerHTML=users.map(u=>`<label class="user-result"><span>${escapeHtml(u.display_name)} @${escapeHtml(u.username)}</span><input type="checkbox" data-uid="${u.id}" ${selected.has(u.id)?"checked":""}></label>`).join("");
      qsa("#qtqUsers input[data-uid]").forEach(x=>x.onchange=()=>{
        const id=Number(x.dataset.uid),u=users.find(v=>v.id===id);
        if(x.checked&&u){selected.set(id,u);$("qtqSearch").value="";$("qtqUsers").innerHTML=""}
        else selected.delete(id);
        renderSelected();
      });
    }catch(e){toast(e.message,true)}
  };
  $("qtqSend").onclick=async()=>{
    const prompt=$("qtqPrompt").value.trim();
    const options=$("qtqOptions").value.split("\n").map(x=>x.trim()).filter(Boolean);
    if(!selected.size||!prompt)return toast("Choose at least one contact and enter a shared plan.",true);
    try{
      await api("/v27/q/coordination",{method:"POST",body:JSON.stringify({target_user_ids:[...selected.keys()],kind:options.length?"AVAILABILITY":"PLAN",prompt,options})});
      closeModal();
      await loadAgentV24();
      toast(`Q-to-Q request sent to ${selected.size} contact${selected.size===1?"":"s"}`);
    }catch(e){toast(e.message,true)}
  };
}

async function askAgent(){
  const q=$("agentQuestion").value.trim();
  if(!q)return;
  $("agentAnswer").innerHTML="<div class='answer-box'>Q is thinking…</div>";
  try{
    const r=await api("/agent/ask",{method:"POST",body:JSON.stringify({question:q,days:30,external_context:[]})});
    $("agentAnswer").innerHTML=`<div class="answer-box"><strong>Q</strong><p>${escapeHtml(r.answer||"")}</p>${(r.references||[]).slice(0,3).map(x=>`<p class="micro">• ${escapeHtml(x.contact||"")}: ${escapeHtml(x.text||"")}</p>`).join("")}</div>`;
  }catch(e){
    $("agentAnswer").innerHTML=`<div class="answer-box">${escapeHtml(e.message)}</div>`;
  }
}
async function scanSocial(){
  try{
    toast("Refreshing Q memory…");
    await api("/v24/social-iq/scan",{method:"POST"});
    await loadAgentV24();
    toast("Q memory refreshed");
  }catch(e){toast(e.message,true)}
}

async function uploadProfilePhoto(file){if(!file)return;const fd=new FormData();fd.append("file",file);try{const u=await api("/v24/profile/avatar",{method:"POST",body:fd});state.user={...state.user,...u};localStorage.setItem("lemmiq_user",JSON.stringify(state.user));renderMeAvatar();await loadChats();toast("Profile photo updated")}catch(e){toast(e.message,true)}}
async function removeProfilePhoto(){try{const u=await api("/v24/profile/avatar",{method:"DELETE"});state.user={...state.user,...u};localStorage.setItem("lemmiq_user",JSON.stringify(state.user));renderMeAvatar();await loadChats();toast("Profile photo removed")}catch(e){toast(e.message,true)}}

document.addEventListener("DOMContentLoaded",()=>{
  $("androidDownloadPublicBtn").onclick=installAndroidApp;
  $("loginTab").onclick=()=>{$("loginTab").classList.add("active");$("registerTab").classList.remove("active");$("loginForm").classList.remove("hidden");$("registerForm").classList.add("hidden")};
  $("registerTab").onclick=()=>{$("registerTab").classList.add("active");$("loginTab").classList.remove("active");$("registerForm").classList.remove("hidden");$("loginForm").classList.add("hidden")};
  $("loginForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/login",{method:"POST",body:JSON.stringify({username:$("loginUsername").value,password:$("loginPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};
  $("registerForm").onsubmit=async e=>{e.preventDefault();try{
    const referral=($("regReferral")?.value||"").trim();
    const payload={display_name:$("regName").value,username:$("regUsername").value,password:$("regPassword").value};
    if(referral)payload.referral_code=referral;
    const r=await api("/register",{method:"POST",body:JSON.stringify(payload)});
    saveSession(r);showApp()
  }catch(err){toast(err.message,true)}};

  qsa("#nav button").forEach(b=>b.onclick=()=>{
    const view=b.dataset.view;
    if(view==="chats"){
      chatsHome(false);
      setView("chats");
    }else{
      setView(view);
    }
    if(location.hash!==`#${view}`) history.pushState({view},"",`#${view}`);
  });
  qsa("[data-more-view]").forEach(b=>b.onclick=()=>{
    if(b.id==="qAdminMoreCard") return;
    const view=b.dataset.moreView;
    setView(view);
    if(location.hash!==`#${view}`) history.pushState({view},"",`#${view}`);
  });
  qsa("[data-q-prompt]").forEach(b=>b.onclick=()=>runQStarter(b.dataset.qPrompt));
  $("moreAndroidDownloadBtn").onclick=installAndroidApp;
  $("refreshCallsBtn").onclick=loadCalls;
  $("refreshBtn").onclick=refreshCurrent;$("logoutBtn").onclick=logout;
  if($("profileMenuBtn"))$("profileMenuBtn").onclick=()=>setView("more");
  if($("globalQOrb"))$("globalQOrb").onclick=()=>setView("agent");

  $("newChatBtn").onclick=showNewChat;$("newGroupBtn").onclick=showNewGroup;$("chatFilter").oninput=renderChats;$("chatAskQBtn").onclick=askQFromChatSearch;
  qsa("[data-chat-filter]").forEach(b=>b.onclick=()=>{state.chatFilterMode=b.dataset.chatFilter;qsa("[data-chat-filter]").forEach(x=>x.classList.toggle("active",x===b));renderChats()});

  $("sendBtn").onclick=sendMessage;$("suggestBtn").onclick=suggestReply;$("assistBarBtn").onclick=suggestReply;
  $("messageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}});
  $("messageInput").addEventListener("input",()=>{clearTimeout(window.__draftTimer);window.__draftTimer=setTimeout(()=>saveDraft($("messageInput").value),500)});
  $("fileInput").onchange=e=>{uploadAttachment(e.target.files[0]);e.target.value=""};
  $("voiceBtn").onclick=()=>toggleVoice("direct");$("callBtn").onclick=startVoiceCall;$("videoCallBtn").onclick=startVideoCall;$("chatSearchBtn").onclick=openChatSearch;$("chatMoreBtn").onclick=openChatMore;
  $("chatAiBtn").onclick=personalChatSettings;$("summaryBtn").onclick=chatSummary;$("businessChatBtn").onclick=businessChatSettings;

  $("groupVoiceBtn").onclick=()=>toggleVoice("group");$("groupSendBtn").onclick=sendGroupMessage;
  $("groupMessageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendGroupMessage()}});
  $("groupFileInput").onchange=async e=>{const f=e.target.files[0];if(f&&state.activeGroup){const fd=new FormData();fd.append("file",f);try{await api(`/v24/groups/${state.activeGroup.id}/attachments`,{method:"POST",body:fd});await openGroup(state.activeGroup.id)}catch(err){toast(err.message,true)}}e.target.value=""};
  $("groupSuggestBtn").onclick=groupSuggestReply;$("groupSuggestTop").onclick=groupSuggestReply;$("groupCatchupBtn").onclick=groupCatchup;$("groupQBtn").onclick=groupAsk;$("groupSettingsBtn").onclick=groupSettings;

  $("muteCallBtn").onclick=toggleCallMute;$("cameraCallBtn").onclick=toggleCallCamera;$("flipCameraBtn").onclick=flipCallCamera;$("endCallBtn").onclick=()=>endVoiceCall(true);$("speakerCallBtn").onclick=()=>toast("Browser speaker routing follows your device/browser audio output.");

  $("addTextStatusBtn").onclick=addTextStatus;
  $("statusMediaInput").onchange=e=>{uploadStatusMedia(e.target.files[0]);e.target.value=""};
  $("statusRefreshBtn").onclick=loadStatuses;
  $("statusCloseBtn").onclick=closeStatusViewer;
  $("statusPrevBtn").onclick=()=>{if(state.statusIndex>0)showStatusAt(state.statusIndex-1)};
  $("statusNextBtn").onclick=()=>{if(state.statusIndex<state.statusStoryIds.length-1)showStatusAt(state.statusIndex+1)};
  $("statusViewer").addEventListener("click",e=>{if(e.target===$("statusViewer"))closeStatusViewer()});

  $("askAgentBtn").onclick=askAgent;
  $("scanSocialBtn").onclick=scanSocial;
  $("qVisionInput").onchange=e=>{uploadQVision(e.target.files[0]);e.target.value=""};
  $("qVisionCameraInput").onchange=e=>{uploadQVision(e.target.files[0]);e.target.value=""};
  qsa(".q27-vision-inline").forEach(x=>x.onchange=e=>{uploadQVision(e.target.files[0]);e.target.value=""});
  $("qVisionHistoryBtn").onclick=showVisionHistory;
  $("qVisionHistoryBtn2").onclick=showVisionHistory;
  $("qToQStartBtn").onclick=startQToQ;
  $("trustBtn").onclick=()=>{const t=$("trustText").value.trim();if(t)runTrust(t)};
  $("trustHistorySearch").oninput=()=>{clearTimeout(window.__trustSearch);window.__trustSearch=setTimeout(loadTrustHistory,250)};
  $("clearTrustHistoryBtn").onclick=async()=>{if(confirm("Clear all saved Trust checks?")){await api("/trust/history",{method:"DELETE"});await loadTrustHistory()}};

  $("resetMoneyBtn").onclick=()=>resetInsights("MONEY");$("resetActivityBtn").onclick=()=>resetInsights("ACTIVITY");$("resetAllInsightsBtn").onclick=()=>resetInsights("ALL");
  $("saveBizBtn").onclick=saveBusiness;$("addKbBtn").onclick=addKnowledge;$("bizDocInput").onchange=e=>{uploadBizDoc(e.target.files[0]);e.target.value=""};

  $("profilePhotoInput").onchange=e=>{uploadProfilePhoto(e.target.files[0]);e.target.value=""};$("removeProfilePhotoBtn").onclick=removeProfilePhoto;

  $("closeModal").onclick=closeModal;$("modal").addEventListener("click",e=>{if(e.target===$("modal"))closeModal()});
  $("installBtn").onclick=installHelp;$("installBtn2").onclick=installHelp;$("androidDownloadBtn").onclick=installAndroidApp;$("androidBtnTop").onclick=installAndroidApp;
  window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();state.installPrompt=e;$("installBtn").classList.remove("hidden")});
  if("serviceWorker" in navigator)navigator.serviceWorker.register("/web/sw.js?v=2.10.8.3").catch(()=>{});

  window.addEventListener("popstate",async e=>{
    const s=e.state||{};
    if(s.chatId){setView("chats");await loadChats();await openChat(Number(s.chatId),false);return}
    if(s.groupId){setView("chats");await loadChats();await openGroup(Number(s.groupId),false);return}
    if(s.qThread){setView("chats");await loadChats();await openQThread();return}

    const hashView=(location.hash||"").replace(/^#/,"");
    const nextView=s.view || (document.getElementById(`view-${hashView}`)?hashView:"chats");
    if(nextView==="chats") chatsHome(false);
    setView(nextView);
  });
  if(!history.state){
    const hashView=(location.hash||"").replace(/^#/,"");
    const initialView=document.getElementById(`view-${hashView}`)?hashView:"chats";
    history.replaceState({view:initialView},"",`#${initialView}`);
  }

  loadAppConfig();
  if(state.token&&state.user)showApp();
});

window.openChat=openChat;
window.openGroup=openGroup;
window.openQThread=openQThread;
window.loadQThread=loadQThread;
window.renderQThread=renderQThread;
window.renderChats=renderChats;
window.loadChats=loadChats;
window.setView=setView;
window.askAgent=askAgent;
window.checkMessage=checkMessage;
