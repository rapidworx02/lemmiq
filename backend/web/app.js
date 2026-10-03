const state = {
  token: localStorage.getItem("lemmiq_token") || "",
  user: JSON.parse(localStorage.getItem("lemmiq_user") || "null"),
  chats: [],
  activeChat: null,
  messages: [],
  socket: null,
  installPrompt: null
};

const $ = id => document.getElementById(id);
const qsa = s => [...document.querySelectorAll(s)];
const escapeHtml = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = cents => new Intl.NumberFormat(undefined,{style:"currency",currency:"AUD"}).format((cents||0)/100);
const initials = s => (s||"?").trim().split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase();

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
  connectSocket(); refreshCurrent();
}
function setView(name){
  qsa(".view").forEach(v=>v.classList.remove("active"));
  $(`view-${name}`).classList.add("active");
  qsa("#nav button").forEach(b=>b.classList.toggle("active",b.dataset.view===name));
  const meta={
    chats:["Chats","Your conversations, understood by Q."],
    agent:["Q Agent","Personal communication intelligence across your LEMMIQ chats."],
    trust:["LEMMIQ Trust","Check claims, suspicious links and possible scams."],
    business:["Business Agent","Teach LEMMIQ how your business operates."],
    activity:["Activity & Money","Detected phone activity synced by your Android companion."],
    me:["Me","Your account and LEMMIQ access."]
  }[name];
  $("pageTitle").textContent=meta[0];$("pageSub").textContent=meta[1];
  refreshView(name);
}
async function refreshView(name){
  try{
    if(name==="chats") await loadChats();
    if(name==="agent") await loadAgent();
    if(name==="business") await loadBusiness();
    if(name==="activity") await loadActivity();
  }catch(e){toast(e.message,true)}
}
function refreshCurrent(){
  const active=document.querySelector("#nav button.active")?.dataset.view||"chats";
  refreshView(active);
}
function connectSocket(){
  if(!state.token) return;
  if(state.socket) try{state.socket.close()}catch{}
  const proto=location.protocol==="https:"?"wss":"ws";
  const ws=new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(state.token)}`);
  state.socket=ws;
  ws.onopen=()=>{ $("socketDot").classList.add("on");$("socketText").textContent="connected"; ws.send("hello"); };
  ws.onclose=()=>{ $("socketDot").classList.remove("on");$("socketText").textContent="offline"; setTimeout(()=>{if(state.token)connectSocket()},4500); };
  ws.onerror=()=>{};
  ws.onmessage=async ev=>{
    try{
      const p=JSON.parse(ev.data);
      if(p.type==="message"){
        await loadChats();
        if(state.activeChat && p.data?.chat_id===state.activeChat.id) await openChat(state.activeChat.id,false);
      }
    }catch{}
  };
  window.__wsPing && clearInterval(window.__wsPing);
  window.__wsPing=setInterval(()=>{if(ws.readyState===1)ws.send("ping")},20000);
}

async function loadChats(){
  state.chats=await api("/chats");
  renderChats();
}
function renderChats(){
  const filter=$("chatFilter").value.toLowerCase().trim();
  const rows=state.chats.filter(c=>(c.other_user.display_name+" "+c.other_user.username+" "+(c.last_message||"")).toLowerCase().includes(filter));
  $("chatList").innerHTML=rows.length?rows.map(c=>`
    <button class="chat-row ${state.activeChat?.id===c.id?"active":""}" onclick="openChat(${c.id})">
      <span class="avatar">${escapeHtml(initials(c.other_user.display_name))}</span>
      <span class="body"><strong>${escapeHtml(c.other_user.display_name)}</strong><small>${escapeHtml(c.last_message||"Start chatting")}</small></span>
      ${c.unread?`<span class="badge">${c.unread}</span>`:""}
    </button>`).join(""):`<div class="empty-state"><p>No conversations yet.</p></div>`;
}
async function openChat(cid, mark=true){
  let chat=state.chats.find(x=>x.id===cid);
  if(!chat){await loadChats();chat=state.chats.find(x=>x.id===cid)}
  if(!chat)return;
  state.activeChat=chat;
  state.messages=await api(`/chats/${cid}/messages`);
  if(mark) api(`/chats/${cid}/read`,{method:"POST"}).catch(()=>{});
  $("emptyChat").classList.add("hidden");$("activeChat").classList.remove("hidden");
  $("chatName").textContent=chat.other_user.display_name;
  $("chatMeta").textContent=`@${chat.other_user.username} · ${chat.category} · AI ${chat.ai_mode}`;
  document.querySelector(".chat-layout").classList.add("open-chat");
  renderMessages(); renderChats();
}
function renderMessages(){
  const me=state.user?.id;
  $("messageList").innerHTML=state.messages.map(m=>{
    const mine=m.sender_id===me;
    const attachment=m.attachment;
    let attach="";
    if(attachment){
      if(attachment.kind==="CONTACT"){
        attach=`<div class="answer-box">👤 <strong>${escapeHtml(attachment.contact_name)}</strong><br><small>${escapeHtml(attachment.contact_phone)}</small></div>`;
      }else{
        attach=`<button class="mini" onclick="downloadMedia(${m.id},'${escapeHtml((attachment.name||"file").replace(/'/g,""))}')">📎 ${escapeHtml(attachment.name||attachment.kind)}</button>`;
      }
    }
    return `<div class="msg ${mine?"mine":"theirs"}">
      ${m.ai_generated?`<div class="micro">✨ AI generated</div>`:""}
      <div>${escapeHtml(m.text).replace(/\n/g,"<br>")}</div>${attach}
      ${!mine?`<div class="msg-actions"><button class="mini" onclick="checkMessage(${m.id})">🛡 Fact / Scam Check</button></div>`:""}
      <div class="meta">${new Date(m.created_at).toLocaleString()}</div>
    </div>`;
  }).join("");
  const list=$("messageList"); setTimeout(()=>list.scrollTop=list.scrollHeight,30);
}
async function sendMessage(){
  const box=$("messageInput"), text=box.value.trim();
  if(!text||!state.activeChat)return;
  box.value="";
  try{await api(`/chats/${state.activeChat.id}/messages`,{method:"POST",body:JSON.stringify({text})});await openChat(state.activeChat.id,false)}
  catch(e){toast(e.message,true)}
}
async function suggestReply(){
  if(!state.activeChat)return;
  try{
    const r=await api(`/chats/${state.activeChat.id}/suggest`,{method:"POST"});
    showSuggestion(r.reply);
  }catch(e){toast(e.message,true)}
}
function showSuggestion(reply){
  const el=$("suggestionCard"); el.classList.remove("hidden");
  el.innerHTML=`<strong>Q suggested reply</strong><p>${escapeHtml(reply)}</p>
  <div class="suggestion-actions">
    <button class="ghost" onclick="discardSuggestion()">Discard</button>
    <button class="ghost" onclick="editSuggestion(${JSON.stringify(reply)})">Edit</button>
    <button class="primary" onclick="sendSuggested(${JSON.stringify(reply)})">Send</button>
  </div>`;
}
window.discardSuggestion=()=>{$("suggestionCard").classList.add("hidden");$("suggestionCard").innerHTML=""};
window.editSuggestion=r=>{$("messageInput").value=r;discardSuggestion();$("messageInput").focus()};
window.sendSuggested=async r=>{ $("messageInput").value=r;discardSuggestion();await sendMessage(); };

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
  const el=$("suggestionCard");el.classList.remove("hidden");
  el.innerHTML=`<strong>💼 Business Agent · ${Number(r.confidence||0)}% grounded</strong>
  <p>${escapeHtml(r.reply||"")}</p><p class="micro">${escapeHtml(r.reason||"")}${src?`<br>Sources: ${escapeHtml(src)}`:""}</p>
  <div class="suggestion-actions"><button class="ghost" onclick="discardSuggestion()">Discard</button><button class="ghost" onclick="editSuggestion(${JSON.stringify(r.reply||"")})">Edit</button><button class="primary" onclick="sendSuggested(${JSON.stringify(r.reply||"")})">Send</button></div>`;
}

async function loadActivity(){
  const r=await api("/insights/brief?days=30");
  $("spendingValue").textContent=money(r.spending_cents);
  $("activityStats").innerHTML=`<div class="stat"><strong>${r.detected_count||0}</strong><span>Detected events</span></div><div class="stat"><strong>${r.transactions||0}</strong><span>Transactions</span></div><div class="stat"><strong>${money(r.incoming_cents)}</strong><span>Detected incoming</span></div>`;
  $("activityList").innerHTML=(r.events||[]).length?(r.events||[]).map(e=>`<div class="event"><div><strong>${escapeHtml(e.title)}</strong><small>${escapeHtml(e.source)} · ${escapeHtml(e.category)} · ${new Date(e.occurred_at).toLocaleString()}</small><small>${escapeHtml(e.detail||"")}</small></div>${e.amount_cents!=null?`<div class="money">${e.direction==="OUT"?"−":e.direction==="IN"?"+":""}${money(e.amount_cents)}</div>`:""}</div>`).join(""):"<p class='micro'>No synced notification activity yet.</p>";
}

function openModal(html){$("modalContent").innerHTML=html;$("modal").showModal()}
function closeModal(){$("modal").close()}
async function installHelp(){
  if(state.installPrompt){
    state.installPrompt.prompt();
    await state.installPrompt.userChoice;
    state.installPrompt=null;$("installBtn").classList.add("hidden");
  }else{
    openModal(`<h3>Install LEMMIQ</h3><p><strong>Android / Chrome:</strong> open the browser menu and choose <em>Install app</em> or <em>Add to Home screen</em>.</p><p><strong>iPhone / iPad:</strong> open LEMMIQ in Safari → Share → <em>Add to Home Screen</em>.</p><p class="micro">The installed PWA uses the same cloud account. Android's native companion app is still required for cross-app notification intelligence.</p>`);
  }
}

