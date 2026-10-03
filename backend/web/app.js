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
  trustHistory: [],
  socialBrief: null,
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
  ringAudio: null,
  appConfig: {android_download_url:"", android_play_url:"", web_install_enabled:true}
};

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
  if(!r.ok) throw new Error(body?.detail || body?.message || body || `HTTP ${r.status}`);
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
  connectSocket(); refreshCurrent();
}
function setView(name){
  qsa(".view").forEach(v=>v.classList.remove("active"));
  const target = $(`view-${name}`);
  if(!target) return;
  target.classList.add("active");
  const secondaryViews = new Set(["updates","activity","money","me"]);
  qsa("#nav button").forEach(b=>b.classList.toggle(
    "active",
    b.dataset.view===name || (secondaryViews.has(name) && b.dataset.view==="more")
  ));
  const meta={
    chats:["Chats","Search, filter, message, group chat and call."],
    updates:["Updates","LEMMIQ Status — text, photo and video for 24 hours."],
    agent:["Q Agent","Personal communication intelligence and Social IQ memory."],
    trust:["LEMMIQ Trust","Fact / Scam Check with saved history."],
    business:["Business Agent","Teach LEMMIQ how your business operates."],
    activity:["Activity","Detected phone activity synced by your Android companion."],
    money:["Money","Review and correct notification-derived payment insights."],
    me:["Me","Your profile photo, account and LEMMIQ access."],
    more:["More","Profile, updates, activity, money and app installation."]
  }[name]||["LEMMIQ","Messaging with social IQ."];
  $("pageTitle").textContent=meta[0];$("pageSub").textContent=meta[1];
  refreshView(name);
}
async function refreshView(name){
  try{
    if(name==="chats") await loadChats();
    if(name==="updates") await loadStatuses();
    if(name==="agent") await loadAgentV24();
    if(name==="trust") await loadTrustHistory();
    if(name==="business") await loadBusiness();
    if(name==="activity") await loadActivity();
    if(name==="money") await loadMoney();
    if(name==="me") renderMeAvatar();
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
        if(state.activeGroup&&p.group_id===state.activeGroup.id)await openGroup(state.activeGroup.id);
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

async function loadChats(){
  const [chats,groups]=await Promise.all([api("/chats"),api("/v24/groups")]);
  state.chats=chats;state.groups=groups;renderChats();
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
  el.innerHTML=rows.length?rows.map(r=>{
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
  }).join(""):`<div class="empty-state"><p>No matching conversations.</p></div>`;
}
async function openChat(cid,mark=true){
  let chat=state.chats.find(x=>x.id===cid);
  if(!chat){await loadChats();chat=state.chats.find(x=>x.id===cid)}
  if(!chat)return;
  state.activeGroup=null;state.activeChat=chat;state.replyTo=null;
  const [messages,calls]=await Promise.all([api(`/chats/${cid}/messages`),api(`/v24/chats/${cid}/calls`).catch(()=>[])]);
  state.messages=messages;state.chatCalls=calls;
  if(mark)api(`/chats/${cid}/read`,{method:"POST"}).catch(()=>{});
  $("emptyChat").classList.add("hidden");$("activeGroup").classList.add("hidden");$("activeChat").classList.remove("hidden");
  $("chatName").textContent=chat.other_user.display_name;
  $("chatMeta").textContent=`@${chat.other_user.username} · ${chat.category} · AI ${chat.ai_mode}`;
  $("chatAvatar").innerHTML=chat.other_user.avatar_url?`<img src="${escapeHtml(chat.other_user.avatar_url)}" alt="">`:escapeHtml(initials(chat.other_user.display_name));
  $("assistBar").classList.toggle("hidden",chat.ai_mode!=="ASSIST");
  $("messageInput").value=chat.draft_text||"";
  clearReplyPreview();
  document.querySelector(".chat-layout").classList.add("open-chat");
  renderMessages();renderChats();
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
      const label=c.status==="MISSED"?"Missed voice call":c.status==="DECLINED"?"Voice call · declined":c.status==="RINGING"?"Voice call · no answer":"Voice call";
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
  const current=document.querySelector(".view.active")?.id?.replace("view-","");
  if(current==="money")await loadMoney(); else if(current==="activity")await loadActivity();
}

function openModal(html){$("modalContent").innerHTML=html;$("modal").showModal()}
function closeModal(){$("modal").close()}

async function loadAppConfig(){
  try{
    state.appConfig = await api("/app-config");
    const hasNative = !!(state.appConfig.android_play_url || state.appConfig.android_download_url);
    $("androidBtnTop")?.classList.toggle("hidden", !hasNative);
    if($("androidInstallHint")){
      $("androidInstallHint").textContent = hasNative
        ? "Choose the native Android app for WhatsApp/SMS notification intelligence and stronger background features. The web app is the universal browser/PWA version."
        : "The Android app download is not available yet. You can still use or install the LEMMIQ web app.";
    }
    if($("moreAndroidStatus")){
      $("moreAndroidStatus").textContent = hasNative
        ? "Android download is available"
        : "Android download is not published yet";
    }
  }catch(e){
    console.warn("App config unavailable", e);
  }
}

function installAndroidApp(){
  const url = state.appConfig.android_play_url || state.appConfig.android_download_url;
  if(url){
    window.location.href = url;
    return;
  }
  openModal(`<h3>📱 Android app</h3>
    <p>The native Android download link has not been configured yet.</p>
    <p>For your own phone right now, build/install from Android Studio. For testers, publish the APK to a private GitHub Release or Google Play Internal Testing, then set the URL in Render.</p>
    <p class="micro">Render environment variable: <strong>ANDROID_PLAY_URL</strong> or <strong>ANDROID_APK_URL</strong></p>`);
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
async function openGroup(gid){
  state.activeChat=null;state.replyTo=null;
  const g=await api(`/v24/groups/${gid}`);state.activeGroup=g;state.groupMessages=await api(`/v24/groups/${gid}/messages`);await api(`/v24/groups/${gid}/read`,{method:"POST"}).catch(()=>{});
  $("emptyChat").classList.add("hidden");$("activeChat").classList.add("hidden");$("activeGroup").classList.remove("hidden");
  $("groupName").textContent=g.name;$("groupMeta").textContent=`${g.member_count} members · Q ${g.ai_mode}`;
  $("groupAvatar").innerHTML=g.photo_url?`<img src="${escapeHtml(g.photo_url)}" alt="">`:escapeHtml(initials(g.name));
  $("groupAssistBar").classList.toggle("hidden",g.ai_mode!=="ASSIST");renderGroupMessages();renderChats();
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

function startTone(kind){stopRing();try{const AC=window.AudioContext||window.webkitAudioContext,ctx=new AC();state.ringAudio={ctx,timer:null};const beep=()=>{const o=ctx.createOscillator(),g=ctx.createGain();o.frequency.value=kind==="incoming"?740:440;g.gain.value=.035;o.connect(g);g.connect(ctx.destination);o.start();o.stop(ctx.currentTime+.22)};beep();state.ringAudio.timer=setInterval(beep,kind==="incoming"?900:1600)}catch{}}
function stopRing(){if(state.ringAudio){clearInterval(state.ringAudio.timer);try{state.ringAudio.ctx.close()}catch{}state.ringAudio=null}}
function startCallTimer(){clearInterval(state.callTimerHandle);state.callSeconds=0;$("callTimer").textContent="00:00";state.callTimerHandle=setInterval(()=>{$("callTimer").textContent=formatDuration(++state.callSeconds)},1000)}
async function startVoiceCall(){
  if(!state.activeChat)return;
  try{
    const join=await api("/v24/calls/start",{method:"POST",body:JSON.stringify({chat_id:state.activeChat.id})});
    state.callPhase="ringing";$("callState").textContent="Ringing…";$("callTimer").textContent="";$("callOverlay").classList.remove("hidden");$("callAvatar").innerHTML=state.activeChat.other_user.avatar_url?`<img src="${escapeHtml(state.activeChat.other_user.avatar_url)}">`:escapeHtml(initials(state.activeChat.other_user.display_name));startTone("outgoing");
    await connectCallRoom(join,state.activeChat.other_user.display_name,false);
    clearTimeout(state.callTimeoutHandle);state.callTimeoutHandle=setTimeout(()=>{if(state.callPhase==="ringing"){toast("No answer");endVoiceCall()}},45000);
  }catch(e){toast(e.message,true)}
}
async function connectCallRoom(join,person,incoming){
  if(!window.LivekitClient)throw new Error("LiveKit client unavailable");
  const {Room,RoomEvent,Track}=LivekitClient,room=new Room();state.callRoom=room;state.callId=join.call.id;$("callPerson").textContent=person;
  room.on(RoomEvent.ParticipantConnected,()=>onRemoteAnswered());
  room.on(RoomEvent.TrackSubscribed,t=>{if(t.kind===Track.Kind.Audio){const el=t.attach();el.autoplay=true;$("remoteAudio").appendChild(el)}});
  room.on(RoomEvent.Disconnected,()=>{if(state.callPhase==="connected")$("callState").textContent="Call ended"});
  await room.connect(join.ws_url,join.token);await room.localParticipant.setMicrophoneEnabled(true);
  if(incoming||room.remoteParticipants?.size>0)onRemoteAnswered();
}
function onRemoteAnswered(){if(state.callPhase==="connected")return;stopRing();clearTimeout(state.callTimeoutHandle);state.callPhase="connected";$("callState").textContent="Connected";$("callTimer").textContent="00:00";startCallTimer()}
function showIncomingCall(p){
  openModal(`<h3>📞 Incoming LEMMIQ call</h3><p><strong>${escapeHtml(p.caller_name||"LEMMIQ user")}</strong> is calling.</p><div class="suggestion-actions"><button id="incDecline" class="danger">Decline</button><button id="incAnswer" class="primary">Answer</button></div>`);startTone("incoming");
  $("incDecline").onclick=async()=>{stopRing();await api(`/v24/calls/${p.call_id}/decline`,{method:"POST"}).catch(()=>{});closeModal()};
  $("incAnswer").onclick=async()=>{stopRing();const join=await api(`/v24/calls/${p.call_id}/join`,{method:"POST"});closeModal();state.callPhase="connecting";$("callOverlay").classList.remove("hidden");$("callPerson").textContent=p.caller_name||"LEMMIQ user";$("callAvatar").innerHTML=p.caller_avatar_url?`<img src="${escapeHtml(p.caller_avatar_url)}">`:escapeHtml(initials(p.caller_name||"LEMMIQ user"));await connectCallRoom(join,p.caller_name||"LEMMIQ user",true)};
}
async function endVoiceCall(notify=true){
  stopRing();clearInterval(state.callTimerHandle);clearTimeout(state.callTimeoutHandle);try{state.callRoom?.disconnect()}catch{}
  if(notify&&state.callId)api(`/v24/calls/${state.callId}/end`,{method:"POST"}).catch(()=>{});
  state.callRoom=null;state.callId=null;state.callPhase="idle";$("remoteAudio").innerHTML="";$("callOverlay").classList.add("hidden");if(state.activeChat)openChat(state.activeChat.id,false).catch(()=>{});
}
async function toggleCallMute(){if(!state.callRoom)return;const enabled=state.callRoom.localParticipant.isMicrophoneEnabled;await state.callRoom.localParticipant.setMicrophoneEnabled(!enabled);$("muteCallBtn").textContent=enabled?"🔇":"🎙"}

async function loadStatuses(){state.statuses=await api("/v24/status");renderStatuses()}
function renderStatuses(){
  const mine=state.statuses.filter(s=>s.user.id===state.user.id),other=state.statuses.filter(s=>s.user.id!==state.user.id);
  $("myStatusList").innerHTML=mine.length?mine.map(s=>`<div class="status-card" onclick="openStatus(${s.id})"><strong>${escapeHtml(s.text||s.kind)}</strong><p class="micro">${timeOnly(s.created_at)} · ${s.view_count||0} views</p></div>`).join(""):`<p class="micro">No active status.</p>`;
  $("statusList").innerHTML=other.length?other.map(s=>`<div class="status-card" onclick="openStatus(${s.id})"><div class="status-ring ${s.viewed?"viewed":""}">${avatarHtml(s.user)}</div><strong>${escapeHtml(s.user.display_name)}</strong><p>${escapeHtml(s.text||s.kind)}</p><span class="micro">${timeOnly(s.created_at)}</span></div>`).join(""):`<p class="micro">No recent updates.</p>`;
}
async function addTextStatus(){openModal(`<h3>⭕ Text status</h3><textarea id="stText" maxlength="1500" placeholder="What’s happening?"></textarea><button id="stPost" class="primary full">Post for 24 hours</button>`);$("stPost").onclick=async()=>{const text=$("stText").value.trim();if(!text)return;await api("/v24/status/text",{method:"POST",body:JSON.stringify({text})});closeModal();await loadStatuses()}}
async function uploadStatusMedia(file){if(!file)return;const fd=new FormData();fd.append("file",file);fd.append("caption","");try{toast("Posting status…");await api("/v24/status/media",{method:"POST",body:fd});await loadStatuses();toast("Status posted")}catch(e){toast(e.message,true)}}
async function openStatus(id){
  let s=state.statuses.find(x=>x.id===id);if(!s)return;s=await api(`/v24/status/${id}/view`,{method:"POST"});let media="";
  if(s.media_url){try{const r=await fetch(s.media_url,{headers:authHeaders()});const b=await r.blob(),url=URL.createObjectURL(b);media=s.kind==="VIDEO"?`<video class="status-media" src="${url}" controls autoplay></video>`:`<img class="status-media" src="${url}">`}catch{}}
  openModal(`<h3>${escapeHtml(s.user.display_name)} · Status</h3>${media}<p>${escapeHtml(s.text||"")}</p><p class="micro">${new Date(s.created_at).toLocaleString()}${s.view_count!=null?` · ${s.view_count} views`:""}</p>${s.user.id!==state.user.id?`<button id="statusReply" class="primary">Reply in chat</button>`:`<button id="statusDelete" class="danger">Delete status</button>`}`);
  if($("statusReply"))$("statusReply").onclick=async()=>{const c=await api("/chats/direct",{method:"POST",body:JSON.stringify({user_id:s.user.id})});closeModal();setView("chats");await loadChats();await openChat(c.id);$("messageInput").value=`Replied to your status: ${s.text||s.kind}`;await saveDraft($("messageInput").value)};
  if($("statusDelete"))$("statusDelete").onclick=async()=>{await api(`/v24/status/${s.id}`,{method:"DELETE"});closeModal();await loadStatuses()};
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

async function loadAgentV24(){await loadAgent();try{state.socialBrief=await api("/v24/social-iq/brief");renderSocialIq()}catch{}}
function renderSocialIq(){
  const b=state.socialBrief||{count:0,promises:0,follow_ups:0,items:[]};
  $("socialIqStats").innerHTML=`<div class="stat"><strong>${b.count}</strong><span>remembered</span></div><div class="stat"><strong>${b.promises}</strong><span>promises</span></div><div class="stat"><strong>${b.follow_ups}</strong><span>follow-ups</span></div>`;
  $("socialMemoryList").innerHTML=(b.items||[]).map(m=>`<div class="social-memory"><strong>${escapeHtml(m.memory_type)} · ${escapeHtml(m.title)}</strong><p>${escapeHtml(m.detail||"")}</p><span class="micro">${escapeHtml(m.contact||"")} · ${new Date(m.created_at).toLocaleDateString()}</span><button class="mini" onclick="deleteSocialMemory(${m.id})">Delete</button></div>`).join("")||`<p class="micro">No Social IQ memories yet. Scan recent chats when you want Q to extract explicit follow-ups and commitments.</p>`;
}
async function scanSocial(){try{toast("Q is scanning recent chats…");const r=await api("/v24/social-iq/scan",{method:"POST"});state.socialBrief=await api("/v24/social-iq/brief");renderSocialIq();toast(`${r.added||0} new memory items added`)}catch(e){toast(e.message,true)}}
async function deleteSocialMemory(id){await api(`/v24/social-iq/memories/${id}`,{method:"DELETE"});state.socialBrief=await api("/v24/social-iq/brief");renderSocialIq()}
window.deleteSocialMemory=deleteSocialMemory;

async function uploadProfilePhoto(file){if(!file)return;const fd=new FormData();fd.append("file",file);try{const u=await api("/v24/profile/avatar",{method:"POST",body:fd});state.user={...state.user,...u};localStorage.setItem("lemmiq_user",JSON.stringify(state.user));renderMeAvatar();await loadChats();toast("Profile photo updated")}catch(e){toast(e.message,true)}}
async function removeProfilePhoto(){try{const u=await api("/v24/profile/avatar",{method:"DELETE"});state.user={...state.user,...u};localStorage.setItem("lemmiq_user",JSON.stringify(state.user));renderMeAvatar();await loadChats();toast("Profile photo removed")}catch(e){toast(e.message,true)}}

document.addEventListener("DOMContentLoaded",()=>{
  $("loginTab").onclick=()=>{$("loginTab").classList.add("active");$("registerTab").classList.remove("active");$("loginForm").classList.remove("hidden");$("registerForm").classList.add("hidden")};
  $("registerTab").onclick=()=>{$("registerTab").classList.add("active");$("loginTab").classList.remove("active");$("registerForm").classList.remove("hidden");$("loginForm").classList.add("hidden")};
  $("loginForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/login",{method:"POST",body:JSON.stringify({username:$("loginUsername").value,password:$("loginPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};
  $("registerForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/register",{method:"POST",body:JSON.stringify({display_name:$("regName").value,username:$("regUsername").value,password:$("regPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};

  qsa("#nav button").forEach(b=>b.onclick=()=>setView(b.dataset.view));
  qsa("[data-more-view]").forEach(b=>b.onclick=()=>setView(b.dataset.moreView));
  $("refreshBtn").onclick=refreshCurrent;$("logoutBtn").onclick=logout;

  $("newChatBtn").onclick=showNewChat;$("newGroupBtn").onclick=showNewGroup;$("chatFilter").oninput=renderChats;
  qsa("[data-chat-filter]").forEach(b=>b.onclick=()=>{state.chatFilterMode=b.dataset.chatFilter;qsa("[data-chat-filter]").forEach(x=>x.classList.toggle("active",x===b));renderChats()});

  $("sendBtn").onclick=sendMessage;$("suggestBtn").onclick=suggestReply;$("assistBarBtn").onclick=suggestReply;
  $("messageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}});
  $("messageInput").addEventListener("input",()=>{clearTimeout(window.__draftTimer);window.__draftTimer=setTimeout(()=>saveDraft($("messageInput").value),500)});
  $("fileInput").onchange=e=>{uploadAttachment(e.target.files[0]);e.target.value=""};
  $("voiceBtn").onclick=()=>toggleVoice("direct");$("callBtn").onclick=startVoiceCall;$("chatSearchBtn").onclick=openChatSearch;$("chatMoreBtn").onclick=openChatMore;
  $("chatAiBtn").onclick=personalChatSettings;$("summaryBtn").onclick=chatSummary;$("businessChatBtn").onclick=businessChatSettings;

  $("groupVoiceBtn").onclick=()=>toggleVoice("group");$("groupSendBtn").onclick=sendGroupMessage;
  $("groupMessageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendGroupMessage()}});
  $("groupFileInput").onchange=async e=>{const f=e.target.files[0];if(f&&state.activeGroup){const fd=new FormData();fd.append("file",f);try{await api(`/v24/groups/${state.activeGroup.id}/attachments`,{method:"POST",body:fd});await openGroup(state.activeGroup.id)}catch(err){toast(err.message,true)}}e.target.value=""};
  $("groupSuggestBtn").onclick=groupSuggestReply;$("groupSuggestTop").onclick=groupSuggestReply;$("groupCatchupBtn").onclick=groupCatchup;$("groupQBtn").onclick=groupAsk;$("groupSettingsBtn").onclick=groupSettings;

  $("muteCallBtn").onclick=toggleCallMute;$("endCallBtn").onclick=()=>endVoiceCall(true);$("speakerCallBtn").onclick=()=>toast("Browser speaker routing follows your device/browser audio output.");

  $("addTextStatusBtn").onclick=addTextStatus;$("statusMediaInput").onchange=e=>{uploadStatusMedia(e.target.files[0]);e.target.value=""};

  $("askAgentBtn").onclick=askAgent;$("scanSocialBtn").onclick=scanSocial;
  $("trustBtn").onclick=()=>{const t=$("trustText").value.trim();if(t)runTrust(t)};
  $("trustHistorySearch").oninput=()=>{clearTimeout(window.__trustSearch);window.__trustSearch=setTimeout(loadTrustHistory,250)};
  $("clearTrustHistoryBtn").onclick=async()=>{if(confirm("Clear all saved Trust checks?")){await api("/trust/history",{method:"DELETE"});await loadTrustHistory()}};

  $("resetMoneyBtn").onclick=()=>resetInsights("MONEY");$("resetActivityBtn").onclick=()=>resetInsights("ACTIVITY");$("resetAllInsightsBtn").onclick=()=>resetInsights("ALL");
  $("saveBizBtn").onclick=saveBusiness;$("addKbBtn").onclick=addKnowledge;$("bizDocInput").onchange=e=>{uploadBizDoc(e.target.files[0]);e.target.value=""};

  $("profilePhotoInput").onchange=e=>{uploadProfilePhoto(e.target.files[0]);e.target.value=""};$("removeProfilePhotoBtn").onclick=removeProfilePhoto;

  $("closeModal").onclick=closeModal;$("modal").addEventListener("click",e=>{if(e.target===$("modal"))closeModal()});
  $("installBtn").onclick=installHelp;$("installBtn2").onclick=installHelp;$("androidDownloadBtn").onclick=installAndroidApp;$("androidBtnTop").onclick=installAndroidApp;
  $("moreInstallBtn").onclick=installHelp;$("moreAndroidBtn").onclick=installAndroidApp;
  window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();state.installPrompt=e;$("installBtn").classList.remove("hidden")});
  if("serviceWorker" in navigator)navigator.serviceWorker.register("/web/sw.js").catch(()=>{});

  loadAppConfig();
  if(state.token&&state.user)showApp();
});

window.openChat=openChat;
window.openGroup=openGroup;
window.checkMessage=checkMessage;
