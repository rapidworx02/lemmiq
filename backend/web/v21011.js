/* LEMMIQ V2.10.11 — consolidated browser/PWA UX + performance fixes */
(()=>{
  const VERSION="2.10.11";
  const photoUrls=new Map();
  let oldestDirectHasMore=false,oldestGroupHasMore=false,preserveDirectScroll=false,preserveGroupScroll=false;
  const $id=id=>document.getElementById(id);

  function setTheme(theme){
    const t=theme==="dark"?"dark":"light";
    document.documentElement.dataset.lemmiqTheme=t;
    localStorage.setItem("lemmiq_theme",t);
    document.querySelectorAll("[data-v211-theme]").forEach(b=>b.textContent=t==="dark"?"☀ Light mode":"🌙 Dark mode");
  }
  setTheme(localStorage.getItem("lemmiq_theme")||"light");

  function inboxStamp(iso){
    if(!iso)return "";
    const d=new Date(iso);if(Number.isNaN(d.getTime()))return "";
    const now=new Date();
    const a=new Date(d.getFullYear(),d.getMonth(),d.getDate());
    const b=new Date(now.getFullYear(),now.getMonth(),now.getDate());
    const diff=Math.round((b-a)/86400000);
    if(diff===0)return d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});
    if(diff===1)return "Yesterday";
    if(diff>1&&diff<7)return d.toLocaleDateString([],{weekday:"long"});
    return d.toLocaleDateString([],{day:"numeric",month:"numeric",year:"2-digit"});
  }

  function isImageAttachment(a){
    if(!a||!a.media_id)return false;
    const mime=String(a.mime_type||"").toLowerCase();
    const name=String(a.name||"").toLowerCase();
    return mime.startsWith("image/") || ["PHOTO","IMAGE"].includes(String(a.kind||"").toUpperCase()) || /\.(jpe?g|png|webp|gif)$/i.test(name);
  }
  function escAttr(v){return escapeHtml(String(v??"")).replace(/`/g,"&#96;")}
  function photoPlaceholder(mid,isGroup,name){
    const key=(isGroup?"g":"d")+mid;
    return `<button class="v211-photo-wrap" data-v211-photo="${key}" data-mid="${mid}" data-group="${isGroup?1:0}" data-name="${escAttr(name||"photo")}" type="button"><span class="v211-photo-loading">Loading photo…</span></button>`;
  }
  function releasePhotoUrls(){
    for(const u of photoUrls.values())try{URL.revokeObjectURL(u)}catch{}
    photoUrls.clear();
  }
  async function hydratePhotos(root=document){
    const nodes=[...root.querySelectorAll("[data-v211-photo]")];
    await Promise.all(nodes.map(async el=>{
      if(el.dataset.loaded==="1")return;
      el.dataset.loaded="1";
      const mid=Number(el.dataset.mid),isGroup=el.dataset.group==="1";
      try{
        const r=await fetch(isGroup?`/v24/group-media/${mid}`:`/media/${mid}`,{headers:authHeaders()});
        if(!r.ok)throw new Error(`HTTP ${r.status}`);
        const blob=await r.blob();
        const url=URL.createObjectURL(blob);photoUrls.set(el.dataset.v211Photo,url);
        const img=document.createElement("img");img.className="v211-photo";img.alt=el.dataset.name||"Photo";img.loading="lazy";img.src=url;
        el.innerHTML="";el.appendChild(img);el.onclick=()=>openPhotoViewer(url,img.alt);
      }catch(e){
        el.innerHTML=`<span class="v211-photo-failed">📎 ${escapeHtml(el.dataset.name||"Photo")} · preview unavailable</span>`;
        el.onclick=()=>isGroup?downloadGroupMedia(mid,el.dataset.name||"photo"):downloadMedia(mid,el.dataset.name||"photo");
      }
    }));
  }
  function openPhotoViewer(url,alt="Photo"){
    const wrap=document.createElement("div");wrap.className="v211-viewer";wrap.tabIndex=0;
    wrap.innerHTML=`<button class="v211-viewer-close" aria-label="Close">×</button><img src="${escAttr(url)}" alt="${escAttr(alt)}">`;
    const close=()=>wrap.remove();wrap.querySelector("button").onclick=close;wrap.onclick=e=>{if(e.target===wrap)close()};
    const key=e=>{if(e.key==="Escape"){close();document.removeEventListener("keydown",key)}};document.addEventListener("keydown",key);document.body.appendChild(wrap);wrap.focus();
  }

  // Replace chat-list renderer to add local WhatsApp-style timestamps while retaining filters/unread.
  if(typeof renderChats==="function")renderChats=function(){
    const query=($id("chatFilter")?.value||"").toLowerCase().trim();
    let rows=[
      ...state.chats.map(c=>({kind:"chat",data:c,updated:c.updated_at||"",unread:c.unread||0,pinned:!!c.pinned,hay:`${c.other_user.display_name} ${c.other_user.username} ${c.last_message||""} ${c.draft_text||""}`.toLowerCase()})),
      ...state.groups.map(g=>({kind:"group",data:g,updated:g.updated_at||"",unread:g.unread||0,pinned:false,hay:`${g.name} ${g.last_message||""} ${(g.members||[]).map(m=>m.username).join(" ")}`.toLowerCase()}))
    ];
    rows=rows.filter(r=>r.hay.includes(query));
    if(state.chatFilterMode==="UNREAD")rows=rows.filter(r=>r.unread>0);
    if(state.chatFilterMode==="GROUPS")rows=rows.filter(r=>r.kind==="group");
    rows.sort((a,b)=>(Number(b.pinned)-Number(a.pinned))||(new Date(b.updated)-new Date(a.updated)));
    const el=$id("conversationList");if(!el)return;
    const qp=(state.qThread?.items||[])[0],qHay=`q lemmiq assistant ${qp?.title||""} ${qp?.body||""}`.toLowerCase();
    const qVisible=state.chatFilterMode!=="GROUPS"&&(state.chatFilterMode!=="UNREAD"||Number(state.qThread?.unread_count||0)>0)&&qHay.includes(query);
    const qRow=qVisible?`<button class="chat-row q-thread-row" onclick="openQThread()"><span class="avatar q-thread-avatar">Q</span><span class="body"><strong>Q · LEMMIQ Assistant</strong><small>${escapeHtml(qp?.body||"Q requests, results and coordination updates")}</small></span><span class="v211-chat-side ${state.qThread?.unread_count?"unread":""}"><time class="v211-chat-time">${escapeHtml(inboxStamp(qp?.created_at||""))}</time>${state.qThread?.unread_count?`<span class="badge">${state.qThread.unread_count}</span>`:""}</span></button>`:"";
    const normal=rows.map(r=>{
      if(r.kind==="group"){
        const g=r.data,av=g.photo_url?`<span class="avatar"><img src="${escAttr(g.photo_url)}" alt=""></span>`:`<span class="avatar">${escapeHtml(initials(g.name))}</span>`;
        return `<button class="chat-row ${state.activeGroup?.id===g.id?"active":""}" onclick="openGroup(${g.id})">${av}<span class="body"><strong>${escapeHtml(g.name)}</strong><small>${g.member_count} members · ${escapeHtml(g.last_message||"New group")}</small></span><span class="v211-chat-side ${g.unread?"unread":""}"><time class="v211-chat-time">${escapeHtml(inboxStamp(g.updated_at))}</time>${g.unread?`<span class="badge">${g.unread}</span>`:""}</span></button>`;
      }
      const c=r.data,draft=c.draft_text?`Draft: ${c.draft_text}`:(c.last_message||"Start chatting");
      return `<button class="chat-row ${state.activeChat?.id===c.id?"active":""}" onclick="openChat(${c.id})">${avatarHtml(c.other_user)}<span class="body"><strong>${c.pinned?"📌 ":""}${c.favourite?"⭐ ":""}${escapeHtml(c.other_user.display_name)}</strong><small>${escapeHtml(draft)}</small></span><span class="v211-chat-side ${c.unread?"unread":""}"><time class="v211-chat-time">${escapeHtml(inboxStamp(c.updated_at))}</time>${c.unread?`<span class="badge">${c.unread}</span>`:""}</span></button>`;
    }).join("");
    el.innerHTML=qRow+(normal||(!qRow?`<div class="empty-state"><p>No matching conversations.</p></div>`:""));
  };

  // Latest-first paginated browser chat load. Existing Android calls remain backward compatible.
  if(typeof openChat==="function")openChat=async function(cid,mark=true){
    let chat=state.chats.find(x=>x.id===cid);if(!chat){await loadChats();chat=state.chats.find(x=>x.id===cid)}if(!chat)return;
    state.activeGroup=null;state.activeChat=chat;state.replyTo=null;releasePhotoUrls();
    $id("globalQOrb")?.classList.add("q2106-hide-orb");
    const [messages,calls]=await Promise.all([api(`/chats/${cid}/messages?limit=60`),api(`/v24/chats/${cid}/calls`).catch(()=>[])]);
    state.messages=messages;state.chatCalls=calls;oldestDirectHasMore=messages.length===60;
    if(mark)api(`/chats/${cid}/read`,{method:"POST"}).catch(()=>{});
    $id("emptyChat")?.classList.add("hidden");$id("activeQThread")?.classList.add("hidden");$id("activeGroup")?.classList.add("hidden");$id("activeChat")?.classList.remove("hidden");
    $id("chatName").textContent=chat.other_user.display_name;$id("chatMeta").textContent=`@${chat.other_user.username} · ${chat.category} · AI ${chat.ai_mode}`;
    $id("chatAvatar").innerHTML=chat.other_user.avatar_url?`<img src="${escAttr(chat.other_user.avatar_url)}" alt="">`:escapeHtml(initials(chat.other_user.display_name));
    $id("assistBar")?.classList.toggle("hidden",chat.ai_mode!=="ASSIST");$id("messageInput").value=chat.draft_text||"";clearReplyPreview();document.querySelector(".chat-layout")?.classList.add("open-chat");renderMessages();renderChats();
    if(mark&&location.hash!==`#chat-${cid}`)history.pushState({view:"chats",chatId:cid},"",`#chat-${cid}`);
  };

  window.v211LoadOlderDirect=async function(){
    if(!state.activeChat||!state.messages?.length)return;const first=state.messages[0]?.id;if(!first)return;
    const host=$id("messageList"),oldHeight=host?.scrollHeight||0;
    const rows=await api(`/chats/${state.activeChat.id}/messages?limit=60&before=${first}`);oldestDirectHasMore=rows.length===60;
    const known=new Set(state.messages.map(x=>x.id));state.messages=[...rows.filter(x=>!known.has(x.id)),...state.messages];preserveDirectScroll=true;renderMessages();
    requestAnimationFrame(()=>{if(host)host.scrollTop=Math.max(0,host.scrollHeight-oldHeight)});
  };

  if(typeof renderMessages==="function")renderMessages=function(){
    const me=state.user?.id,items=[];(state.messages||[]).forEach(m=>items.push({type:"message",at:m.created_at,m}));(state.chatCalls||[]).forEach(c=>items.push({type:"call",at:c.started_at,c}));items.sort((a,b)=>new Date(a.at)-new Date(b.at));
    let lastDay="",html=oldestDirectHasMore?`<button class="ghost v211-load-older" onclick="v211LoadOlderDirect()">Load older messages</button>`:"";
    for(const item of items){
      const day=friendlyDay(item.at);if(day!==lastDay){html+=`<div class="date-separator"><span>${escapeHtml(day)}</span></div>`;lastDay=day}
      if(item.type==="call"){const c=item.c,kind=String(c.call_type||"VOICE").toUpperCase()==="VIDEO"?"video call":"voice call",label=c.status==="MISSED"?`Missed ${kind}`:c.status==="DECLINED"?`${kind[0].toUpperCase()+kind.slice(1)} · declined`:c.status==="RINGING"?`${kind[0].toUpperCase()+kind.slice(1)} · no answer`:(kind[0].toUpperCase()+kind.slice(1)),detail=c.duration_seconds?`${formatDuration(c.duration_seconds)} · ${timeOnly(c.started_at)}`:timeOnly(c.started_at);html+=`<div class="msg call-event"><strong>📞 ${label}</strong><div class="micro">${detail}</div></div>`;continue}
      const m=item.m,mine=m.sender_id===me,a=m.attachment;let attach="";
      if(a?.kind==="CONTACT")attach=`<div class="answer-box">👤 <strong>${escapeHtml(a.contact_name)}</strong><br><small>${escapeHtml(a.contact_phone)}</small></div>`;
      else if(a?.kind==="VOICE")attach=`<div class="voice-note"><button class="mini" onclick="loadVoice(${m.id},false,this)">▶ ${Math.round((a.duration_ms||0)/1000)}s</button><button class="mini" onclick="voiceAI(${m.id})">Q</button></div>${a.transcript?`<div class="micro">Transcript: ${escapeHtml(a.transcript)}</div>`:""}`;
      else if(isImageAttachment(a))attach=photoPlaceholder(m.id,false,a.name||"photo");
      else if(a?.media_id)attach=`<button class="mini" onclick="downloadMedia(${m.id},'${escAttr((a.name||"file").replace(/'/g,""))}')">📎 ${escapeHtml(a.name||a.kind)}</button>`;
      const quote=m.reply_to?`<div class="reply-quote">${escapeHtml(m.reply_to.text||"")}</div>`:"",reactions=(m.reactions||[]).map(r=>`<button class="reaction-pill" onclick="reactMessage(${m.id},'${escAttr(r.emoji)}')">${escapeHtml(r.emoji)} ${r.count}</button>`).join("");
      html+=`<div class="msg ${mine?"mine":"theirs"}" data-mid="${m.id}"><button class="mini msg-action-trigger message-menu" onclick="openMessageMenu(${m.id})">⋯</button>${m.ai_generated?`<div class="micro">✨ AI generated</div>`:""}${quote}<div>${escapeHtml(m.text).replace(/\n/g,"<br>")}${m.edited_at?`<span class="edited-tag"> edited</span>`:""}</div>${attach}${reactions?`<div class="reaction-strip">${reactions}</div>`:""}${!mine&&!m.deleted_for_everyone?`<div class="msg-actions"><button class="mini" onclick="checkMessage(${m.id})">🛡 Fact / Scam Check</button></div>`:""}<div class="meta"><span>${timeOnly(m.created_at)}</span>${mine?`<span>${m.read_at?"✓✓":"✓"}</span>`:""}</div></div>`;
    }
    $id("messageList").innerHTML=html;hydratePhotos($id("messageList"));
    if(preserveDirectScroll)preserveDirectScroll=false;else setTimeout(()=>$id("messageList").scrollTop=$id("messageList").scrollHeight,20);
  };

  if(typeof openGroup==="function")openGroup=async function(gid,pushHistory=true){
    state.activeChat=null;state.replyTo=null;releasePhotoUrls();$id("globalQOrb")?.classList.add("q2106-hide-orb");
    const [g,msgs]=await Promise.all([api(`/v24/groups/${gid}`),api(`/v24/groups/${gid}/messages?limit=60`)]);state.activeGroup=g;state.groupMessages=msgs;oldestGroupHasMore=msgs.length===60;await api(`/v24/groups/${gid}/read`,{method:"POST"}).catch(()=>{});
    $id("emptyChat")?.classList.add("hidden");$id("activeQThread")?.classList.add("hidden");$id("activeChat")?.classList.add("hidden");$id("activeGroup")?.classList.remove("hidden");$id("groupName").textContent=g.name;$id("groupMeta").textContent=`${g.member_count} members · Q ${g.ai_mode}`;$id("groupAvatar").innerHTML=g.photo_url?`<img src="${escAttr(g.photo_url)}" alt="">`:escapeHtml(initials(g.name));$id("groupAssistBar")?.classList.toggle("hidden",g.ai_mode!=="ASSIST");renderGroupMessages();renderChats();document.querySelector(".chat-layout")?.classList.add("open-chat");if(pushHistory&&location.hash!==`#group-${gid}`)history.pushState({view:"chats",groupId:gid},"",`#group-${gid}`);
  };
  window.v211LoadOlderGroup=async function(){
    if(!state.activeGroup||!state.groupMessages?.length)return;const first=state.groupMessages[0]?.id;if(!first)return;const host=$id("groupMessageList"),oldHeight=host?.scrollHeight||0;const rows=await api(`/v24/groups/${state.activeGroup.id}/messages?limit=60&before=${first}`);oldestGroupHasMore=rows.length===60;const known=new Set(state.groupMessages.map(x=>x.id));state.groupMessages=[...rows.filter(x=>!known.has(x.id)),...state.groupMessages];preserveGroupScroll=true;renderGroupMessages();requestAnimationFrame(()=>{if(host)host.scrollTop=Math.max(0,host.scrollHeight-oldHeight)});
  };
  if(typeof renderGroupMessages==="function")renderGroupMessages=function(){
    let day="",html=oldestGroupHasMore?`<button class="ghost v211-load-older" onclick="v211LoadOlderGroup()">Load older messages</button>`:"";const me=state.user?.id;
    for(const m of state.groupMessages){const d=friendlyDay(m.created_at);if(d!==day){html+=`<div class="date-separator"><span>${escapeHtml(d)}</span></div>`;day=d}const mine=m.sender_id===me,a=m.attachment;let attach="";if(a?.kind==="VOICE")attach=`<div class="voice-note"><button class="mini" onclick="loadVoice(${m.id},true,this)">▶ ${Math.round((a.duration_ms||0)/1000)}s</button></div>${a.transcript?`<div class="micro">Transcript: ${escapeHtml(a.transcript)}</div>`:""}`;else if(isImageAttachment(a))attach=photoPlaceholder(m.id,true,a.name||"photo");else if(a?.media_id)attach=`<button class="mini" onclick="downloadGroupMedia(${m.id},'${escAttr((a.name||"file").replace(/'/g,""))}')">📎 ${escapeHtml(a.name||a.kind)}</button>`;html+=`<div class="msg ${mine?"mine":"theirs"}"><div class="micro">${escapeHtml(m.sender?.display_name||"Member")}</div><div>${escapeHtml(m.text)}</div>${attach}<div class="meta"><span>${timeOnly(m.created_at)}</span></div></div>`}
    $id("groupMessageList").innerHTML=html;hydratePhotos($id("groupMessageList"));
    if(preserveGroupScroll)preserveGroupScroll=false;else setTimeout(()=>$id("groupMessageList").scrollTop=$id("groupMessageList").scrollHeight,20);
  };

  // Do not refetch an entire conversation after a successful send.
  if(typeof sendMessage==="function")sendMessage=async function(){
    const input=$id("messageInput"),text=input.value.trim();if(!state.activeChat||!text)return;input.value="";
    try{const m=state.replyTo?await api(`/v24/chats/${state.activeChat.id}/reply`,{method:"POST",body:JSON.stringify({text,reply_to_message_id:state.replyTo.id})}):await api(`/chats/${state.activeChat.id}/messages`,{method:"POST",body:JSON.stringify({text})});if(m&&state.messages.every(x=>x.id!==m.id))state.messages.push(m);clearReplyPreview();await saveDraft("");renderMessages();setTimeout(()=>loadChats().catch(()=>{}),120)}catch(e){toast(e.message,true)}
  };
  if(typeof sendGroupMessage==="function")sendGroupMessage=async function(){const input=$id("groupMessageInput"),text=input.value.trim();if(!text||!state.activeGroup)return;input.value="";try{const m=await api(`/v24/groups/${state.activeGroup.id}/messages`,{method:"POST",body:JSON.stringify({text})});if(m&&state.groupMessages.every(x=>x.id!==m.id))state.groupMessages.push(m);renderGroupMessages();setTimeout(()=>loadChats().catch(()=>{}),120)}catch(e){toast(e.message,true)}};

  async function enableBrowserPush(btn){
    try{
      if(!("serviceWorker" in navigator)||!("Notification" in window))throw new Error("Browser notifications are unavailable on this device");
      const cfg=await api("/app-config");if(!cfg.web_push_configured||!cfg.firebase_web_config||!cfg.firebase_web_vapid_key)throw new Error("PWA push is not configured on the server yet");
      const permission=await Notification.requestPermission();if(permission!=="granted")throw new Error("Notification permission was not allowed");
      const reg=await navigator.serviceWorker.register(`/web/sw.js?v=${VERSION}`);await navigator.serviceWorker.ready;
      if(!window.firebase?.messaging)throw new Error("Firebase Messaging did not load");
      if(!firebase.apps.length)firebase.initializeApp(cfg.firebase_web_config);
      const messaging=firebase.messaging();const token=await messaging.getToken({vapidKey:cfg.firebase_web_vapid_key,serviceWorkerRegistration:reg});if(!token)throw new Error("Browser push token was not created");
      await api("/push/register",{method:"POST",body:JSON.stringify({token:`WEB:${token}`})});
      btn.textContent="✓ Browser notifications on";toast("Browser/PWA notifications enabled");
      messaging.onMessage(payload=>{const d=payload?.data||{};toast(`${d.sender_name||d.group_name||"LEMMIQ"}: ${d.body||"New activity"}`)});
    }catch(e){toast(e.message||"Could not enable browser notifications",true)}
  }

  function injectSettings(){
    const more=document.querySelector("#view-more .more-grid");if(!more||more.querySelector(".v211-settings-card"))return;
    const card=document.createElement("article");card.className="v211-settings-card";card.innerHTML=`<strong>Appearance & notifications</strong><small>Light is the default. You can switch theme and enable native PWA notifications on this phone.</small><div class="actions"><button class="ghost" data-v211-theme></button><button class="primary" data-v211-push>Enable browser notifications</button></div>`;more.prepend(card);const theme=card.querySelector("[data-v211-theme]");theme.onclick=()=>setTheme(document.documentElement.dataset.lemmiqTheme==="dark"?"light":"dark");setTheme(document.documentElement.dataset.lemmiqTheme||"light");const push=card.querySelector("[data-v211-push]");push.onclick=()=>enableBrowserPush(push);
  }

  document.addEventListener("DOMContentLoaded",()=>{
    injectSettings();
    // Re-inject if More is rendered/updated later.
    const observer=new MutationObserver(injectSettings);observer.observe(document.body,{subtree:true,childList:true});
    if("serviceWorker" in navigator)navigator.serviceWorker.register(`/web/sw.js?v=${VERSION}`).catch(()=>{});
  });
})();
