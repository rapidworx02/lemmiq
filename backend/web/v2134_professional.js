/* V21354_CREATOR_AUTOPUBLISH */
/* LEMMIQ V2.13.4 — personal vs professional identities, separate creator threads. */
(()=>{
 'use strict';
 const by=id=>document.getElementById(id);
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const apiPro=(route,options={})=>api('/v2134'+route,options);
 const post=(route,data={})=>apiPro(route,{method:'POST',body:JSON.stringify(data)});
 const key=()=>crypto.randomUUID();
 let selectedThread=null,tab='inbox',query='',proMe=null,busy=false,poll=null;
 const host=()=>by('v2134Page');
 const toastPro=(message,bad=false)=>typeof toast==='function'?toast(message,bad):alert(message);
 const time=v=>{try{return new Date(v).toLocaleString()}catch{return v||''}};
 const profileLabel=c=>`${esc(c.stage_name||'Creator')} <small>@${esc(c.handle||'')}</small>`;
 const cardAvatar=c=>c?.avatar_url?`<img src="${esc(c.avatar_url)}" class="v2134-avatar" alt="Professional avatar">`:'<span class="v2134-avatar">✦</span>';
 const terms=p=>p?`${p.fan_sent}/${p.max_messages} fan messages · ${p.creator_sent}/${p.max_messages} creator replies · ${esc(p.status)}`:'No paid chat pass active';
 function shell(){
   if(by('view-professional-inbox'))return;
   const v=document.createElement('section');v.id='view-professional-inbox';v.className='view';v.innerHTML='<div id="v2134Page"></div>';
   (by('view-q-creators')||by('view-more'))?.after(v);
   // V300: one chat navigation bar.
   const more=by('view-more')?.querySelector('.more-grid');if(more&&!by('v2134MoreInbox')){
     const b=document.createElement('button');b.id='v2134MoreInbox';b.className='more-card';
     b.innerHTML='<span>✦</span><strong>Creator Inbox</strong><small>Professional chat identity and paid fan messages</small>';
     b.onclick=()=>open();more.prepend(b);
   }
 }
 function open(nextTab='inbox'){
   shell();tab=nextTab;selectedThread=null;
   setView('professional-inbox');refresh();
 }
 window.openCreatorProfessionalInbox=open;
 function fail(e){toastPro(e?.message||String(e),true)}
 async function refresh(){
   if(!host()||!by('view-professional-inbox')?.classList.contains('active')||busy)return;
   busy=true;const root=host();root.innerHTML='<div class="v2134-loading">Loading professional conversations…</div>';
   try{
     proMe=await apiPro('/me');
     if(selectedThread){const data=await apiPro('/chats/'+encodeURIComponent(selectedThread));renderThread(data)}
     else if(tab==='inbox')renderInbox(await apiPro('/inbox'));
     else if(tab==='requests')renderRequests(await apiPro('/requests'));
     else if(tab==='discover')renderDiscover(await apiPro('/discover?'+new URLSearchParams({qtext:query})));
     else if(tab==='identity')renderIdentity();
   }catch(e){root.innerHTML='<div class="v2134-error">'+esc(e.message)+'</div>'}finally{busy=false}
 }
 function head(title,subtitle=''){
   return `<div class="v2134-head"><div><span class="eyebrow">LEMMIQ · SEPARATE PROFESSIONAL IDENTITY</span><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div><button type="button" class="ghost" data-v2134="personal">← Creators</button></div>`;
 }
 function tabs(){return `<nav class="v2134-tabs" aria-label="Professional navigation">${[['inbox','Chats'],['requests','Requests'],['identity','Professional settings']].map(([k,v])=>`<button type="button" data-v2134-tab="${k}" class="${tab===k?'active':''}">${v}</button>`).join('')}</nav>`}
 function renderInbox(rows){
   host().innerHTML=head('Creator Inbox','Separate from your personal LEMMIQ conversations.')+tabs()+
    `<div class="v2134-stack">${rows.map(c=>`<button class="v2134-thread-card" type="button" data-v2134-thread="${esc(c.thread_id)}">${cardAvatar(c.creator)}<span><strong>${c.role==='FAN'?profileLabel(c.creator):'Fan · '+esc(c.fan?.display_name||'LEMMIQ user')}</strong><small>${terms(c.pass)}</small></span><b>Open ›</b></button>`).join('')||'<p class="v2134-empty">No professional conversations yet. Discover a creator or accept a paid request.</p>'}</div>`;
 }
 function renderRequests(rows){
   host().innerHTML=head('Paid Creator Requests','Accept → Fan confirms → Professional chat opens. Personal chat stays private.')+tabs()+
    `<div class="v2134-stack">${rows.map(r=>{
       const status=r.status;const who=r.role==='FAN'?(r.creator?.stage_name||'Creator'):(r.fan?.display_name||'Fan');
       let actions='';
       if(r.role==='CREATOR'&&status==='REQUESTED')actions+=`<button class="primary" data-v2134-action="accept" data-id="${r.id}">Accept</button>`;
       if(r.role==='FAN'&&status==='ACCEPTED')actions+=`<button class="primary" data-v2134-action="confirm" data-id="${r.id}">Confirm & Start Chat</button>`;
       if(['REQUESTED','ACCEPTED'].includes(status))actions+=`<button class="ghost" data-v2134-action="cancel" data-id="${r.id}">Cancel / refund</button>`;
       if(status==='ACTIVE'&&!r.thread_id&&r.role==='FAN')actions+=`<button class="primary" data-v2134-action="confirm" data-id="${r.id}">Move active pass to Professional Chat</button>`;
       if(status==='DELIVERED'&&r.role==='FAN')actions+=`<button class="primary" data-v2134-action="legacy-confirm" data-id="${r.id}">Confirm earlier reply and release Q</button>`;
       if(r.thread_id||status==='COMPLETED')actions+=`<button class="ghost" data-v2134-action="openRequest" data-id="${r.id}">${r.thread_id?'Open Professional Chat':'View Previous Reply'}</button>`;
       return `<article class="v2134-request"><strong>${esc(who)} · ${esc(status)}</strong><small>${Number(r.amount_q||0)} Q · ${time(r.created_at)}</small><p>${esc(r.message)}</p>${r.pass?`<small>${terms(r.pass)}</small>`:''}<div class="v2134-actions">${actions}</div></article>`;
     }).join('')||'<p class="v2134-empty">No paid requests.</p>'}</div>`;
 }
 function renderDiscover(rows){
   host().innerHTML=head('Discover Creators','Only professional stage names and creator usernames are shown.')+tabs()+
    `<div class="v2134-search"><input id="v2134Search" type="search" placeholder="Search @creator" value="${esc(query)}"><button type="button" class="ghost" data-v2134="search">Search</button></div>
    <div class="v2134-stack">${rows.map(c=>`<article class="v2134-thread-card">${cardAvatar(c)}<span><strong>${profileLabel(c)}</strong><small>${esc(c.category)} · ${Number(c.chat_q||0)} Q per chat pass</small><p>${esc(c.bio||'')}</p></span><button class="primary" data-v2134-request="${esc(c.public_id)}" data-price="${Number(c.chat_q||0)}" ${!c.chat_q?'disabled':''}>Request Chat</button></article>`).join('')||'<p class="v2134-empty">No approved creators with professional usernames yet.</p>'}</div>`;
 }
 function renderIdentity(){
   const x=proMe?.identity||{};const t=proMe?.terms||{};
   host().innerHTML=head('Professional Profile','One login, two separate usernames and inboxes.')+tabs()+
   `<div class="v2134-stack"><article class="v2134-request"><h3>${x.handle?'@'+esc(x.handle):'Set up your creator username'}</h3><p>Your creator display name and photo are different from your personal LEMMIQ profile. They never copy automatically.</p>
      <p class="micro">Creator approval: ${esc(proMe?.creator_status||'Apply in Q Creators Studio first')} · Professional chat is moderated under LEMMIQ policies.</p>
      <form id="v2134IdentityForm"><label>Creator username<input name="handle" minlength="3" maxlength="32" required placeholder="studio_nova" value="${esc(x.handle||'')}"></label><label>Professional display name<input name="stage_name" minlength="2" maxlength="80" required placeholder="Nova Studio" value="${esc(x.stage_name||'')}"></label><button class="primary" type="submit">Save Professional Identity</button></form>
      ${x.public_id?`<form id="v2134AvatarForm"><label>Professional photo (separate from personal)<input type="file" name="file" accept="image/jpeg,image/png,image/webp" required></label><button class="ghost" type="submit">Upload creator avatar</button></form>`:''}</article>
      <article class="v2134-request"><h3>Paid Chat Package</h3><form id="v2134TermsForm"><label>Fan messages + creator replies per pass<input type="number" name="messages" min="1" max="25" value="${Number(t.messages||3)}"></label><label>Validity in hours<input type="number" name="hours" min="1" max="168" value="${Number(t.hours||48)}"></label><button class="primary" type="submit">Save chat terms</button></form><p class="micro">The creator's Q price is configured in Q Creators → Creator Studio.</p>${proMe?.creator_status==='APPROVED'?'<button type="button" class="ghost" data-v21341="manager">🖼 Open My Media Library & Gallery</button>':''}</article></div>`;
 }
 function renderThread(data){
   const isCreator=data.role==='CREATOR',title=isCreator?'Fan · '+(data.fan?.display_name||'LEMMIQ user'):data.creator.stage_name;
   // V21342_CHAT_EXPLANATIONS: status ACTIVE does not mean unlimited messaging.
    const p=data.pass,active=p?.status==='ACTIVE';
    const fanLeft=Math.max(0,Number(p?.fan_remaining||0));
    const creatorOwed=Math.max(0,Number(p?.creator_remaining||0));
    const allowed=!!(active&&(isCreator?creatorOwed>0:fanLeft>0));
    const canFinish=!!(active&&!isCreator&&Number(p.fan_sent)>0&&Number(p.creator_sent)>0&&Number(p.creator_sent)===Number(p.fan_sent));
    const reason=active?(isCreator?(creatorOwed===0?'Waiting for the fan to send the next message.':'Reply to the remaining '+creatorOwed+' message(s).'):
       (fanLeft===0?'You have sent all '+p.max_messages+' messages in this pass. '+(creatorOwed?'Waiting for '+creatorOwed+' creator reply/replies.':'All replies received: complete this pass to request another.'):'You can still send '+fanLeft+' message(s).')):
       (p?.status==='EXPIRED'?'Your paid chat pass expired.':'Your paid chat pass is completed or no longer active.');
   host().innerHTML=head(title,isCreator?'Professional Creator Inbox · @'+data.creator.handle:'Professional chat · @'+data.creator.handle)+
    `<div class="v2134-thread-menu"><button class="ghost" data-v2134="back">‹ Inbox</button><span>✦ ${active?'Paid pass active':'Read-only professional history'} · ${terms(p)}</span></div>
    <div class="v2134-messages" id="v2134Messages">${(data.messages||[]).map(m=>{
      const own=(isCreator?m.role==='CREATOR':m.role==='FAN');
      if(m.kind==='DIRECT_MEDIA'&&m.media)return window.v2135MediaCard?.(m,own)||'';
      if(m.kind==='OFFER'&&m.offer){const o=m.offer;return `<div class="v2134-bubble ${own?'mine':''}"><strong>🔒 Exclusive ${esc(o.kind)}</strong><p>${esc(o.title)}</p>${o.unlocked?'<small>Unlocked in your Exclusive Gallery</small>':`<button class="primary" data-v2134-action="unlock" data-id="${o.id}" data-price="${o.price_q}">Unlock ${o.price_q} Q</button>`}</div>`}
      return `<div class="v2134-bubble ${own?'mine':''}">${esc(m.body)}<small>${time(m.created_at)}</small></div>`
    }).join('')||'<p class="v2134-empty">Chat will begin when the fan sends their first included message.</p>'}</div>
    ${allowed?`<form class="v2134-composer" id="v2134MessageForm"><input name="text" maxlength="4000" placeholder="${isCreator?'Reply as @'+data.creator.handle:'Message the professional creator'}" required><button class="primary">Send</button></form>`:
    `<div class="v2134-locked" role="status">🔒 ${esc(reason)} ${!active&&!isCreator?'<button class="ghost" data-v2134="requestAgain">Request another chat pass</button>':''}</div>`}
     ${canFinish?'<div class="v2134-early-finish"><small>You may close this pass after receiving the replies owed so far. This releases the agreed Q payment and lets you request another pass.</small><button class="ghost" type="button" data-v2134="finish">Complete paid chat</button></div>':''}
    ${isCreator?`<div class="v2134-offer"><strong>Send exclusive photos, videos or albums</strong><p class="micro">Choose existing published creator content or send new media immediately. Admin can audit or remove content afterwards. Personal Chats are never used.</p><button type="button" class="primary" data-v21341="picker">🖼 Choose from My Gallery / Upload</button></div>`:''}`;
   window.v2135RefreshThread=()=>refresh();
   if(window.v2135SetupThread)window.v2135SetupThread(data);
   const sc=by('v2134Messages');if(sc)sc.scrollTop=sc.scrollHeight;
 }
 async function requestNew(publicId,price){
   const msg=prompt('Message to creator (minimum 3 characters):','Hello! I would like to chat.');
   if(!msg||msg.trim().length<3)return;
   if(!confirm(`Reserve ${Number(price)} Q to request a professional chat? The creator must accept before you can start.`))return;
   try{await post(`/profiles/${encodeURIComponent(publicId)}/requests`,{message:msg.trim(),request_key:key()});toastPro('Request submitted. Q reserved.');selectedThread=null;tab='requests';refresh()}catch(e){fail(e)}
 }
 async function click(ev){
   const b=ev.target.closest('button');if(!b||!host()?.contains(b))return;
   // V21341_VISUAL_PICKER: use authenticated professional chat, never personal Chat IDs.
   if(b.dataset.v21341==='picker'){
     if(!selectedThread)return toastPro('Open a professional thread first.',true);
     return window.LEMMIQCreatorGalleryV21341?.openPicker(selectedThread,()=>refresh());
   }
   if(b.dataset.v21341==='manager')return window.LEMMIQCreatorGalleryV21341?.openManager();
   if(b.dataset.v2134Tab){tab=b.dataset.v2134Tab;selectedThread=null;return refresh()}
   if(b.dataset.v2134==='personal')return setView('q-creators');
   if(b.dataset.v2134==='back'){selectedThread=null;tab='inbox';return refresh()}
   if(b.dataset.v2134==='search'){query=by('v2134Search')?.value.trim()||'';return refresh()}
    if(b.dataset.v2134==='finish'){
      if(!selectedThread)return;
      if(!confirm('Confirm this professional chat was delivered? The reserved Q will be settled and your pass closed.'))return;
      try{await post('/chats/'+encodeURIComponent(selectedThread)+'/complete',{});toastPro('Chat completed. You can request another paid pass.');return refresh()}catch(e){return fail(e)}
    }
   if(b.dataset.v2134==='requestAgain'){
     const d=await apiPro('/chats/'+encodeURIComponent(selectedThread));
     return requestNew(d.creator.public_id,(await apiPro('/profiles/'+encodeURIComponent(d.creator.public_id))).profile.chat_q);
   }
   if(b.dataset.v2134Thread){selectedThread=b.dataset.v2134Thread;return refresh()}
   if(b.dataset.v2134Request)return requestNew(b.dataset.v2134Request,b.dataset.price);
   const action=b.dataset.v2134Action;if(!action)return;
   b.disabled=true;
   try{
     const rid=Number(b.dataset.id);
     if(action==='unlock'){
       if(!confirm(`Unlock this content for ${b.dataset.price} Q?`))return;
       await post(`/offers/${rid}/unlock`,{request_key:key()});return refresh();
     }
     if(action==='confirm'&&!confirm('Start paid professional chat? Your message allowance and validity start now.'))return;
     if(action==='cancel'&&!confirm('Cancel this pending request and refund reserved Q?'))return;
     if(action==='legacy-confirm'&&!confirm('Confirm receipt of the earlier paid reply and release the held Q?'))return;
     const route=action==='openRequest'?'open':action;
     const r=await post(`/requests/${rid}/${route}`);
     if(action==='legacy-confirm'){const history=await post(`/requests/${rid}/open`);selectedThread=history.thread_id;tab='inbox';return refresh();}
     if(r.thread_id){selectedThread=r.thread_id;tab='inbox'}
     await refresh();
   }catch(e){fail(e)}finally{b.disabled=false}
 }
 async function submit(ev){
   const f=ev.target;if(!host()?.contains(f)||!f.id.startsWith('v2134'))return;
   ev.preventDefault();const data=Object.fromEntries(new FormData(f));const b=f.querySelector('button[type=submit]');if(b)b.disabled=true;
   try{
     if(f.id==='v2134IdentityForm'){await apiPro('/me',{method:'PUT',body:JSON.stringify(data)});toastPro('Professional username saved');}
     else if(f.id==='v2134TermsForm'){await apiPro('/me/terms',{method:'PUT',body:JSON.stringify({messages:Number(data.messages),hours:Number(data.hours)})});toastPro('Chat terms saved')}
     else if(f.id==='v2134AvatarForm'){await apiPro('/me/avatar',{method:'POST',body:new FormData(f)});toastPro('Professional photo updated')}
     else if(f.id==='v2134MessageForm'){await post(`/chats/${encodeURIComponent(selectedThread)}/messages`,{text:String(data.text||'').trim()})}
     else if(f.id==='v2134OfferForm'){await post(`/chats/${encodeURIComponent(selectedThread)}/offers`,{item_id:Number(data.item_id),price_q:Number(data.price_q),request_key:key()});toastPro('Locked media offer sent')}
     await refresh();
   }catch(e){fail(e)}finally{if(b)b.disabled=false}
 }
 function extendLegacyCreators(){
   const root=by('v213CreatorsApp');if(!root)return;
   // The old Requests tab would offer legacy personal-chat actions. Route to new professional inbox.
   root.addEventListener('click',ev=>{
     const b=ev.target.closest('button[data-mode="requests"]');
     if(b){ev.preventDefault();ev.stopImmediatePropagation();open('requests');return}
     const chatBtn=ev.target.closest('button[data-service="CHAT"]');
     if(chatBtn){ev.preventDefault();ev.stopImmediatePropagation();
       const handle=root.querySelector('.v213-profile-identity small')?.textContent?.match(/@([a-z0-9_.]+)/i)?.[1];
       if(!handle)return toastPro('Creator professional username is not available.',true);
       apiPro('/discover?qtext='+encodeURIComponent(handle)).then(xs=>{
         const x=xs.find(y=>y.handle===handle);if(!x)throw Error('Professional profile not available');
         requestNew(x.public_id,x.chat_q)
       }).catch(fail);
     }
   },true);
   const observer=new MutationObserver(()=>{
     if(root.querySelector('.v304-studio-nav [data-mode="studio"].active')&&!by('v2134StudioIdentityLink')){
       const toolbar=document.createElement('div');toolbar.id='v2134StudioIdentityLink';toolbar.className='v2134-studio-link';
       toolbar.innerHTML='<strong>Professional identity is separate from your personal username.</strong><button class="primary" type="button" id="v2134OpenIdentity">Set professional username, photo & chat rules</button>';
       const main=root.querySelector('.v213-main');if(main)main.prepend(toolbar);
       by('v2134OpenIdentity').onclick=()=>open('identity');
     }
   });observer.observe(root,{childList:true,subtree:false});
 }
 function setup(){shell();extendLegacyCreators();document.addEventListener('click',click);document.addEventListener('submit',submit);
   poll=setInterval(()=>{if(by('view-professional-inbox')?.classList.contains('active')&&(selectedThread||tab==='requests')&&document.visibilityState==='visible'&&!document.activeElement?.closest('form'))refresh()},25000);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
})();
// V300_INSTALLED
// V304_INSTALLED
