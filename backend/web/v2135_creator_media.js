/* V2.13.5 Creator Freedom beta: direct professional free/PPV media, Q ledger and audit. */
(()=>{'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 const token=()=>window.lemmiqState?.token||'';
 const headers=()=>({Authorization:'Bearer '+token()});
 const blobs=new Map();
 const request=async(path,opts={})=>{
   const h={...headers(),...(opts.headers||{})};
   const r=await fetch('/v2135'+path,{...opts,headers:h});
   if(!r.ok){let d;try{d=await r.json()}catch{}throw new Error(d?.detail||`Media request failed (${r.status})`)}
   return r.headers.get('content-type')?.includes('application/json')?r.json():r;
 };
 const notify=(t,err=false)=>typeof toast==='function'?toast(t,err):console.log(t);
 const modal=()=>document.getElementById('v2135MediaDialog');
 const close=()=>{modal()?.close();};
 const key=()=>crypto.randomUUID();
 let threadId=null,uploading=false;
 function ensure(){if(modal())return;
   const d=document.createElement('dialog');d.id='v2135MediaDialog';d.innerHTML=`<div class="v2135-card">
     <div class="v2135-head"><h3>Send media to this fan</h3><button type="button" id="v2135Close" class="ghost">✕</button></div>
     <p>Send an allowed photo or video directly in this professional chat. No gallery item required.</p>
     <form id="v2135Upload"><label>Choose photo or video<input type="file" name="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" required></label>
       <label>Send as<select name="kind" id="v2135Kind"><option value="FREE">Free media</option><option value="PPV">Locked PPV media</option></select></label>
       <label id="v2135PriceLabel" class="hidden">PPV price in Q<input type="number" name="price_q" min="0.01" step="0.01" value="25"></label>
       <button type="submit" class="primary" id="v2135Send">Send to fan</button></form>
     <p class="micro">Mainstream, non-explicit content only. Media is stored privately and can be reviewed, quarantined or removed by authorised LEMMIQ moderators. Administrative access is logged.</p>
   </div>`;document.body.append(d);
   d.querySelector('#v2135Close').onclick=close;
   d.querySelector('#v2135Kind').onchange=e=>d.querySelector('#v2135PriceLabel').classList.toggle('hidden',e.target.value!=='PPV');
   d.querySelector('#v2135Upload').onsubmit=async e=>{
     e.preventDefault();if(uploading||!threadId)return;
     const f=e.currentTarget,fd=new FormData(f),kind=fd.get('kind');
     fd.set('price_q',kind==='PPV'?fd.get('price_q'):'0');
     if(kind==='PPV'&&!confirm(`Send a locked media offer for ${fd.get('price_q')} Q?`))return;
     uploading=true;const btn=d.querySelector('#v2135Send');btn.disabled=true;btn.textContent='Uploading…';
     try{await request(`/chats/${encodeURIComponent(threadId)}/media`,{method:'POST',body:fd});close();notify(kind==='PPV'?'Locked PPV sent':'Free media sent');
       if(typeof window.v2135RefreshThread==='function')await window.v2135RefreshThread();
     }catch(err){notify(err.message,true)}finally{uploading=false;btn.disabled=false;btn.textContent='Send to fan'}
   };
 }
 window.v2135MediaCard=(message,own)=>{
   const m=message.media;if(!m)return '';
   const locked=!m.unlocked;const cls=own?' mine':'';
   return `<div class="v2134-bubble v2135-media-card${cls}" data-v2135-mid="${m.id}" data-v2135-locked="${locked}">
     <strong>${m.kind==='PPV'?'🔒 PPV':'🖼 Free'} ${esc(m.media_kind==='VIDEO'?'video':'photo')}</strong>
     <div class="v2135-preview" data-v2135-preview="${m.id}">${locked?'Locked · unlock to view':m.status==='VISIBLE'?'Loading private media…':'Media unavailable'}</div>
     ${locked&&m.status==='VISIBLE'?`<button type="button" class="primary" data-v2135-unlock="${m.id}" data-price="${m.price_q}">Unlock ${m.price_q} Q</button>`:''}
     ${!own?`<button type="button" class="ghost v2135-report" data-v2135-report="${m.id}">Report</button>`:''}
   </div>`;
 };
 async function hydrateMedia(){
   const items=[...document.querySelectorAll('[data-v2135-preview]')];
   for(const node of items){const id=node.dataset.v2135Preview;const wrap=node.closest('[data-v2135-mid]');
     if(!wrap||wrap.dataset.v2135Locked==='true'||node.dataset.loaded)return;
     try{const r=await request(`/media/${id}/file`);
       const mime=r.headers.get('content-type')||'';if(!/^(image\/|video\/)/.test(mime))throw Error('Unsupported media');
       const b=await r.blob();const url=URL.createObjectURL(b);blobs.set(node,url);
       const el=document.createElement(mime.startsWith('video/')?'video':'img');el.src=url;
       if(mime.startsWith('video/')){el.controls=true;el.preload='metadata'}else{el.loading='lazy';el.alt='Creator media'}
       node.replaceChildren(el);node.dataset.loaded='1';
     }catch{node.textContent='Media unavailable'}
   }
 }
 function cleanStale(){for(const [node,url] of blobs){if(!node.isConnected){URL.revokeObjectURL(url);blobs.delete(node)}}}
 window.v2135SetupThread=data=>{
   threadId=data.thread_id;cleanStale();
   const container=document.querySelector('#view-professional-inbox');if(!container)return;
   const old=container.querySelector('#v2135DirectButton');old?.remove();
   if(data.role==='CREATOR'){
     const b=document.createElement('button');b.id='v2135DirectButton';b.type='button';b.className='ghost v2135-attach';b.textContent='＋ Photo / Video · Free or PPV';
     b.onclick=()=>{ensure();modal().showModal()};
     const composer=container.querySelector('.v2134-composer'),offer=container.querySelector('.v2134-offer');
     if(composer)composer.after(b);else if(offer)offer.before(b);else container.append(b);
   }
   requestAnimationFrame(hydrateMedia);
 };
 let auditBlob=null;
 async function loadAdminDirect(){
   const root=document.querySelector('[data-v2124-admin-panel="creators"]');
   if(!root||!document.getElementById('view-q-admin')?.classList.contains('active'))return;
   const rows=await request('/admin/media?limit=100');
   let box=document.getElementById('v2135AuditCard');
   if(!box){box=document.createElement('article');box.id='v2135AuditCard';box.className='card glass';root.append(box)}
   box.innerHTML=`<h3>Instant Creator Media · Compliance Audit</h3>
     <p class="micro">All free/PPV direct-chat uploads remain privately stored. Admin previews are logged.</p>
     <div class="v2131-rows">${rows.map(m=>`<div><span><strong>#${m.id} ${esc(m.kind)} ${esc(m.mime_type)}</strong>
     <small>Creator #${m.creator_id} · Recipient #${m.fan_id} · ${m.status} · ${m.price_q} Q</small></span>
     <button type="button" class="ghost" data-v2135-audit="${m.id}">Audit view</button>
     <button type="button" class="ghost" data-v2135-review="${m.id}" data-action="${m.status==='VISIBLE'?'QUARANTINE':'RESTORE'}">${m.status==='VISIBLE'?'Quarantine':'Restore'}</button></div>`).join('')||'<p>No direct media yet.</p>'}</div>
     <button type="button" class="ghost" id="v2135AuditRefresh">Refresh direct-media audit</button>`;
   box.querySelector('#v2135AuditRefresh').onclick=()=>loadAdminDirect().catch(e=>notify(e.message,true));
 }
 async function inspectAdminMedia(id){
   if(!confirm('Open private creator media for an authorised safety audit? This access is logged.'))return;
   const r=await request(`/admin/media/${id}/file`);
   const mime=r.headers.get('content-type')||'';
   if(!mime.startsWith('image/')&&!mime.startsWith('video/'))throw Error('Unsupported preview format');
   if(auditBlob)URL.revokeObjectURL(auditBlob);
   auditBlob=URL.createObjectURL(await r.blob());
   const d=document.createElement('dialog');d.id='v2135AuditPreview';d.innerHTML=`<div class="v2135-card"><h3>Authorised Audit · Media #${id}</h3><div id="v2135AuditPreviewMedia"></div><button class="ghost" type="button">Close</button></div>`;
   document.body.append(d);
   const media=document.createElement(mime.startsWith('image/')?'img':'video');media.src=auditBlob;
   media.style.maxWidth='100%';media.style.maxHeight='65dvh';media.controls=mime.startsWith('video/');
   d.querySelector('#v2135AuditPreviewMedia').append(media);
   d.querySelector('button').onclick=()=>d.close();
   d.onclose=()=>{URL.revokeObjectURL(auditBlob);auditBlob=null;d.remove()};d.showModal();
 }
 document.addEventListener('click',async ev=>{
   const b=ev.target.closest('#v2135AuditCard [data-v2135-audit],#v2135AuditCard [data-v2135-review]');if(!b)return;
   try{
     if(b.dataset.v2135Audit)await inspectAdminMedia(Number(b.dataset.v2135Audit));
     else{
       const action=b.dataset.action;const reason=prompt('Reason for this action (minimum 8 characters):');
       if(!reason||reason.trim().length<8)return;
       await request(`/admin/media/${Number(b.dataset.v2135Review)}/review`,{
         method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,reason})});
       await loadAdminDirect();
     }
   }catch(e){notify(e.message,true)}
 });
 const previousAdmin=window.loadQAdmin;
 if(typeof previousAdmin==='function')window.loadQAdmin=async function(){await previousAdmin();try{await loadAdminDirect()}catch(e){console.warn('Direct media admin audit:',e.message)}};
 document.addEventListener('click',async e=>{
   const unlock=e.target.closest('[data-v2135-unlock]');
   if(unlock){const mid=unlock.dataset.v2135Unlock;if(!confirm(`Unlock for ${unlock.dataset.price} Q?`))return;
     unlock.disabled=true;
     try{await request(`/media/${mid}/unlock`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:key()})});
       notify('Media unlocked. Reopen the conversation to view it.');
       if(typeof window.v2135RefreshThread==='function')await window.v2135RefreshThread();
     }catch(err){notify(err.message,true)}finally{unlock.disabled=false}
   }
   const report=e.target.closest('[data-v2135-report]');
   if(report){const reason=prompt('Reason for reporting this media:');if(!reason)return;
     try{await request(`/media/${report.dataset.v2135Report}/report`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason})});notify('Reported. Media was quarantined for review.');report.closest('.v2135-media-card')?.remove()}
     catch(err){notify(err.message,true)}
   }
 });
})();
