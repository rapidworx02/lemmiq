/* V21354_CREATOR_AUTOPUBLISH */
/* LEMMIQ V2.13.1 — Creator library, galleries, chat PPV, Master Admin audit.
 * The server authorises every media request and calculates every Q debit.
 */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=x=>Number(x||0).toLocaleString(undefined,{maximumFractionDigits:6});
 const url='/v2131/exclusives';
 const call=(p,options={})=>api(url+p,options);
 const json=(m,p)=>({method:m,body:JSON.stringify(p)});
 const key=()=>crypto.randomUUID();
 const notify=(msg,error=false)=>{const n=$('v2131Notice');if(n){n.textContent=msg;n.classList.toggle('v2131-error',error)}else toast(msg,error)};
 const S={context:null,library:[],mineGallery:[],chatList:[],currentGallery:[],offers:[],adminOffset:0,isAdmin:false,adminData:null,adminQueue:null,adminLogs:null,blobs:new Set(),modalBlob:null,renderSeq:0};
 function clearModalBlob(){revokeBlobs()}
 function revokeBlobs(){for(const b of S.blobs)URL.revokeObjectURL(b);S.blobs.clear();S.modalBlob=null}
 const galleryCard=(item,own=false)=>`<article class="v2131-gallery-card" data-item="${item.id}"><div class="v2131-placeholder"><span>🔒</span><strong>${esc(item.kind)}</strong><small>${item.media_count} file${item.media_count===1?'':'s'}</small></div><h4>${esc(item.title)}</h4><p>${esc(item.teaser||'Exclusive creator media')}</p><div class="v2131-card-bottom"><span>${item.visibility==='PPV'?num(item.price_q)+' Q':'Subscriber included'}</span>${own?`<small>${esc(item.review)}</small>`:item.unlocked?`<button class="ghost" type="button" data-xaction="view" data-id="${item.id}">View</button>`:item.visibility==='PPV'?`<button class="primary" type="button" data-xaction="unlock" data-id="${item.id}">Unlock</button>`:`<small>Subscribe to view</small>`}</div>${own?`<button type="button" class="ghost" data-xaction="view" data-id="${item.id}">Preview</button>`:''}</article>`;
 const gallerySection=(items,own)=>`<section class="v2131-section" id="v2131GallerySection"><div class="v2131-title"><div><span class="eyebrow">Q CREATORS</span><h3>Exclusive Photos & Videos</h3><p class="micro">Private albums and single-media offers. Files remain locked until you qualify for access.</p></div></div><div class="v2131-gallery-grid">${items.map(x=>galleryCard(x,own)).join('')||'<p class="micro">No exclusive items published yet.</p>'}</div></section>`;
 const libraryBox=()=>{
  const approved=S.library.filter(a=>a.review==='APPROVED');const chats=S.chatList;
  return `<section class="card glass v2131-section" id="v2131CreatorTools"><div class="v2131-title"><div><span class="eyebrow">CREATOR MEDIA STUDIO</span><h3>Media Library & Exclusive Gallery</h3></div></div><p class="micro">Create individually priced photos, videos and albums. After your professional profile is approved, uploads publish immediately; reuse permitted media for gallery items and professional chat offers.</p>
   <p class="v2131-policy">Content safety: Creator uploads, including locked/private media and rejected submissions, may be accessed by authorised LEMMIQ administrators for moderation, compliance and abuse investigations. Reviews are recorded in an internal access log; individual review notifications are not sent. Explicit content is not permitted in this app.</p>
   <div class="v2131-studio-grid"><form id="v2131UploadForm" class="v2131-form"><h4>1. Upload to private library</h4><label>File name / title<input name="title" minlength="3" maxlength="140" required placeholder="My photoshoot"></label><label>Media category<select name="level"><option value="MAINSTREAM">Mainstream</option><option value="GLAMOUR">Glamour · non-explicit</option></select></label><label>Photo or video<input type="file" name="file" required accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"></label><button type="submit" class="primary">Upload to library</button></form>
   <form id="v2131PublishForm" class="v2131-form"><h4>2. Make an exclusive item</h4><label>Title<input name="title" minlength="3" maxlength="140" required placeholder="Exclusive collection"></label><label>Public teaser<input name="teaser" maxlength="240" placeholder="Short description (no private media)"></label><label>Type<select name="kind"><option value="PHOTO">Single photo</option><option value="VIDEO">Single video</option><option value="ALBUM">Photo / video album (2–20)</option></select></label><label>Access<select name="visibility"><option value="PPV">Pay to unlock</option><option value="SUBSCRIBERS">Included for subscribers</option></select></label><label>PPV price in Q (0 for subscriber included)<input name="price_q" type="number" min="0" max="100000" step="0.01" value="50" required></label><label>Available files (select 1; Ctrl-click for albums)<select name="assets" multiple size="5" required>${approved.map(a=>`<option value="${a.id}">#${a.id} ${esc(a.kind)} · ${esc(a.title)}</option>`).join('')}</select></label><button type="submit" class="primary" ${approved.length?'':'disabled'}>Publish gallery item</button></form></div>
   <details><summary>My media library (${S.library.length})</summary><div class="v2131-rows">${S.library.map(a=>`<div><span><strong>#${a.id} · ${esc(a.title)}</strong><small>${esc(a.kind)} · ${esc(a.review)}</small></span><button type="button" class="ghost" data-xaction="libraryview" data-id="${a.id}">Preview</button></div>`).join('')||'<p class="micro">No uploaded media.</p>'}</div></details>
   <details><summary>My exclusive gallery (${S.mineGallery.length})</summary><div class="v2131-gallery-grid">${S.mineGallery.map(i=>galleryCard(i,true)).join('')||'<p class="micro">No gallery items.</p>'}</div></details>
    <details><summary>Send PPV in Professional Chat</summary><p class="micro">To protect your personal identity, send PPV only through the separate Professional Inbox.</p><button class="ghost" type="button" data-xaction="professionalpicker">Open Professional Inbox</button></details>
   <p id="v2131Notice" role="status" aria-live="polite"></p></section>`;
 };
 function inboxBox(items){return `<section class="card glass v2131-section" id="v2131Inbox"><h3>Private PPV offers</h3><p class="micro">Locked photo/video offers received in your LEMMIQ conversations.</p><div class="v2131-rows">${items.map(x=>`<div><span><strong>${esc(x.title)}</strong><small>Creator #${x.creator_id} · ${num(x.price_q)} Q · ${x.unlocked?'Unlocked':'Locked'}</small></span><button class="ghost" type="button" data-xaction="offer" data-id="${x.id}">${x.unlocked?'View':'Open offer'}</button></div>`).join('')||'<p class="micro">No private offers.</p>'}</div></section>`}
 async function decorate(context){
  S.context=context;const seq=++S.renderSeq;
  const root=$('v213CreatorsApp');if(!root||!root.closest('.view'))return;
  const main=root.querySelector('.v213-main');if(!main)return;
  if(context.selected){
    const insert=document.createElement('div');insert.id='v2131Area';
    const after=root.querySelector('.v213-profile-detail');if(after)after.after(insert);else main.prepend(insert);
    try{const items=await call(`/profile/${Number(context.selected)}/gallery`);if(seq!==S.renderSeq||!insert.isConnected)return;
      S.currentGallery=items;insert.innerHTML=gallerySection(items,context.mine?.id===context.selected);
    }catch(e){if(insert.isConnected)insert.innerHTML=`<p class="micro">Exclusive gallery unavailable: ${esc(e.message)}</p>`}
  }else if(context.mode==='studio'&&context.mine?.status==='APPROVED'){
    const insert=document.createElement('div');insert.id='v2131Area';main.append(insert);
    try{// V21341_NO_PERSONAL_CHAT_LOOKUP: the old /chats endpoint returns 410 after dual-identity upgrade.
     const results=await Promise.all([call('/library'),call('/gallery/mine')]);
      if(seq!==S.renderSeq||!insert.isConnected)return;
      [S.library,S.mineGallery]=results;S.chatList=[];insert.innerHTML=libraryBox();
    }catch(e){if(insert.isConnected)insert.innerHTML=`<p class="micro">Creator library unavailable: ${esc(e.message)}</p>`}
  }else if(context.mode==='studio'){
    const insert=document.createElement('div');insert.id='v2131Area';main.append(insert);
    insert.innerHTML='<section class="v2131-section"><h3>Creator media review policy</h3><p class="v2131-policy">Uploaded creator media, including locked/private content, may be inspected by authorised administrators for safety and compliance. Each access is logged. Creators do not receive a separate alert for each authorised inspection. Explicit content remains unavailable in this app.</p></section>';
  }else if(context.mode==='discover'||context.mode==='following'){
    const insert=document.createElement('div');insert.id='v2131Area';main.append(insert);
    try{const items=await call('/offers/inbox');if(seq!==S.renderSeq||!insert.isConnected)return;
       S.offers=items;insert.innerHTML=inboxBox(items);
    }catch(e){if(insert.isConnected)insert.innerHTML=`<p class="micro">Private offers unavailable: ${esc(e.message)}</p>`}
  }
 }
 window.v2131CreatorsDecorate=decorate;
 async function mediaBlob(endpoint,el){
   const r=await fetch(url+endpoint,{headers:authHeaders()});if(!r.ok)throw Error(`Media unavailable (${r.status})`);
   const type=r.headers.get('content-type')||'';
   if(!type.startsWith('image/')&&!type.startsWith('video/'))throw Error('Unsupported media type');
   const blob=URL.createObjectURL(await r.blob());S.blobs.add(blob);
   const v=document.createElement(type.startsWith('video/')?'video':'img');v.src=blob;v.controls=type.startsWith('video/');v.style.maxWidth='100%';
   v.loading='lazy';el.appendChild(v);
 }
 async function viewItem(itemId){
   const data=await call(`/gallery/${itemId}/assets`);
   openModal(`<h3>Exclusive Media</h3><p class="micro">Private creator content — only you and authorised viewers have access.</p><div id="v2131ModalMedia" class="v2131-media-list"></div>`);
   const host=$('v2131ModalMedia');if(!host)return;
   for(const a of data){const slot=document.createElement('div');host.append(slot);try{await mediaBlob(`/gallery/${itemId}/assets/${a.id}/media`,slot)}catch(e){slot.textContent=e.message}}
 }
 function makeNoticeOfPurchase(price,title){return `Unlock ${title} for ${num(price)} Q?\nQ will be deducted from your wallet. LEMMIQ commission is taken from the creator's gross amount. Confirm?`}
 async function unlockGallery(itemId){const item=S.currentGallery.find(i=>i.id===itemId);if(!item)throw Error('Item no longer in view');
  if(!confirm(makeNoticeOfPurchase(item.price_q,item.title)))return;
  await call(`/gallery/${itemId}/unlock`,json('POST',{request_key:key()}));notify('Exclusive item unlocked');await decorate(S.context);await viewItem(itemId)}
 async function offerModal(offerId){
  const x=await call(`/offers/${offerId}`);
  openModal(`<span class="eyebrow">PRIVATE Q CREATORS OFFER</span><h3>${esc(x.title)}</h3><p>Photo/video media is locked until you unlock it. This offer was sent specifically to this chat.</p><p><strong>${x.unlocked?'Already unlocked':num(x.price_q)+' Q to unlock'}</strong></p><button type="button" id="v2131OfferConfirm" class="primary full">${x.unlocked?'Open media':'Unlock and pay Q'}</button>`);
  $('v2131OfferConfirm').onclick=async()=>{try{if(!x.unlocked){if(!confirm(makeNoticeOfPurchase(x.price_q,x.title)))return;await call(`/offers/${offerId}/unlock`,json('POST',{request_key:key()}))}closeModal();await viewItem(x.item_id);if($('messageList'))window.v2131HydrateChatOffers?.()}catch(e){toast(e.message,true)}};
 }
 async function handleAction(b){const what=b.dataset.xaction,id=Number(b.dataset.id);try{
  if(what==='view')await viewItem(id);
   if(what==='professionalpicker'){window.openCreatorProfessionalInbox?.('inbox');return}
  if(what==='unlock')await unlockGallery(id);
  if(what==='offer')await offerModal(id);
  if(what==='libraryview'){openModal('<h3>Media Library Preview</h3><div id="v2131ModalMedia"></div>');await mediaBlob(`/library/${id}/media`,$('v2131ModalMedia'))}
 }catch(e){notify(e.message,true)}}
 async function handleForm(form){const what=form.id,b=form.querySelector('[type=submit]');b.disabled=true;try{
  if(what==='v2131UploadForm'){
   const f=new FormData(form);await call('/library/upload',{method:'POST',body:f});notify('Media saved to your library. No additional approval required.');await decorate(S.context)
  }else if(what==='v2131PublishForm'){
   const f=new FormData(form);const selected=[...form.querySelector('[name=assets]').selectedOptions].map(x=>Number(x.value));
   const payload={title:f.get('title'),teaser:f.get('teaser'),kind:f.get('kind'),visibility:f.get('visibility'),price_q:Number(f.get('price_q')),asset_ids:selected};
   await call('/gallery',json('POST',payload));notify('Exclusive gallery published immediately.');await decorate(S.context)
  }else if(what==='v2131SendForm'){
   const f=new FormData(form);const chatId=Number(f.get('chat_id'));
   const itemId=Number(f.get('item_id'));const amount=Number(f.get('price_q'));
   if(!confirm(`Send a locked PPV media offer in this chat for ${num(amount)} Q?`))return;
   await call(`/chats/${chatId}/offers`,json('POST',{item_id:itemId,price_q:amount,client_key:key()}));notify('Locked PPV offer sent to chat');
  }
 }catch(e){notify(e.message,true)}finally{b.disabled=false}}
 function renderChatOffer(txt,mine){const match=String(txt||'').match(/^\[\[QCREATORS_PPV:(\d+)\]\]$/);
  if(!match)return '';return `<div class="v2131-chat-offer"><strong>🔒 Q Creators PPV media</strong><p class="micro">${mine?'Private offer sent':'Private photo/video offer received'}</p><button type="button" class="ghost" data-xaction="offer" data-id="${match[1]}">View locked offer</button></div>`;
 }
 window.v2131RenderChatOffer=renderChatOffer;
 window.v2131HydrateChatOffers=async()=>{for(const el of document.querySelectorAll('#messageList [data-xaction="offer"]')){
   const id=Number(el.dataset.id);try{const offer=await call(`/offers/${id}`);if(el.isConnected)el.textContent=offer.unlocked?'View unlocked media':`Unlock ${offer.kind.toLowerCase()} · ${num(offer.price_q)} Q`;}catch{if(el.isConnected)el.textContent='Unavailable private offer'}
 }};
 // Shortcut for the currently open LEMMIQ chat, using the same gallery/library and Q pricing.
 async function chatSendShortcut(){try{
   const active=state?.activeChat;if(!active)throw Error('Open a LEMMIQ conversation first');
   const mine=await call('/gallery/mine');const list=mine.filter(x=>x.review==='APPROVED');
   if(!list.length)throw Error('Create an approved exclusive gallery item first in Q Creators → Creator Studio');
   openModal(`<h3>Send PPV media in this chat</h3><p class="micro">Select approved exclusive content and a separate Q price.</p><label>Media<select id="v2131ChatItem">${list.map(x=>`<option value="${x.id}">#${x.id} ${esc(x.title)}</option>`).join('')}</select></label><label>Private offer price (Q)<input type="number" id="v2131ChatPrice" min="0.01" step="0.01" max="100000" value="25"></label><button id="v2131ChatSend" type="button" class="primary full">Send locked PPV</button>`);
   $('v2131ChatSend').onclick=async()=>{try{const price=Number($('v2131ChatPrice').value);if(!confirm(`Send private media for ${num(price)} Q?`))return;
    await call(`/chats/${active.id}/offers`,json('POST',{item_id:Number($('v2131ChatItem').value),price_q:price,client_key:key()}));closeModal();toast('Private PPV media sent.');
   }catch(e){toast(e.message,true)}};
 }catch(e){toast(e.message,true)}}
  window.v2131OpenChatPPV=()=>window.openCreatorProfessionalInbox?.('inbox');
 function installComposerShortcut(){if($('v2131ChatComposerButton'))return;const input=$('fileInput');const attach=input?.closest('.attach-btn');if(!attach)return;
  const btn=document.createElement('button');btn.id='v2131ChatComposerButton';btn.type='button';btn.className='ghost';btn.title='Send Q Creators PPV media';btn.textContent='🔒';btn.onclick=chatSendShortcut;attach.after(btn);attach.closest('.composer')?.classList.add('v2131-composer');
 }
 async function loadAdmin(){
  const host=document.querySelector('[data-v2124-admin-panel="creators"]');if(!host||!document.querySelector('#view-q-admin.active'))return;
  const data=await Promise.all([call(`/admin/media?limit=50&offset=${S.adminOffset}`),call('/admin/review-queue'),call('/admin/access-log')]);
  [S.adminData,S.adminQueue,S.adminLogs]=data;
  let card=$('v2131AuditCard');if(!card){card=document.createElement('article');card.id='v2131AuditCard';card.className='card glass v2131-section';host.append(card)}
  card.innerHTML=`<div class="section-head"><div><span class="eyebrow">MASTER ADMIN</span><h3>Creator Media Audit</h3><p class="micro">Inspect uploaded creator content after publication, including gallery PPV and subscriber-only content. Professional chat direct-media audits are in the adjacent audit panel. Admin viewing is recorded; creators do not receive per-view alerts. The review policy is disclosed in Creator Studio.</p></div><button type="button" class="ghost" data-xaction="adminrefresh">↻ Refresh</button></div>
   <p class="micro">No per-upload approval queue. All creator media is available for post-publication review and takedown below.</p>
   <div class="v2131-pages"><button type="button" class="ghost" data-xaction="adminprev" ${S.adminOffset===0?'disabled':''}>← Previous</button><strong>Media audit page ${Math.floor(S.adminOffset/50)+1}</strong><button type="button" class="ghost" data-xaction="adminnext" ${(S.adminData.library.length<50&&S.adminData.posts.length<50&&(S.adminData.gallery||[]).length<50)?'disabled':''}>Next →</button></div>
   <details><summary>All uploaded Media Library files (${S.adminData.library.length} loaded)</summary><div class="v2131-rows">${S.adminData.library.map(a=>`<div><span><strong>#${a.id} ${esc(a.title)}</strong><small>@${esc(a.username)} · ${esc(a.review)}</small></span><div><button type="button" class="ghost" data-xaction="adminviewasset" data-id="${a.id}">Audit view</button>${a.review==='REJECTED'?`<button type="button" class="ghost" data-xaction="reviewasset" data-id="${a.id}" data-review="APPROVE">Restore</button>`:`<button type="button" class="ghost" data-xaction="reviewasset" data-id="${a.id}" data-review="REJECT">Remove</button>`}</div></div>`).join('')}</div></details>
   <details><summary>All creator galleries (${(S.adminData.gallery||[]).length} loaded)</summary><div class="v2131-rows">${(S.adminData.gallery||[]).map(g=>`<div><span><strong>#${g.id} ${esc(g.title)}</strong><small>@${esc(g.username)} · ${esc(g.visibility)} · ${esc(g.review)} · ${num(g.price_q)} Q</small></span><div>${g.asset_ids.map(a=>`<button type="button" class="ghost" data-xaction="adminviewasset" data-id="${a}">Audit file #${a}</button>`).join('')}${g.review==='REJECTED'?`<button type="button" class="ghost" data-xaction="reviewgallery" data-id="${g.id}" data-review="APPROVE">Restore</button>`:`<button type="button" class="ghost" data-xaction="reviewgallery" data-id="${g.id}" data-review="REJECT">Remove</button>`}</div></div>`).join('')||'<p class="micro">No creator galleries yet.</p>'}</div></details>
   <details><summary>All legacy creator-post media (${S.adminData.posts.length} loaded)</summary><div class="v2131-rows">${S.adminData.posts.map(p=>`<div><span><strong>#${p.id} ${esc(p.title)}</strong><small>@${esc(p.username)} · ${esc(p.visibility)} · ${esc(p.review)}</small></span><button type="button" class="ghost" data-xaction="adminviewpost" data-id="${p.id}">Audit view</button></div>`).join('')}</div></details>
   <details><summary>Master Admin media access log (${S.adminLogs.length} loaded)</summary><div class="v2131-rows">${S.adminLogs.map(x=>`<div><span><strong>${esc(x.source_type)} #${x.source_id}</strong><small>Admin #${x.admin_id} · Creator #${x.creator_id} · ${esc(x.accessed_at)}</small></span></div>`).join('')||'<p class="micro">No admin reads yet.</p>'}</div></details>
   <p id="v2131AuditNote" class="micro" role="status" aria-live="polite"></p>`;
 }
 async function adminAction(b){const act=b.dataset.xaction,id=Number(b.dataset.id);
  try{
   if(act==='adminrefresh')return loadAdmin();
   if(act==='adminprev'){S.adminOffset=Math.max(0,S.adminOffset-50);return loadAdmin()}
   if(act==='adminnext'){S.adminOffset+=50;return loadAdmin()}
   if(act==='adminviewasset'||act==='adminviewpost'){
    if(!confirm('Open this creator media for an authorised safety/compliance audit? This access will be logged.'))return;
    openModal('<h3>Authorised creator media review</h3><p class="micro">Internal access is logged for accountability.</p><div id="v2131ModalMedia"></div>');
    await mediaBlob(act==='adminviewasset'?`/admin/assets/${id}/media`:`/admin/posts/${id}/media`,$('v2131ModalMedia'));
    return loadAdmin();
   }
   if(act==='reviewasset'||act==='reviewgallery'){
    const reason=prompt('Moderation reason (at least 8 characters):');if(reason===null)return;
    if(reason.trim().length<8)throw Error('Reason must be at least 8 characters');
    if(!confirm(`Confirm ${b.dataset.review} of item #${id}?`))return;
    await call(act==='reviewasset'?`/admin/assets/${id}/review`:`/admin/gallery/${id}/review`,json('POST',{action:b.dataset.review,reason:reason.trim()}));
    toast('Moderation action recorded');return loadAdmin();
   }
  }catch(e){const note=$('v2131AuditNote');if(note)note.textContent=e.message;else toast(e.message,true)}
 }
 document.addEventListener('DOMContentLoaded',()=>{
  // V21341: old direct-chat PPV button is disabled; use Professional Inbox only.
  const app=$('v213CreatorsApp');
  if(app){app.addEventListener('click',e=>{const b=e.target.closest('[data-xaction]');if(b)handleAction(b)});
   app.addEventListener('submit',e=>{if(!['v2131UploadForm','v2131PublishForm','v2131SendForm'].includes(e.target.id))return;e.preventDefault();handleForm(e.target)});
  }
  document.addEventListener('click',e=>{const b=e.target.closest('#messageList [data-xaction="offer"]');if(b){e.preventDefault();offerModal(Number(b.dataset.id)).catch(err=>toast(err.message,true))}});
  $('view-q-admin')?.addEventListener('click',e=>{const b=e.target.closest('#v2131AuditCard [data-xaction]');if(b)adminAction(b)});
  $('modal')?.addEventListener('close',clearModalBlob);
 });
 const previous=window.loadQAdmin;
 if(typeof previous==='function')window.loadQAdmin=async function(){await previous();try{await loadAdmin()}catch(e){console.warn('Creator media audit panel unavailable:',e.message)}};
 window.loadQCreatorsMediaAdmin=loadAdmin;
})();
