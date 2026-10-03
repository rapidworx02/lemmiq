const state = {
  token: localStorage.getItem("lemmiq_token") || "",
  user: JSON.parse(localStorage.getItem("lemmiq_user") || "null"),
  chats: [],
  groups: [],
  activeChat: null,
  activeGroup: null,
  messages: [],
  groupMessages: [],
  socket: null,
  installPrompt: null,
  mediaRecorder:null,
  voiceChunks:[],
  voiceStartedAt:0,
  voiceTarget:"direct",
  voiceTranscript:"",
  speechRecognition:null,
  callRoom:null,
  callId:null,
  callMuted:false,
  appConfig: {android_download_url:"", android_play_url:"", web_install_enabled:true}
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
    activity:["Activity","Detected phone activity synced by your Android companion."],
    money:["Money","Review and correct notification-derived payment insights."],
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
    if(name==="money") await loadMoney();
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
      if(p.type==="group_message"){
        await loadGroups();
        if(state.activeGroup && p.group_id===state.activeGroup.id) await openGroup(state.activeGroup.id);
      }
      if(p.type==="incoming_call"){
        showIncomingWebCall(p);
      }
    }catch{}
  };
  window.__wsPing && clearInterval(window.__wsPing);
  window.__wsPing=setInterval(()=>{if(ws.readyState===1)ws.send("ping")},20000);
}

async function loadChats(){
  state.chats=await api("/chats");
  renderChats();
  await loadGroups();
}
async function loadGroups(){
  state.groups=await api("/v23/groups");
  renderGroups();
}
function renderGroups(){
  const el=$("groupList"); if(!el)return;
  el.innerHTML=state.groups.length?`<div class="micro" style="padding:4px 5px">GROUPS</div>`+state.groups.map(g=>`
    <button class="group-row ${state.activeGroup?.id===g.id?"active":""}" onclick="openGroup(${g.id})">
      <span class="group-avatar">${escapeHtml(initials(g.name))}</span>
      <span class="body"><strong>${escapeHtml(g.name)}</strong><small>${g.member_count} members · ${escapeHtml(g.last_message||"New group")}</small></span>
      ${g.unread?`<span class="badge">${g.unread}</span>`:""}
    </button>`).join(""):"";
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
  state.activeGroup=null;
  state.activeChat=chat;
  state.messages=await api(`/chats/${cid}/messages`);
  if(mark) api(`/chats/${cid}/read`,{method:"POST"}).catch(()=>{});
  $("emptyChat").classList.add("hidden");$("activeGroup").classList.add("hidden");$("activeChat").classList.remove("hidden");
  $("chatName").textContent=chat.other_user.display_name;
  $("chatMeta").textContent=`@${chat.other_user.username} · ${chat.category} · AI ${chat.ai_mode}`;
  updateAssistBar(chat);
  document.querySelector(".chat-layout").classList.add("open-chat");
  renderMessages(); renderChats();
}

