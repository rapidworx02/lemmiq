/* LEMMIQ V3.0.6 candidate — admin lifecycle panel, inline call controls. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const request=(path,opts)=>window.api('/v306/admin'+path,opts);
let rows=[],access='READ',busy=false,selected=new Set();
function say(s){$('v306MarketStatus').textContent=s}
function allowed(m){let a=[];if(access!=='READ'){
 if(m.status==='LIVE')a.push('SUSPEND');if(m.status==='SUSPENDED')a.push('RESUME');
}if(access==='FULL'){
 if(['LIVE','SUSPENDED'].includes(m.status))a.push('CLOSE');
 if(m.demo_only&&['LIVE','SUSPENDED','CLOSED'].includes(m.status))a.push('VOID_DEMO');
 if(['RESOLVED','VOID'].includes(m.status))a.push('ARCHIVE');
}return a}
const labels={SUSPEND:'Suspend',RESUME:'Resume',CLOSE:'Close market',VOID_DEMO:'Void & refund Demo',ARCHIVE:'Archive'};
function draw(){const q=$('v306Search').value.trim().toLowerCase(),s=$('v306Status').value,c=$('v306Category').value;
const visible=rows.filter(m=>(!q||String(m.id).includes(q)||m.question.toLowerCase().includes(q))&&(!s||m.status===s)&&(!c||m.category===c));
$('v306Markets').innerHTML=visible.map(m=>`<article class="v306-market"><div class="v306-market-meta">${access==='FULL'&&['LIVE','SUSPENDED'].includes(m.status)?`<label><input type="checkbox" data-v306-select="${m.id}" ${selected.has(m.id)?'checked':''}> Select</label>`:''}<strong>#${m.id} · ${esc(m.status)}</strong><small>${esc(m.category)}${m.demo_only?' · DEMO ONLY':''}</small></div><p>${esc(m.question)}</p><small>Scheduled close: ${esc(new Date(m.close_at).toLocaleString())}</small><div class="v306-actions">${allowed(m).map(a=>`<button type="button" class="ghost" data-v306-action="${a}" data-market="${m.id}">${labels[a]}</button>`).join('')}${m.demo_only&&m.status==='CLOSED'?'<small>Record official result in Cricket Market Studio after scheduled close.</small>':''}</div></article>`).join('')||'<p>No matching markets.</p>';
$('v306Bulk').hidden=access!=='FULL';$('v306Bulk').textContent=`Close selected (${selected.size})`;
$('v306Markets').querySelectorAll('[data-v306-select]').forEach(x=>x.onchange=()=>{x.checked?selected.add(+x.dataset.v306Select):selected.delete(+x.dataset.v306Select);$('v306Bulk').textContent=`Close selected (${selected.size})`});
$('v306Markets').querySelectorAll('[data-v306-action]').forEach(x=>x.onclick=()=>act([+x.dataset.market],x.dataset.v306Action));
}
async function load(){try{const data=await request('/markets');rows=data.markets;access=data.access;selected.clear();let cat=$('v306Category'),prev=cat.value;cat.innerHTML='<option value="">All categories</option>'+[...new Set(rows.map(r=>r.category))].sort().map(c=>`<option>${esc(c)}</option>`).join('');cat.value=prev;draw();say(`${rows.length} recent markets · ${access} access`)}catch(e){rows=[];access='READ';selected.clear();say(e.message);$('v306Markets').replaceChildren();$('v306Bulk').hidden=true}}
async function act(ids,action){if(busy||!ids.length)return;let reason=prompt(`Reason for ${labels[action]} (${ids.map(x=>'#'+x).join(', ')}), minimum 8 characters:`);if(!reason||reason.trim().length<8)return;if(!confirm(`${labels[action]} for ${ids.length} market(s)? This action is audited.`))return;busy=true;try{await request('/markets/action',{method:'POST',body:JSON.stringify({ids,action,reason})});await load();say(`${labels[action]} completed. Refresh Cricket Market Studio if open.`)}catch(e){say(e.message)}finally{busy=false}}
window.v306OpenMarket=async id=>{if(!$('v306Admin'))return;await load();$('v306Search').value=String(id);$('v306Status').value='';$('v306Category').value='';draw();$('v306Admin').scrollIntoView({block:'start',behavior:'auto'})};
function setup(){if(!$('v306Admin'))return;$('v306Refresh').onclick=load;['v306Search','v306Status','v306Category'].forEach(id=>$(id).addEventListener('input',draw));$('v306Bulk').onclick=()=>act([...selected],'CLOSE');$('v306CallingLoad').onclick=async()=>{try{let d=await request('/calling');$('v306PaidOnly').checked=d.paid_only;$('v306CallingSave').disabled=false;$('v306CallStatus').textContent='Loaded.'}catch(e){$('v306CallStatus').textContent=e.message}};$('v306CallingSave').onclick=async()=>{let reason=prompt('Reason for calling policy change (minimum 8 characters):');if(!reason||reason.trim().length<8||!confirm('Apply calling policy to new outgoing personal calls?'))return;try{let d=await request('/calling',{method:'PUT',body:JSON.stringify({paid_only:$('v306PaidOnly').checked,reason})});$('v306PaidOnly').checked=d.paid_only;$('v306CallStatus').textContent='Saved.'}catch(e){$('v306CallStatus').textContent=e.message}};}
let wake=null, requesting=false;
async function acquire(){if(requesting||wake||document.visibilityState!=='visible'||!navigator.wakeLock||$('callOverlay')?.classList.contains('hidden'))return;requesting=true;try{const w=await navigator.wakeLock.request('screen');if($('callOverlay')?.classList.contains('hidden')){await w.release();return}wake=w;w.addEventListener('release',()=>{if(wake===w)wake=null})}catch{}finally{requesting=false}}
function release(){const w=wake;wake=null;w?.release().catch(()=>{})}
function callSetup(){const overlay=$('callOverlay'),min=$('v306MinCall');if(!overlay||!min)return;min.onclick=()=>{const small=overlay.classList.toggle('v306-min-call');min.textContent=small?'Expand call':'Minimise call'};const observe=()=>{if(overlay.classList.contains('hidden')){if(overlay.classList.contains('v306-min-call'))overlay.classList.remove('v306-min-call');min.textContent='Minimise call';release()}else acquire()};new MutationObserver(observe).observe(overlay,{attributes:true,attributeFilter:['class']});document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')acquire()});observe()}
function start(){setup();callSetup();$('logoutBtn')?.addEventListener('click',()=>{rows=[];access='READ';selected.clear();if($('v306Markets'))$('v306Markets').replaceChildren();if($('v306Bulk'))$('v306Bulk').hidden=true;if($('v306CallingSave'))$('v306CallingSave').disabled=true;if($('v306PaidOnly'))$('v306PaidOnly').checked=false;if($('v306CallStatus'))$('v306CallStatus').textContent='';if($('v306MarketStatus'))$('v306MarketStatus').textContent=''});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
