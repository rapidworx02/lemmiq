/* Single Q Admin entry coordinator. Existing endpoint authorisation remains authoritative. */
(()=>{'use strict';
const $=id=>document.getElementById(id),root=()=>$('view-q-admin');
const active=()=>root()?.classList.contains('active');const token=()=>window.lemmiqState?.token;
let identity=null,session=null,opening=null,sectionSeq=0,visit=0;const flights=new Map(),ready=new Set();
const master=()=>identity?.role==='MASTER_ADMIN'&&session===token();
window.v307PredictLevel=()=>!active()||session!==token()?'NONE':master()?'FULL':(identity?.permissions?.Q_PREDICT||'NONE');
window.v307CanPredict=()=>['READ','WRITE','FULL'].includes(window.v307PredictLevel());
window.v307AdminGroup=()=>window.v307CurrentGroup?.()||'overview';
const gate=(message)=>{const p=$('v307GateText');if(p)p.textContent=message;};
function status(message){const p=$('v307StatusText');if(p)p.textContent=message}
function ensureStatus(){if($('v307SectionStatus'))return;const area=document.querySelector('#v2124AdminShell .v2124-admin-main');if(!area)return;const div=document.createElement('div');div.id='v307SectionStatus';div.className='card glass';const p=document.createElement('p');p.id='v307StatusText';p.setAttribute('role','status');const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent='Refresh section';b.onclick=()=>loadSection(window.v307AdminGroup(),true);div.append(p,b);area.insertBefore(div,area.children[1]||null)}
async function loadSection(group,force=false){
 if(!master()||!active())return;
 if(flights.has(group)){status('Loading '+group+'…');return flights.get(group);}if(!force&&ready.has(group)){status('Section ready · Refresh for latest data');return}
 const currentToken=token(),epoch=visit,seq=++sectionSeq;status('Loading '+group+'…');
 const work=(async()=>{let jobs=[];const add=(name,fn)=>{if(typeof fn==='function')jobs.push([name,Promise.resolve().then(fn)])};
   add('Core '+group,()=>window.v307LoadCore?.(group));
   if(group==='overview'||group==='predict'||group==='analytics')add('Operations',()=>window.loadV29Admin?.(group));
   if(group==='predict'){add('Market management',()=>window.v307LoadMarkets?.());add('Cricket studio',()=>window.v307LoadCricket?.());add('Predict controls',()=>window.v307LoadPredictTreasury?.());add('Refill and withdrawals',()=>window.v307LoadBroadcast?.());}
   if(group==='creators')add('Creators',window.loadQCreatorsAdmin);
   if(group==='analytics')add('Usage analytics',window.v307LoadUsage);
   if(group==='settings')add('Admin team',()=>window.v307LoadTeam?.(identity));
   if(['economy','payments','settings'].includes(group))add('Economy controls',()=>window.v307LoadEconomy?.(group,identity));
   if(group==='communication')add('Communication',window.v307LoadBroadcast);
   if(group==='calling')add('Calling policy',()=> $('v306CallingLoad')?.click());
   const results=await Promise.allSettled(jobs.map(x=>x[1]));if(currentToken!==token()||epoch!==visit||!master())return;
   window.v307Organise?.();const failed=results.flatMap((r,i)=>r.status==='rejected'?[jobs[i][0]+': '+(r.reason?.message||'unavailable')]:[]);
   if(!failed.length)ready.add(group);else ready.delete(group);
   if(seq===sectionSeq&&window.v307AdminGroup()===group)status(failed.length?failed.join(' · '):'Section ready · Refresh for latest data');
 })();flights.set(group,work);try{await work}finally{if(flights.get(group)===work)flights.delete(group)}
}
window.v307LoadSection=loadSection;
const delegated=window.loadQAdmin;
async function open(){
 if(!active()||!token())return;
 if(opening)return opening;
 const t=token(),epoch=visit;if(session!==t){identity=null;session=t;ready.clear();flights.clear();root().removeAttribute('data-v307-ready');}
 if(master()&&root().dataset.v307Ready==='master'){return loadSection(window.v307AdminGroup(),true)}
 gate('Checking admin access…');
 const run=(async()=>{try{const access=await window.api('/v28/admin/access/me');if(t!==token()||!active()||epoch!==visit)return;identity=access;
   if(identity.role==='MASTER_ADMIN'){
      window.v307MountLayout(identity);ensureStatus();root().dataset.v307Ready='master';
      await loadSection(window.v307AdminGroup()||'overview');
   }else{await delegated?.();if(t===token()&&active()&&epoch===visit){root().dataset.v307Ready='delegated';if(window.v307CanPredict()){const m=$('v306Admin');if(m){root().append(m);m.style.display='';m.dataset.v307DelegatedPredict='1'}await Promise.allSettled([window.v307LoadMarkets?.(),window.v307LoadCricket?.()]);}}}
 }catch(e){if(t!==token()||epoch!==visit)return;root().removeAttribute('data-v307-ready');gate('Q Admin: '+(e.message||'Access unavailable'))}})();opening=run;try{await run}finally{if(opening===run)opening=null}
}
window.loadQAdmin=open;
window.v307LeaveAdmin=()=>{visit++;sectionSeq++;identity=null;opening=null;ready.clear();flights.clear();root()?.removeAttribute('data-v307-ready');const m=$('v306Admin');if(m)delete m.dataset.v307DelegatedPredict;};
function start(){ $('v307GateRetry')?.addEventListener('click',open);document.addEventListener('lemmiq:admin-section',e=>{if(master()&&active()&&root().dataset.v307Ready==='master')loadSection(e.detail)});if(active())open();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