async function openGroup(gid){
  state.activeChat=null;
  const g=await api(`/v23/groups/${gid}`);
  state.activeGroup=g;
  state.groupMessages=await api(`/v23/groups/${gid}/messages`);await api(`/v23/groups/${gid}/read`,{method:"POST"});
  $("emptyChat").classList.add("hidden");$("activeChat").classList.add("hidden");$("activeGroup").classList.remove("hidden");
  $("groupName").textContent=g.name;
  $("groupMeta").textContent=`${g.member_count} members · Q ${g.ai_mode}`;
  $("groupAssistBar").classList.toggle("hidden",g.ai_mode!=="ASSIST");
  document.querySelector(".chat-layout").classList.add("open-chat");
  renderGroupMessages();renderGroups();renderChats();
}
function renderGroupMessages(){
  const me=state.user?.id;
  $("groupMessageList").innerHTML=state.groupMessages.map(m=>{
    const mine=m.sender_id===me;
    const a=m.attachment;
    let attachment="";
    if(a?.kind==="VOICE"){
      attachment=`<div class="voice-note"><button class="mini" onclick="loadVoice(${m.id},true,this)">▶ Voice ${Math.round((a.duration_ms||0)/1000)}s</button></div>${a.transcript?`<div class="micro">Transcript: ${escapeHtml(a.transcript)}</div>`:""}`;
    }else if(a?.media_id){
      attachment=`<button class="mini" onclick="downloadGroupMedia(${m.id},'${escapeHtml((a.name||"file").replace(/'/g,""))}')">📎 ${escapeHtml(a.name||a.kind)}</button>`;
    }
    return `<div class="msg ${mine?"mine":"theirs"}"><div class="micro">${escapeHtml(m.sender?.display_name||"Member")}</div><div>${escapeHtml(m.text)}</div>${attachment}<div class="meta">${new Date(m.created_at).toLocaleString()}</div></div>`;
  }).join("");
  const list=$("groupMessageList");setTimeout(()=>list.scrollTop=list.scrollHeight,30);
}
async function sendGroupMessage(){
  const box=$("groupMessageInput"),text=box.value.trim();if(!state.activeGroup||!text)return;
  box.value="";
  try{await api(`/v23/groups/${state.activeGroup.id}/messages`,{method:"POST",body:JSON.stringify({text})});await openGroup(state.activeGroup.id)}
  catch(e){toast(e.message,true)}
}
async function showNewGroup(){
  openModal(`<h3>👥 New LEMMIQ group</h3><label>Group name<input id="newGroupName" placeholder="Weekend Crew"></label><label>Search usernames<input id="groupUserSearch" placeholder="Search username or display name"></label><div id="groupUserResults" class="modal-results"></div><div><strong>Selected</strong><div id="groupSelected" class="chips"></div></div><button id="createGroupBtn" class="primary full">Create group</button>`);
  const selected=new Map();
  const rerender=()=>{$("groupSelected").innerHTML=[...selected.values()].map(u=>`<span>@${escapeHtml(u.username)} <button class="mini" onclick="removeGroupPick(${u.id})">×</button></span>`).join("")};
  window.removeGroupPick=id=>{selected.delete(id);rerender()};
  $("groupUserSearch").oninput=async e=>{
    const q=e.target.value.trim();if(q.length<2){$("groupUserResults").innerHTML="";return}
    const rows=await api(`/users/search?q=${encodeURIComponent(q)}`);
    $("groupUserResults").innerHTML=rows.map(u=>`<div class="user-result"><div><strong>${escapeHtml(u.display_name)}</strong><small> @${escapeHtml(u.username)}</small></div><button class="ghost" data-pick="${u.id}">Add</button></div>`).join("");
    document.querySelectorAll("[data-pick]").forEach(btn=>btn.onclick=()=>{
      const u=rows.find(x=>x.id===Number(btn.dataset.pick));if(u){selected.set(u.id,u);rerender()}
    });
  };
  $("createGroupBtn").onclick=async()=>{
    const name=$("newGroupName").value.trim();if(!name||!selected.size)return toast("Add a group name and at least one member",true);
    try{const g=await api("/v23/groups",{method:"POST",body:JSON.stringify({name,member_ids:[...selected.keys()]})});closeModal();await loadGroups();await openGroup(g.id)}
    catch(e){toast(e.message,true)}
  };
}
async function groupSuggestReply(){
  if(!state.activeGroup)return;
  try{
    const r=await api(`/v23/groups/${state.activeGroup.id}/suggest`,{method:"POST"});
    const card=$("groupSuggestionCard");card.classList.remove("hidden");
    card.innerHTML=`<strong>Q · Group suggestion</strong><p>${escapeHtml(r.reply||"")}</p><div class="suggestion-actions"><button class="ghost" id="discardGroupSuggestion">Discard</button><button class="ghost" id="editGroupSuggestion">Edit</button><button class="primary" id="sendGroupSuggestion">Send</button></div>`;
    $("discardGroupSuggestion").onclick=()=>card.classList.add("hidden");
    $("editGroupSuggestion").onclick=()=>{$("groupMessageInput").value=r.reply||"";card.classList.add("hidden")};
    $("sendGroupSuggestion").onclick=async()=>{await api(`/v23/groups/${state.activeGroup.id}/messages`,{method:"POST",body:JSON.stringify({text:r.reply||""})});card.classList.add("hidden");await openGroup(state.activeGroup.id)};
  }catch(e){toast(e.message,true)}
}
async function groupCatchup(){
  if(!state.activeGroup)return;
  openModal("<h3>🧠 Catch me up</h3><p>Q is reading the recent group conversation…</p>");
  try{
    const r=await api(`/v23/groups/${state.activeGroup.id}/summary`,{method:"POST"});
    $("modalContent").innerHTML=`<h3>🧠 Catch me up</h3><p>${escapeHtml(r.summary||"")}</p>${(r.decisions||[]).length?`<h4>Decisions</h4>${r.decisions.map(x=>`<p>• ${escapeHtml(x)}</p>`).join("")}`:""}${(r.actions||[]).length?`<h4>Follow-ups</h4>${r.actions.map(x=>`<p>• ${escapeHtml(x)}</p>`).join("")}`:""}`;
  }catch(e){$("modalContent").innerHTML=`<h3>Catch-up failed</h3><p>${escapeHtml(e.message)}</p>`}
}
async function groupAsk(){
  if(!state.activeGroup)return;
  openModal(`<h3>Q · ${escapeHtml(state.activeGroup.name)}</h3><textarea id="groupQuestion" placeholder="What did everyone decide about Saturday?"></textarea><button id="askGroupNow" class="primary full">Ask Q</button><div id="groupAnswer"></div>`);
  $("askGroupNow").onclick=async()=>{
    const question=$("groupQuestion").value.trim();if(!question)return;
    $("groupAnswer").innerHTML="<p>Q is checking the group history…</p>";
    try{const r=await api(`/v23/groups/${state.activeGroup.id}/ask`,{method:"POST",body:JSON.stringify({question})});$("groupAnswer").innerHTML=`<div class="answer-box"><p>${escapeHtml(r.answer||"")}</p>${(r.references||[]).map(x=>`<p class="micro">• ${escapeHtml(x)}</p>`).join("")}</div>`}
    catch(e){$("groupAnswer").textContent=e.message}
  };
}
async function groupSettings(){
  const g=state.activeGroup;if(!g)return;
  const admin=g.role==="ADMIN";
  openModal(`<h3>👥 ${escapeHtml(g.name)}</h3>
    <label>Group AI<select id="groupAiMode"><option ${g.ai_mode==="OFF"?"selected":""}>OFF</option><option ${g.ai_mode==="ASSIST"?"selected":""}>ASSIST</option><option ${g.ai_mode==="SUMMARY"?"selected":""}>SUMMARY</option></select></label>
    <label>Tone<select id="groupTone"><option>Natural</option><option>Warm</option><option>Casual</option><option>Professional</option></select></label>
    ${admin?`<label class="upload">🖼 Upload group photo<input id="groupPhotoInput" type="file" accept="image/*" hidden></label><label>Add member<input id="groupAddSearch" placeholder="Search username"></label><div id="groupAddResults"></div>`:""}
    <button id="saveGroupSettings" class="primary">Save</button>
    <div class="group-member-list">${g.members.map(m=>`<div class="group-member"><span>${escapeHtml(m.display_name)} <small>@${escapeHtml(m.username)}</small></span><span><strong>${m.role}</strong>${admin&&m.id!==state.user.id?` <button class="mini" data-admin="${m.id}">${m.role==="ADMIN"?"Make member":"Make admin"}</button><button class="mini" data-remove="${m.id}">Remove</button>`:""}</span></div>`).join("")}</div>
    <p class="micro">Group AUTO replies are intentionally disabled in V2.3.</p>`);
  $("groupTone").value=g.tone||"Natural";
  $("saveGroupSettings").onclick=async()=>{try{const updated=await api(`/v23/groups/${g.id}/settings`,{method:"PUT",body:JSON.stringify({ai_mode:$("groupAiMode").value,tone:$("groupTone").value})});state.activeGroup=updated;closeModal();await loadGroups();$("groupMeta").textContent=`${updated.member_count} members · Q ${updated.ai_mode}`;toast("Group AI saved")}catch(e){toast(e.message,true)}};
  if(admin){
    $("groupPhotoInput").onchange=async e=>{const file=e.target.files[0];if(!file)return;const fd=new FormData();fd.append("file",file);try{await api(`/v23/groups/${g.id}/photo`,{method:"POST",body:fd});toast("Group photo updated");await openGroup(g.id)}catch(err){toast(err.message,true)}};
    $("groupAddSearch").oninput=async e=>{const q=e.target.value.trim();if(q.length<2){$("groupAddResults").innerHTML="";return}const rows=await api(`/users/search?q=${encodeURIComponent(q)}`);$("groupAddResults").innerHTML=rows.filter(u=>!g.members.some(m=>m.id===u.id)).map(u=>`<div class="user-result"><span>${escapeHtml(u.display_name)} @${escapeHtml(u.username)}</span><button class="mini" data-addmember="${u.id}">Add</button></div>`).join("");document.querySelectorAll("[data-addmember]").forEach(b=>b.onclick=async()=>{await api(`/v23/groups/${g.id}/members`,{method:"POST",body:JSON.stringify({user_id:Number(b.dataset.addmember)})});closeModal();await openGroup(g.id);groupSettings()})};
    document.querySelectorAll("[data-admin]").forEach(b=>b.onclick=async()=>{const uid=Number(b.dataset.admin);const m=g.members.find(x=>x.id===uid);await api(`/v23/groups/${g.id}/members/${uid}`,{method:"PUT",body:JSON.stringify({role:m.role==="ADMIN"?"MEMBER":"ADMIN"})});closeModal();await openGroup(g.id);groupSettings()});
    document.querySelectorAll("[data-remove]").forEach(b=>b.onclick=async()=>{if(!confirm("Remove this member?"))return;await api(`/v23/groups/${g.id}/members/${Number(b.dataset.remove)}`,{method:"DELETE"});closeModal();await openGroup(g.id);groupSettings()});
  }
}

