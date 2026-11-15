/* LEMMIQ V2.13 — Master Admin creator moderation and accounting. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id);
 const e=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const q=x=>Number(x||0).toLocaleString(undefined,{maximumFractionDigits:6});
 const call=(p,o={})=>api('/v213/creators'+p,o);
 const json=(m,b)=>({method:m,body:JSON.stringify(b)});
 let data=null,previewUrl=null;
 function host(){return document.querySelector('[data-v2124-admin-panel="creators"]')}
 function card(){let h=host();if(!h)return null;let el=$('v213CreatorAdminCard');if(!el){el=document.createElement('article');el.className='card glass v213-admin-panel';el.id='v213CreatorAdminCard';h.appendChild(el)}return el}
 const line=(label,sub,actions='')=>`<div class="v213-line"><span><strong>${e(label)}</strong><small>${e(sub)}</small></span><div class="v213-actions">${actions}</div></div>`;
 const btn=(action,id,label,cl='ghost')=>`<button type="button" data-ca="${e(action)}" data-id="${Number(id)}" class="${cl}">${e(label)}</button>`;
 const formatProfile=p=>`#${p.id} @${p.username} · ${p.display_name} · ${p.category} · ${p.level}`;
 function show(){const el=card();if(!el||!data)return;const c=data.config;
   const profiles=data.profiles||[],posts=data.pending_posts||[],pays=data.payments||[];
   el.innerHTML=`<div class="section-head"><div><span class="eyebrow">Q CREATORS</span><h3>Moderation & Monetisation</h3><p class="micro">Mainstream creator programme only. Explicit content remains disabled.</p></div><button class="ghost" type="button" data-ca="refresh" data-id="0">↻ Refresh</button></div>
   <div class="v213-earnings-grid"><div><small>Creator applications</small><strong>${profiles.filter(x=>x.status==='PENDING').length}</strong></div><div><small>Posts awaiting review</small><strong>${posts.length}</strong></div><div><small>LEMMIQ commission wallet</small><strong>${q(data.fee_wallet_q)} Q</strong></div></div>
   <details open><summary>Commission & payment controls</summary><form class="v213-admin-config" id="v213AdminCreatorConfig"><label>LEMMIQ creator commission %<input name="fee_percent" min="0" max="40" step="0.01" required type="number" value="${c.fee_percent}"></label><label class="v213-check"><input name="payments_enabled" type="checkbox" ${c.payments_enabled?'checked':''}> Enable mainstream Q payments</label><button type="submit" class="primary">Save controls</button></form><p class="micro">New rate applies to future transactions only. Turning off prevents new charges, not existing refunds or earnings transfers.</p></details>
   <details open><summary>Creator applications & status (${profiles.length})</summary><div class="v213-stack">${profiles.map(p=>line(formatProfile(p),`Status ${p.status}${p.adult_requested?' · 18+ requested (unavailable)':''} · subscription ${q(p.monthly_q)} Q`,
     (p.status!=='APPROVED'?btn('APPROVE_CREATOR',p.id,'Approve'):'')+btn('SUSPEND_CREATOR',p.id,'Suspend')+btn('REJECT_CREATOR',p.id,'Reject'))).join('')||'<p class="micro">No creator applications.</p>'}</div></details>
   <details><summary>Posts awaiting content review (${posts.length})</summary><div class="v213-stack">${posts.map(p=>line(`#${p.id} ${p.title}`,`@${p.creator_username} · ${p.level} · ${p.visibility} · ${p.kind} · ${p.price_q} Q · ${p.teaser||''}`,
    btn('VIEW_POST',p.id,'View content')+btn('APPROVE_POST',p.id,'Approve','primary')+btn('REJECT_POST',p.id,'Reject'))).join('')||'<p class="micro">No posts pending.</p>'}</div></details>
   <details><summary>Creator payments (${pays.length} recent)</summary><div class="v213-stack">${pays.map(p=>line(`Payment #${p.id} · ${p.kind} · ${p.status}`,`Fan #${p.fan_id} → Creator #${p.creator_id} · Gross ${q(p.gross_q)} Q · Fee ${q(p.fee_q)} Q · Creator ${q(p.net_q)} Q`, p.status==='REFUNDED'?'':btn('REFUND',p.id,'Refund / review'))).join('')||'<p class="micro">No payments yet.</p>'}</div></details>
   <details><summary>Service requests needing action (${(data.open_requests||[]).length})</summary><div class="v213-stack">${(data.open_requests||[]).map(x=>line(`${x.kind} #${x.id}`,`Creator #${x.creator_id} · Fan #${x.fan_id} · ${x.status}`)).join('')||'<p class="micro">None.</p>'}</div></details>
   <button type="button" class="ghost" data-ca="export" data-id="0">Export loaded finance CSV</button>`;
 }
 async function load(){const h=host();if(!h||!document.querySelector('#view-q-admin.active'))return;try{data=await call('/admin/overview');show()}catch(err){const x=card();if(x)x.innerHTML=`<p class="micro">Creator Admin: ${e(err.message)}</p>`}}
 function reviewReason(action){const reason=prompt(`Reason for ${action} (minimum 8 characters; do not include passwords):`);if(reason===null)return null;if(reason.trim().length<8){toast('Reason must have at least 8 characters',true);return null}return reason.trim()}
 async function previewPost(id){const p=(data?.pending_posts||[]).find(x=>x.id===id);if(!p)return;openModal(`<h3>${e(p.title)}</h3><p class="micro">${e(p.creator_username)} · ${e(p.level)} · ${e(p.visibility)}</p><p style="white-space:pre-wrap;overflow-wrap:anywhere">${e(p.body||'')}</p><div id="v213AdminMediaPreview">${p.kind==='TEXT'?'Text-only post':'Loading media…'}</div><p class="micro">Review content against your legal and moderation requirements. Explicit content is not permitted in this app.</p>`);
  if(p.kind!=='TEXT'){try{const r=await fetch(`/v2131/exclusives/admin/posts/${id}/media`,{headers:authHeaders()});if(!r.ok)throw Error('Media unavailable');const type=r.headers.get('content-type')||'';previewUrl=URL.createObjectURL(await r.blob());const node=document.createElement(type.startsWith('video/')?'video':'img');node.src=previewUrl;node.controls=type.startsWith('video/');node.style.maxWidth='100%';const box=$('v213AdminMediaPreview');if(box)box.replaceChildren(node)}catch(e){if($('v213AdminMediaPreview'))$('v213AdminMediaPreview').textContent=e.message}}
 }
 async function handleClick(ev){const b=ev.target.closest('[data-ca]');if(!b)return;const action=b.dataset.ca,id=Number(b.dataset.id);try{
  if(action==='refresh')return load();
  if(action==='export'){const rows=[['ID','Fan ID','Creator ID','Kind','Gross Q','Fee Q','Creator Net Q','Status'],...(data.payments||[]).map(p=>[p.id,p.fan_id,p.creator_id,p.kind,p.gross_q,p.fee_q,p.net_q,p.status])];const csv=rows.map(r=>r.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='lemmiq-creators-finance-loaded.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return}
  if(action==='VIEW_POST')return previewPost(id);
  const reason=reviewReason(action);if(!reason)return;
  if(!confirm(`Confirm ${action} #${id}?`))return;
  if(action.endsWith('_CREATOR'))await call(`/admin/profiles/${id}/review`,json('POST',{action:action.split('_')[0],reason}));
  else if(action.endsWith('_POST'))await call(`/admin/posts/${id}/review`,json('POST',{action:action.split('_')[0],reason}));
  else if(action==='REFUND')await call(`/admin/payments/${id}/refund`,json('POST',{action:'REFUND',reason}));
  toast('Creator admin action recorded');await load();
 }catch(e){toast(e.message||String(e),true)}}
 document.addEventListener('DOMContentLoaded',()=>{const root=$('view-q-admin');if(!root)return;root.addEventListener('click',ev=>{if(ev.target.closest('#v213CreatorAdminCard'))handleClick(ev)});root.addEventListener('submit',async ev=>{if(ev.target.id!=='v213AdminCreatorConfig')return;ev.preventDefault();try{const f=new FormData(ev.target);await call('/admin/config',json('PUT',{fee_percent:Number(f.get('fee_percent')),payments_enabled:f.get('payments_enabled')==='on'}));toast('Creator settings saved');await load()}catch(e){toast(e.message,true)}});$('modal')?.addEventListener('close',()=>{if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null}})});
 const prev=window.loadQAdmin;
 if(typeof prev==='function')window.loadQAdmin=async function(){await prev();await load()};
 window.loadQCreatorsAdmin=load;
})();