document.addEventListener("DOMContentLoaded",()=>{
  $("loginTab").onclick=()=>{$("loginTab").classList.add("active");$("registerTab").classList.remove("active");$("loginForm").classList.remove("hidden");$("registerForm").classList.add("hidden")};
  $("registerTab").onclick=()=>{$("registerTab").classList.add("active");$("loginTab").classList.remove("active");$("registerForm").classList.remove("hidden");$("loginForm").classList.add("hidden")};

  $("loginForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/login",{method:"POST",body:JSON.stringify({username:$("loginUsername").value,password:$("loginPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};
  $("registerForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/register",{method:"POST",body:JSON.stringify({display_name:$("regName").value,username:$("regUsername").value,password:$("regPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};

  qsa("#nav button").forEach(b=>b.onclick=()=>setView(b.dataset.view));
  $("refreshBtn").onclick=refreshCurrent;$("logoutBtn").onclick=logout;
  $("newChatBtn").onclick=showNewChat;$("chatFilter").oninput=renderChats;
  $("sendBtn").onclick=sendMessage;$("suggestBtn").onclick=suggestReply;
  $("messageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}});
  $("fileInput").onchange=e=>{uploadAttachment(e.target.files[0]);e.target.value=""};
  $("summaryBtn").onclick=chatSummary;$("businessChatBtn").onclick=businessChatSettings;

  $("askAgentBtn").onclick=askAgent;$("trustBtn").onclick=()=>{const t=$("trustText").value.trim();if(t)runTrust(t)};
  $("saveBizBtn").onclick=saveBusiness;$("addKbBtn").onclick=addKnowledge;
  $("bizDocInput").onchange=e=>{uploadBizDoc(e.target.files[0]);e.target.value=""};
  $("closeModal").onclick=closeModal;$("modal").addEventListener("click",e=>{if(e.target===$("modal"))closeModal()});
  $("installBtn").onclick=installHelp;$("installBtn2").onclick=installHelp;

  window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();state.installPrompt=e;$("installBtn").classList.remove("hidden")});
  if("serviceWorker" in navigator) navigator.serviceWorker.register("/web/sw.js").catch(()=>{});

  if(state.token && state.user) showApp();
});

window.openChat=openChat;