async function uploadGroupAttachment(file){
  if(!state.activeGroup||!file)return;
  const fd=new FormData();fd.append("file",file);
  try{toast("Uploading…");await api(`/v23/groups/${state.activeGroup.id}/attachments`,{method:"POST",body:fd});await openGroup(state.activeGroup.id)}
  catch(e){toast(e.message,true)}
}
async function downloadGroupMedia(id,name){
  try{const r=await fetch(`/v23/group-media/${id}`,{headers:authHeaders()});if(!r.ok)throw new Error(`Download failed (${r.status})`);const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name||"lemmiq-group-file";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message,true)}
}
window.openGroup=openGroup;window.downloadGroupMedia=downloadGroupMedia;

function updateAssistBar(chat){
  const bar=$("assistBar");if(!bar)return;
  bar.classList.toggle("hidden",chat?.ai_mode!=="ASSIST");
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
      }else if(attachment.kind==="VOICE"){
        attach=`<div class="voice-note"><button class="mini" onclick="loadVoice(${m.id},false,this)">▶ Voice ${Math.round((attachment.duration_ms||0)/1000)}s</button><button class="mini" onclick="voiceAI(${m.id})">Q</button></div>${attachment.transcript?`<div class="micro">Transcript: ${escapeHtml(attachment.transcript)}</div>`:""}`;
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


function supportsSpeechRecognition(){
  return !!(window.SpeechRecognition||window.webkitSpeechRecognition);
}
async function toggleVoice(target="direct"){
  if(state.mediaRecorder && state.mediaRecorder.state==="recording"){
    state.mediaRecorder.stop();return;
  }
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const preferred=MediaRecorder.isTypeSupported("audio/webm;codecs=opus")?"audio/webm;codecs=opus":"audio/webm";
    state.voiceChunks=[];state.voiceStartedAt=Date.now();state.voiceTarget=target;state.voiceTranscript="";
    const rec=new MediaRecorder(stream,{mimeType:preferred});state.mediaRecorder=rec;
    const btn=target==="group"?$("groupVoiceBtn"):$("voiceBtn");btn.classList.add("recording");btn.textContent="■";
    if(supportsSpeechRecognition()){
      const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
      const sr=new SR();state.speechRecognition=sr;sr.continuous=true;sr.interimResults=true;
      sr.onresult=e=>{let t="";for(let i=0;i<e.results.length;i++)t+=e.results[i][0].transcript+" ";state.voiceTranscript=t.trim()};
      try{sr.start()}catch{}
    }
    rec.ondataavailable=e=>{if(e.data?.size)state.voiceChunks.push(e.data)};
    rec.onstop=async()=>{
      stream.getTracks().forEach(t=>t.stop());
      try{state.speechRecognition?.stop()}catch{}
      btn.classList.remove("recording");btn.textContent="🎙";
      const duration=Date.now()-state.voiceStartedAt;
      const blob=new Blob(state.voiceChunks,{type:rec.mimeType||"audio/webm"});
      const fd=new FormData();fd.append("file",blob,"voice-note.webm");fd.append("duration_ms",String(duration));fd.append("transcript",state.voiceTranscript||"");
      try{
        toast("Sending voice message…");
        if(target==="group"&&state.activeGroup){
          await api(`/v23/groups/${state.activeGroup.id}/voice`,{method:"POST",body:fd});await openGroup(state.activeGroup.id);
        }else if(state.activeChat){
          await api(`/v23/chats/${state.activeChat.id}/voice`,{method:"POST",body:fd});await openChat(state.activeChat.id,false);
        }
      }catch(e){toast(e.message,true)}
      state.mediaRecorder=null;state.voiceChunks=[];
    };
    rec.start(250);
  }catch(e){toast("Microphone unavailable: "+e.message,true)}
}
async function loadVoice(id,isGroup,button){
  try{
    button.disabled=true;button.textContent="Loading…";
    const url=isGroup?`/v23/group-media/${id}`:`/media/${id}`;
    const r=await fetch(url,{headers:authHeaders()});if(!r.ok)throw new Error(`Audio HTTP ${r.status}`);
    const blob=await r.blob();const src=URL.createObjectURL(blob);
    const audio=document.createElement("audio");audio.controls=true;audio.src=src;audio.playbackRate=1;
    const speed=document.createElement("button");speed.className="mini";speed.textContent="1×";
    speed.onclick=()=>{audio.playbackRate=audio.playbackRate===1?1.5:audio.playbackRate===1.5?2:1;speed.textContent=audio.playbackRate+"×"};
    button.replaceWith(audio);audio.parentElement?.appendChild(speed);audio.play().catch(()=>{});
    audio.onended=()=>{};
  }catch(e){button.disabled=false;button.textContent="▶ Voice";toast(e.message,true)}
}
async function voiceAI(id){
  try{
    const r=await api(`/v23/voice/${id}/ai`,{method:"POST"});
    openModal(`<h3>Q · Voice note</h3><p><strong>Transcript</strong></p><p>${escapeHtml(r.transcript||"")}</p><p><strong>Summary</strong></p><p>${escapeHtml(r.summary||"")}</p>${r.suggested_reply?`<p><strong>Suggested reply</strong></p><div class="answer-box">${escapeHtml(r.suggested_reply)}</div><button id="useVoiceReply" class="primary">Use reply</button>`:""}`);
    if($("useVoiceReply"))$("useVoiceReply").onclick=()=>{$("messageInput").value=r.suggested_reply;closeModal()};
  }catch(e){toast(e.message,true)}
}
window.loadVoice=loadVoice;window.voiceAI=voiceAI;

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
  const el=$("suggestionCard");el.classList.remove("hidden");
  el.innerHTML=`<strong>💼 Business Agent · ${Number(r.confidence||0)}% grounded</strong>
  <p>${escapeHtml(r.reply||"")}</p><p class="micro">${escapeHtml(r.reason||"")}${src?`<br>Sources: ${escapeHtml(src)}`:""}</p>
  <div class="suggestion-actions"><button class="ghost" onclick="discardSuggestion()">Discard</button><button class="ghost" onclick="editSuggestion(${JSON.stringify(r.reply||"")})">Edit</button><button class="primary" onclick="sendSuggested(${JSON.stringify(r.reply||"")})">Send</button></div>`;
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
    state.appConfig = await api("/app-config");
    const hasNative = !!(state.appConfig.android_play_url || state.appConfig.android_download_url);
    $("androidBtnTop")?.classList.toggle("hidden", !hasNative);
    if($("androidInstallHint")){
      $("androidInstallHint").textContent = hasNative
        ? "Choose the native Android app for WhatsApp/SMS notification intelligence and stronger background features. The web app is the universal browser/PWA version."
        : "Native Android download is not configured yet. Set ANDROID_PLAY_URL or ANDROID_APK_URL on Render after publishing your APK or Play test link.";
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


function showIncomingWebCall(p){
  openModal(`<h3>📞 Incoming LEMMIQ call</h3><p><strong>${escapeHtml(p.caller_name||"LEMMIQ user")}</strong> is calling.</p><div class="suggestion-actions"><button id="declineWebCall" class="danger">Decline</button><button id="answerWebCall" class="primary">Answer</button></div>`);
  $("declineWebCall").onclick=async()=>{try{await api(`/v23/calls/${p.call_id}/decline`,{method:"POST"})}catch{}closeModal()};
  $("answerWebCall").onclick=async()=>{try{const join=await api(`/v23/calls/${p.call_id}/join`,{method:"POST"});closeModal();await connectVoiceCall(join,p.caller_name)}catch(e){toast(e.message,true)}};
}
async function startVoiceCall(){
  if(!state.activeChat)return;
  try{
    const join=await api("/v23/calls/start",{method:"POST",body:JSON.stringify({chat_id:state.activeChat.id})});
    await connectVoiceCall(join,state.activeChat.other_user.display_name);
  }catch(e){toast(e.message,true)}
}
async function connectVoiceCall(join,person){
  if(!window.LivekitClient)return toast("LiveKit client did not load",true);
  try{
    $("callOverlay").classList.remove("hidden");$("callPerson").textContent=person||"LEMMIQ call";$("callState").textContent="Connecting…";
    const {Room,RoomEvent,Track}=LivekitClient;
    const room=new Room();state.callRoom=room;state.callId=join.call.id;state.callMuted=false;
    room.on(RoomEvent.Connected,()=>{$("callState").textContent="Connected"});
    room.on(RoomEvent.Disconnected,()=>{$("callState").textContent="Call ended"});
    room.on(RoomEvent.TrackSubscribed,(track)=>{
      if(track.kind===Track.Kind.Audio){const el=track.attach();el.autoplay=true;$("remoteAudio").appendChild(el)}
    });
    await room.connect(join.ws_url,join.token);
    await room.localParticipant.setMicrophoneEnabled(true);
  }catch(e){toast("Call failed: "+e.message,true);endVoiceCall()}
}
async function endVoiceCall(){
  try{state.callRoom?.disconnect()}catch{}
  if(state.callId)api(`/v23/calls/${state.callId}/end`,{method:"POST"}).catch(()=>{});
  state.callRoom=null;state.callId=null;$("remoteAudio").innerHTML="";$("callOverlay").classList.add("hidden");
}
async function toggleCallMute(){
  if(!state.callRoom)return;state.callMuted=!state.callMuted;
  await state.callRoom.localParticipant.setMicrophoneEnabled(!state.callMuted);
  $("muteCallBtn").textContent=state.callMuted?"🔇":"🎙";
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

document.addEventListener("DOMContentLoaded",()=>{
  $("loginTab").onclick=()=>{$("loginTab").classList.add("active");$("registerTab").classList.remove("active");$("loginForm").classList.remove("hidden");$("registerForm").classList.add("hidden")};
  $("registerTab").onclick=()=>{$("registerTab").classList.add("active");$("loginTab").classList.remove("active");$("registerForm").classList.remove("hidden");$("loginForm").classList.add("hidden")};

  $("loginForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/login",{method:"POST",body:JSON.stringify({username:$("loginUsername").value,password:$("loginPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};
  $("registerForm").onsubmit=async e=>{e.preventDefault();try{const r=await api("/register",{method:"POST",body:JSON.stringify({display_name:$("regName").value,username:$("regUsername").value,password:$("regPassword").value})});saveSession(r);showApp()}catch(err){toast(err.message,true)}};

  qsa("#nav button").forEach(b=>b.onclick=()=>setView(b.dataset.view));
  $("refreshBtn").onclick=refreshCurrent;$("logoutBtn").onclick=logout;
  $("newChatBtn").onclick=showNewChat;$("newGroupBtn").onclick=showNewGroup;$("chatFilter").oninput=renderChats;
  $("sendBtn").onclick=sendMessage;$("suggestBtn").onclick=suggestReply;$("assistBarBtn").onclick=suggestReply;
  $("voiceBtn").onclick=()=>toggleVoice("direct");$("callBtn").onclick=startVoiceCall;
  $("messageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}});
  $("fileInput").onchange=e=>{uploadAttachment(e.target.files[0]);e.target.value=""};
  $("groupFileInput").onchange=e=>{uploadGroupAttachment(e.target.files[0]);e.target.value=""};
  $("groupVoiceBtn").onclick=()=>toggleVoice("group");$("groupSendBtn").onclick=sendGroupMessage;
  $("groupMessageInput").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendGroupMessage()}});
  $("groupSuggestBtn").onclick=groupSuggestReply;$("groupCatchupBtn").onclick=groupCatchup;$("groupQBtn").onclick=groupAsk;$("groupSettingsBtn").onclick=groupSettings;
  $("chatAiBtn").onclick=personalChatSettings;$("summaryBtn").onclick=chatSummary;$("businessChatBtn").onclick=businessChatSettings;
  $("muteCallBtn").onclick=toggleCallMute;$("endCallBtn").onclick=endVoiceCall;$("speakerCallBtn").onclick=()=>toast("Speaker routing is controlled by your browser/device.");

  $("askAgentBtn").onclick=askAgent;$("trustBtn").onclick=()=>{const t=$("trustText").value.trim();if(t)runTrust(t)};
  $("resetMoneyBtn").onclick=()=>resetInsights("MONEY");$("resetActivityBtn").onclick=()=>resetInsights("ACTIVITY");$("resetAllInsightsBtn").onclick=()=>resetInsights("ALL");
  $("saveBizBtn").onclick=saveBusiness;$("addKbBtn").onclick=addKnowledge;
  $("bizDocInput").onchange=e=>{uploadBizDoc(e.target.files[0]);e.target.value=""};
  $("closeModal").onclick=closeModal;$("modal").addEventListener("click",e=>{if(e.target===$("modal"))closeModal()});
  $("installBtn").onclick=installHelp;$("installBtn2").onclick=installHelp;
  $("androidDownloadBtn").onclick=installAndroidApp;$("androidBtnTop").onclick=installAndroidApp;

  window.addEventListener("beforeinstallprompt",e=>{e.preventDefault();state.installPrompt=e;$("installBtn").classList.remove("hidden")});
  if("serviceWorker" in navigator) navigator.serviceWorker.register("/web/sw.js").catch(()=>{});

  loadAppConfig();
  if(state.token && state.user) showApp();
});

window.openChat=openChat;

window.showNewGroup=showNewGroup;
