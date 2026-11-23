/* V21311_RELEASE */
/* LEMMIQ 2.13.10 — isolated Q Predict Q wallet, USDT purchase quotes (TRC20/BEP20), Demo preserved. */
(()=>{'use strict';
const $=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>Number(n||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:6});
const api=(route,opts)=>window.api('/v21310/predict'+route,opts);const demo=(route,opts)=>window.api('/v2138/predict'+route,opts);
const state={mode:'DEMO',home:null,demo:null,filter:'ALL',sub:'ALL',network:'TRC20',qAmount:'1000',quote:null,order:null,admin:null,busy:false};
const msg=(s,e=false)=>typeof window.toast==='function'?window.toast(s,e):alert(s);
const jpost=data=>({method:'POST',body:JSON.stringify(data)});
function root(){return $('v303PredictContent')}
// V303: stable HTML shell, one owner, read-only preview.
let mode303='predict',seq303=0,token303=null;
const pools303=[['Q Shield AI',100,1000,30],['Q Pulse AI',500,5000,20],['Q Surge AI',1000,10000,10]];
const session303=()=>window.lemmiqState?.token;
function balance303(n){return n!=null&&Number.isFinite(Number(n))?money(n)+' Q':'Unavailable'}
function preview303(data=null,loading=false){
 const host=$('v300Trading');if(!host)return;
 const rate=Number(data?.reference_usdt_per_q),valid=Number.isFinite(rate)&&rate>0;
 const equiv=n=>valid?money(n/rate)+' Q':'Q equivalent unavailable';
 host.innerHTML=`<section class="v302-preview-wallet"><small>Q Predict Wallet · available Q</small><strong>${loading?'Loading…':balance303(data?.available_q)}</strong><small>${valid?'Reference: '+money(rate)+' USDT/Q':'Reference price unavailable'}</small><small>Shared wallet for future allocations · No separate Q purchase</small></section><h2>AI Trading Pools</h2><p>Powered by RapidTradeX · Coming Soon</p><p class="v300-preview-note">Q Economy and Demo balances stay separate. Proposed sequential pools, monthly profit settlement and 12 monthly investment-unit unlocks.</p>${pools303.map(([name,min,cap,fee])=>`<article class="v300-pool"><h3>${name}</h3><dl><div><dt>Minimum allocation</dt><dd>${money(min)} USDT</dd><small>${equiv(min)}</small></div><div><dt>Pool capacity</dt><dd>${money(cap)} USDT</dd><small>${equiv(cap)}</small></div><div><dt>Member profit share</dt><dd>${100-fee}%</dd></div><div><dt>Admin performance fee</dt><dd>${fee}%</dd></div></dl><div class="v300-soon">Coming Soon · No allocations</div></article>`).join('')}<p class="v300-preview-note">Concept only. No trading, deposits, allocations or profit credits available. Capital losses are possible; returns and redemptions are not guaranteed. Subject to appropriate authorisation.</p>`;
}
function setMode303(next,refresh=true){
 mode303=next==='trading'?'trading':'predict';const trading=mode303==='trading';const epoch=++seq303,token=session303();token303=token;
 const panel=root(),preview=$('v300Trading');if(!panel||!preview)return;
 panel.hidden=trading;preview.hidden=!trading;
 for(const b of document.querySelectorAll('#v21310PredictRoot [data-v303-mode]'))b.setAttribute('aria-pressed',String(b.dataset.v303Mode===mode303));
 if(!refresh)return;
 if(!trading)return load();
 preview303(null,true);if(!token){preview303();return;}
 return api('/ui-config').then(data=>{if(epoch===seq303&&token===session303()&&mode303==='trading')preview303(data)}).catch(()=>{if(epoch===seq303&&token===session303()&&mode303==='trading')preview303()});
}
function refresh303(){if(token303!==session303())return setMode303('predict');return setMode303(mode303)}
function init303(){
 const shell=$('v21310PredictRoot');if(!shell||shell.dataset.bound303)return;shell.dataset.bound303='1';
 shell.querySelectorAll('[data-v303-mode]').forEach(b=>b.onclick=()=>setMode303(b.dataset.v303Mode));
 window.loadQPredict=refresh303;
 if($('view-q-predict')?.classList.contains('active'))refresh303();
 const app=$('appView');if(app)new MutationObserver(()=>{if(app.classList.contains('hidden')){++seq303;token303=null;state.mode='DEMO';tab311='markets';route311=null;offset311=0;query304='';sort304='closing';state.home=null;state.demo=null;state.order=null;state.quote=null;root()?.replaceChildren();preview303();setMode303('predict',false)}}).observe(app,{attributes:true,attributeFilter:['class']});
}

function status(){return `<div class="pq-note">LEMMIQ Q Economy and Q Predict Q wallets are fully separate. ${esc(state.home?.notice||'')}</div>`}
function wallet(){const h=state.home||{};return `<section class="pq-hero"><div class="eyebrow">Q PREDICT · DEDICATED WALLET</div><h2>Q Predict Wallet</h2><small>Approved account access · Financial services subject to authorisation</small><p>Buy Q Predict Q using USDT, then use eligible Q on prediction markets.</p><div class="pq-counters"><div><small>Available</small><strong>${h.available_q==null?"—":money(h.available_q)} Q</strong></div><div><small>Locked in markets</small><strong>${h.locked_q==null?"—":money(h.locked_q)} Q</strong></div></div><div class="pq-rates">Reference: ${money(h.reference_usdt_per_q)} USDT/Q · Buy +5%: ${money(h.buy_usdt_per_q)} · Sell −5%: ${money(h.sell_usdt_per_q)}</div></section>
 <div class="pq-actions"><button class="primary" id="pqBuy">Buy Q with USDT</button><button class="ghost" id="pqSell">Sell Q · Withdraw USDT</button><button class="ghost" id="pqActivity">Wallet activity</button></div>${status()}`}
function demoHeader(){const h=state.demo||{};return `<section class="pq-hero"><div class="eyebrow">Q PREDICT · PRACTICE</div><h2>Demo predictions</h2><p>Virtual USDT only. No monetary value and no transfers to real Q.</p><div class="pq-counters"><div><small>Available demo credits</small><strong>${h.available==null?"—":money(h.available)} Demo USDT</strong></div><div><small>Locked</small><strong>${h.locked==null?"—":money(h.locked)} Demo USDT</strong></div></div></section>`}
let query304='',sort304='closing';
let tab311='markets',status311='recent',days311=30,offset311=0,route311=null,historySeq311=0;
function stats311(m,isDemo){const y=Number(m.yes_pool),n=Number(m.no_pool),unit=isDemo?'Demo USDT':'Q';if(!Number.isFinite(y)||!Number.isFinite(n))return '<small>Pool data unavailable</small>';const t=y+n;if(!t)return '<small>No predictions yet</small>';const pct=y/t*100;return `<div class="pq311-pools"><div class="pq311-yes"><small>YES pool share</small><strong>${pct.toFixed(1)}%</strong>${money(y)} ${unit}</div><div class="pq311-no"><small>NO pool share</small><strong>${(100-pct).toFixed(1)}%</strong>${money(n)} ${unit}</div></div><div class="pq311-bar"><span style="width:${pct}%"></span><span style="width:${100-pct}%"></span></div><div class="pq311-pool-caption">${Number(m.participants||0)} participants · Pool ${money(t)} ${unit}. Pool share, not probability.</div>`}
function historyShell311(){return `<section class="pq311-history"><h3>My Predictions</h3><div class="pq311-tabs">${[['active','Active'],['awaiting','Awaiting results'],['recent','Recent results']].map(([k,l])=>`<button class="ghost ${status311===k?'on':''}" data-pq311-status="${k}">${l}</button>`).join('')}</div>${status311==='recent'?`<label>Time period <select id="pq311Days">${[7,30,90,0].map(n=>`<option value="${n}" ${days311===n?'selected':''}>${n?n+' days':'All time'}</option>`).join('')}</select></label>`:''}<div id="pq311HistoryRows" role="status">Loading your predictions…</div></section>`}
function historyCard311(m,unit){return `<article class="pq-market"><small>${esc(m.category)} · ${esc(m.settlement_status==='PENDING'?m.market_status:m.settlement_status)}</small><h4>${esc(m.question)}</h4>${!m.settled_at?'<p class="pq312-position-lock">🔒 Prediction locked until settlement. No cancellation, stake reduction or change of outcome.</p>':''}${m.positions.map(p=>`<div class="pq-line"><span>Your ${esc(p.side)} · ${esc(p.status)}</span><b>${money(p.stake)} ${unit}</b></div>${m.settled_at?`<small>Returned ${money(p.returned)} ${unit} · Fee ${money(p.fee)} · Net ${money(p.returned-p.stake)} ${unit}</small>`:''}`).join('')}<p>${m.settled_at?'Settled '+esc(new Date(m.settled_at).toLocaleString()):'Closes '+esc(new Date(m.close_at).toLocaleString())}</p>${!m.settled_at?`<p class="pq312-timer" data-pq312-close-ms="${Date.parse(m.close_at)||0}">Calculating closing time…</p>`:''}${m.result?`<p>Official result: ${esc(m.result)}</p>`:''}${m.evidence?`<details><summary>Settlement evidence</summary><p>${esc(m.evidence)}</p></details>`:''}${m.template_code==='CRICKET_V312_INTL_WIN'?`<button class="ghost" data-pq312-report="${Number(m.market_id)}">Report a result issue</button>`:''}</article>`}
async function fetchHistory311(){const host=$('pq311HistoryRows');if(!host)return;const seq=++historySeq311,t=session303(),mode=state.mode,unit=mode==='DEMO'?'Demo USDT':'Q';host.textContent='Loading your predictions…';try{const r=await window.api(`/v311/predict/history?wallet=${mode}&status=${status311}&days=${days311}&offset=${offset311}${route311?'&market_id='+Number(route311):''}`);if(seq!==historySeq311||t!==session303()||mode!==state.mode||host!==$('pq311HistoryRows'))return;const s=r.summary||{};host.innerHTML=`${status311==='recent'&&!route311?`<div class="pq-panel"><b>${Number(s.markets||0)} settled markets</b><p>Staked ${money(s.stake)} ${unit} · Returned ${money(s.returned)} ${unit} · Net ${money(s.net)} ${unit}</p></div>`:''}${(r.items||[]).map(m=>historyCard311(m,unit)).join('')||'<p>No predictions in this section.</p>'}<div class="pq311-tabs">${offset311?'<button class="ghost" id="pq311Prev">Previous</button>':''}${r.has_more?'<button class="ghost" id="pq311Next">Next</button>':''}${route311?'<button class="ghost" id="pq311All">All my predictions</button>':''}</div>`;$('pq311Prev')?.addEventListener('click',()=>{offset311=Math.max(0,offset311-20);fetchHistory311()});$('pq311Next')?.addEventListener('click',()=>{offset311+=20;fetchHistory311()});$('pq311All')?.addEventListener('click',()=>{route311=null;offset311=0;fetchHistory311()});host.querySelectorAll('[data-pq312-report]').forEach(b=>b.onclick=async()=>{const reason=prompt('Describe the result issue (at least 15 characters)');if(!reason)return;if(reason.trim().length<15)return msg('Please provide more detail.',true);try{await window.api('/v312/cricket/report',{method:'POST',body:JSON.stringify({market_id:Number(b.dataset.pq312Report),reason:reason.trim()})});msg('Report submitted to Q Predict support.')}catch(e){msg(e.message||'Report failed',true)}})}catch(e){if(seq===historySeq311&&host===$('pq311HistoryRows')){host.textContent=e.message||'History unavailable';const retry=document.createElement('button');retry.textContent='Retry';retry.onclick=fetchHistory311;host.append(retry)}}}
function tabs311(){return `<div class="pq311-tabs"><button class="ghost ${tab311==='markets'?'on':''}" data-pq311-tab="markets">Markets</button><button class="ghost ${tab311==='history'?'on':''}" data-pq311-tab="history">My Predictions</button></div>`}
function bind311(){root()?.querySelectorAll('[data-pq311-tab]').forEach(b=>b.onclick=()=>{tab311=b.dataset.pq311Tab;route311=null;offset311=0;render()});root()?.querySelectorAll('[data-pq311-status]').forEach(b=>b.onclick=()=>{status311=b.dataset.pq311Status;route311=null;offset311=0;render()});$('pq311Days')?.addEventListener('change',e=>{days311=Number(e.target.value);offset311=0;fetchHistory311()});if(tab311==='history')fetchHistory311()}
window.openPredictResult311=(wallet,id)=>{if(!['DEMO','REAL_Q'].includes(wallet)||!Number.isInteger(Number(id)))return;state.mode=wallet;tab311='history';status311='recent';route311=Number(id);offset311=0;setMode303('predict',false);setView('q-predict');render();load()};

let polling311=false;
setInterval(async()=>{if(polling311||!session303()||document.hidden||!$('view-q-predict')?.classList.contains('active')||tab311!=='markets'||mode303!=='predict')return;const nodes=[...(root()?.querySelectorAll('[data-pq311-pool]')||[])].slice(0,100);if(!nodes.length)return;const t=session303(),mode=state.mode;polling311=true;try{const data=await window.api(`/v311/predict/pools?wallet=${mode}&ids=${nodes.map(x=>Number(x.dataset.pq311Pool)).join(',')}`);if(t!==session303()||mode!==state.mode)return;for(const el of nodes){const m=data[el.dataset.pq311Pool];if(el.isConnected&&m)el.innerHTML=stats311(m,mode==='DEMO')}}catch{}finally{polling311=false}},20000);

function filterPanel(){let cat=state.filter,sub=state.sub;return `<form id="pqSearchForm304" class="pq304-search"><input id="pqSearch304" type="search" aria-label="Search prediction markets" placeholder="Search markets" value="${esc(query304)}"><button class="ghost" type="submit">Search</button></form><section class="pq-filter"><label>Category<select id="pqCategory">${['ALL','SPORTS','CRYPTO','ECONOMY','TECH_AI','ENTERTAINMENT','WEATHER','LEMMIQ'].map(x=>`<option value="${x}" ${cat===x?'selected':''}>${x==='ALL'?'All markets':x.replace('_',' & ')}</option>`).join('')}</select></label><label>Sort<select id="pqSort304"><option value="closing" ${sort304==='closing'?'selected':''}>Closing soon</option><option value="newest" ${sort304==='newest'?'selected':''}>Newest listed</option></select></label>${cat==='SPORTS'?`<label>Cricket competition<select id="pqSub">${['ALL','INTERNATIONAL','DOMESTIC','LEAGUES','OTHER'].map(x=>`<option value="${x}" ${sub===x?'selected':''}>${x}</option>`).join('')}</select></label>`:''}</section>`}
function category(m){return m.category||'OTHER'}
// V312 client-only live closing timer: backend close_at remains authoritative.
function tick312(){
 const host=root();if(!host)return;
 host.querySelectorAll('[data-pq312-close-ms]').forEach(el=>{
  const end=Number(el.dataset.pq312CloseMs),left=Math.max(0,Math.floor((end-Date.now())/1000));
  if(!Number.isFinite(end)||end<=0){el.textContent='Closing time unavailable';return}
  if(!left){el.textContent='Closed · predictions ended';el.classList.add('is-closed');return}
  el.classList.remove('is-closed');
  const d=Math.floor(left/86400),h=Math.floor(left%86400/3600),m=Math.floor(left%3600/60),s=left%60;
  const v=d?`${d}d ${h}h ${m}m`:(h?`${h}h ${m}m ${s}s`:`${m}m ${s}s`);
  el.textContent='Closes in '+v;
 });
}
window.setInterval(tick312,1000);

function marketRows304(markets,isDemo){const q=query304.trim().toLowerCase();const filtered=(markets||[]).filter(m=>(state.filter==='ALL'||category(m)===state.filter)&&(state.filter!=='SPORTS'||state.sub==='ALL'||m.subcategory===state.sub)&&(!q||`${m.question} ${m.category} ${m.subcategory||''}`.toLowerCase().includes(q))).sort((a,b)=>sort304==='newest'?Number(b.id)-Number(a.id):Date.parse(a.close_at)-Date.parse(b.close_at));return `<p class="pq304-count">${filtered.length} available markets · ${isDemo?'Demo USDT':'Q Predict Q'}</p><div class="pq-markets">${filtered.map(m=>{const dt=new Date(m.close_at),valid=Number.isFinite(dt.getTime());return `<article class="pq-market"><div class="pq304-market-meta"><span>${esc(category(m))}</span><small>${valid?(dt.getTime()<=Date.now()?'Closed':'Live'):'Check status'}</small></div><h4>${esc(m.question)}</h4><p>${valid?'Closes '+esc(dt.toLocaleString()):'Closing time unavailable'}</p><p class="pq312-timer" data-pq312-close-ms="${valid?dt.getTime():0}">Calculating closing time…</p><div data-pq311-pool="${Number(m.id)}">${stats311(m,isDemo)}</div><button class="ghost" data-pq-market="${Number(m.id)}">View market details</button></article>`}).join('')||'<p class="pq-note">No matching markets.</p>'}</div>`}
function marketsPanel(markets,isDemo){return `<h3 class="pq304-heading">Markets</h3>${filterPanel()}<div id="pqMarketRows304">${marketRows304(markets,isDemo)}</div>`}
function bindFilter304(){const refresh=()=>{const isDemo=state.mode==='DEMO',h=isDemo?state.demo:state.home;const host=$('pqMarketRows304');if(host){host.innerHTML=marketRows304(h?.markets||[],isDemo);bindMarkets(isDemo)}};$('pqSearchForm304')?.addEventListener('submit',e=>{e.preventDefault();query304=$('pqSearch304').value;refresh()});$('pqSort304')?.addEventListener('change',e=>{sort304=e.target.value;refresh()});}
function formBuy(){const h=state.home||{};const enabled=!!h.payments_enabled;return `<section class="pq-panel"><h3>Buy Q using USDT</h3><p>Choose Q quantity and USDT network. Price is the Q Economy reference rate plus 5%; Q is credited only to Q Predict.</p><div class="pq-form"><label>Payment in<select id="pqNetwork"><option value="TRC20">USDT – TRON (TRC20)</option><option value="BEP20">USDT – BNB Smart Chain (BEP20)</option></select></label><label>Q to purchase<input id="pqQAmount" type="number" min="1" max="100000" step="0.000001" value="${esc(state.qAmount)}"></label></div><button class="primary" id="pqQuote">Calculate purchase quote</button><div id="pqQuoteResult"></div><div class="pq-note">${enabled?'Verified-user checkout enabled. Confirm the configured receiving address before sending any USDT.':'Real-money purchase is not enabled for this account. You can calculate quotes without making a payment.'}</div><button class="ghost" id="pqClose">Close</button></section>`}
function orderMarkup(o){
 const pending=o.status==='PENDING',ready=o.status==='CREATED';
 return `<section class="pq-panel" data-pq-order-id="${Number(o.id)}" data-pq-order-network="${esc(o.network)}"><h3>Q Predict USDT checkout</h3><strong>Order ${esc(o.code)} · ${esc(o.status)} · ${esc(o.network)}</strong><p>Send exactly <b>${Number(o.expected_usdt||0).toFixed(6)} USDT</b> on ${esc(o.network)} to the address below. Use the correct network.</p><p><code data-pq-receiving-address>${esc(o.receiving_address)}</code></p><div class="pq12-qr-slot" id="pq12QrSlot" role="status">Loading payment QR…</div><button class="ghost" id="pqCopyAddress">Copy receiving address</button><button class="ghost" id="pqCopyAmount">Copy exact amount</button><button class="ghost" id="pqCopyOrderID">Copy order ID</button><p class="pq-note">${pending?'Payment submitted. Awaiting confirmed blockchain verification. Q is credited only after approval.':ready?'After sending USDT, tap I have paid. No sending address or transaction hash required.':'This order is '+esc(o.status)+'.'}</p>${ready?'<button class="primary" id="pqSubmitPaid">I have paid · Check payment</button>':''}<details><summary>Payment issue? Add transaction details (optional)</summary><p class="pq-note">Only needed if the transfer cannot be matched automatically.</p><label>Sending address (optional)<input id="pqSender" autocomplete="off" placeholder="Sending wallet address"></label><label>Transaction ID (optional)<input id="pqHash" autocomplete="off" placeholder="Blockchain transaction hash"></label>${ready||pending?'<button class="ghost" id="pqSubmitProof">Submit optional payment details</button>':''}</details><button class="ghost" id="pqClose">Close</button></section>`;
}
function bindOrder(){
 const host=$('pqDetail');
 $('pqClose')?.addEventListener('click',()=>host?.replaceChildren());
 $('pqCopyAddress')?.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(state.order.receiving_address);msg('Receiving address copied')}catch(e){msg('Clipboard unavailable',true)}});
 $('pqCopyAmount')?.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(Number(state.order.expected_usdt||0).toFixed(6));msg('Exact amount copied')}catch(e){msg('Clipboard unavailable',true)}});
 $('pqCopyOrderID')?.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(String(state.order.code||''));msg('Order ID copied')}catch(e){msg('Clipboard unavailable',true)}});
 async function submit(optional){
   if(state.busy)return;
   let payload={};
   if(optional){const sender=$('pqSender')?.value.trim()||'',tx=$('pqHash')?.value.trim()||'';
     if(!sender&&!tx)return msg('Enter a sending address or transaction hash only when requesting help.',true);
     if(sender)payload.sender_address=sender;
     if(tx)payload.tx_hash=tx;
   }
   state.busy=true;
   try{state.order=await api(`/buy/orders/${state.order.id}/submit`,jpost(payload));msg('Payment recorded. Awaiting verified blockchain receipt.');host.innerHTML=orderMarkup(state.order);bindOrder();await load()}
   catch(e){msg(e.message||'Payment not submitted',true)}finally{state.busy=false}
 }
 $('pqSubmitPaid')?.addEventListener('click',()=>submit(false));
 $('pqSubmitProof')?.addEventListener('click',()=>submit(true));
}
function activityPanel(){const h=state.home||{};return `<section class="pq-panel"><h3>Q Predict wallet activity</h3>${(h.wallet_activity||[]).map(x=>`<div class="pq-line"><span>${esc(x.kind)} · ${esc(new Date(x.at).toLocaleString())}</span><b>${x.direction==='IN'?'+':'−'}${money(x.amount_q)} Q</b></div>`).join('')||'<p>No Q Predict transactions yet.</p>'}<h3>USDT purchase orders</h3>${(h.orders||[]).map(o=>`<div class="pq-line"><span>${esc(o.code)} · ${esc(o.network)} · ${esc(o.status)}</span><b>${money(o.expected_usdt)} USDT</b></div>`).join('')||'<p>No orders yet.</p>'}<button class="ghost" id="pqClose">Close</button></section>`}
function bindMarkets(isDemo){root()?.querySelectorAll('[data-pq-market]').forEach(b=>b.onclick=()=>openMarket(Number(b.dataset.pqMarket),isDemo))}
function marketPanel(m,isDemo){const chosen=predictionSide312(m.id,isDemo);return `<section class="pq-panel"><h3>${esc(m.question)}</h3><p>${esc(m.rule||m.resolution_rule||'')}</p><p class="pq312-timer" data-pq312-close-ms="${Date.parse(m.close_at)||0}">Calculating closing time…</p><p class="pq-note">${isDemo?'Simulated Demo USDT only':'Only permitted approved verified accounts can place wagers. Winning-profit fee: 10%.'}</p><p class="pq312-final-notice">🔒 Final prediction: no cancellation, reduction or change of outcome after confirmation. Stakes stay locked until settlement or an official void/refund.</p>${chosen?`<p class="pq312-position-lock">🔒 Your ${esc(chosen)} selection is locked. You may only add to ${esc(chosen)} until the market closes.</p>`:''}<label>Stake (${isDemo?'Demo USDT':'Q Predict Q'})<input id="pqStakeAmount" type="number" min="1" max="250" step="0.01" value="10"></label><div class="pq-actions"><button class="primary" data-pq-side="YES" ${chosen&&chosen!=='YES'?'disabled title="Prediction already locked to NO"':''}>Predict YES</button><button class="ghost" data-pq-side="NO" ${chosen&&chosen!=='NO'?'disabled title="Prediction already locked to YES"':''}>Predict NO</button><button class="ghost" id="pqClose">Close</button></div></section>`}
function openMarket(id,isDemo){let h=isDemo?state.demo:state.home;let m=h?.markets?.find(x=>x.id===id);if(!m)return;let panel=$('pqDetail');panel.innerHTML=marketPanel(m,isDemo);panel.scrollIntoView({block:'start',behavior:'smooth'});$('pqClose').onclick=()=>panel.replaceChildren();panel.querySelectorAll('[data-pq-side]').forEach(b=>b.onclick=()=>stake(id,b.dataset.pqSide,isDemo))}

// V312: an accepted prediction stays on the chosen side; add to same side only.
function predictionSide312(marketId,isDemo){
 const home=isDemo?state.demo:state.home;
 const entries=isDemo?home?.my_positions:home?.positions;
 const item=(entries||[]).find(p=>Number(p.market_id)===Number(marketId)&&p.status==='OPEN'&&Number(isDemo?p.stake:p.stake_q)>0);
 return item?.outcome||null;
}
let predictionConfirmOpen312=false;
function confirmPrediction312(question,side,amount,unit,adding){
 if(predictionConfirmOpen312)return Promise.resolve(false);
 predictionConfirmOpen312=true;
 return new Promise(resolve=>{
  const message=`${question}\n\nYour selection: ${side}\nStake: ${money(amount)} ${unit}\n\nFINAL PREDICTION: Once accepted, you cannot cancel, reduce or switch your prediction. Your stake remains locked until settlement or an official void/refund. You may add more to this same outcome only while the market is open. Continue?`;
  const dialog=document.createElement('dialog');
  dialog.className='pq312-confirm-dialog';
  dialog.setAttribute('aria-labelledby','pq312ConfirmTitle');
  dialog.innerHTML=`<div class="pq312-confirm-content"><small>Q PREDICT · CONFIRM</small><h3 id="pq312ConfirmTitle">${adding?'Confirm additional stake':'Confirm & lock prediction'}</h3><p class="pq312-confirm-question">${esc(question)}</p><div class="pq312-confirm-detail"><span>Your selection</span><strong>${esc(side)}</strong><span>Stake</span><strong>${money(amount)} ${esc(unit)}</strong></div><p class="pq312-final-notice">🔒 Once accepted, you cannot cancel, reduce or switch your prediction. Your stake stays locked until settlement or an official void/refund.</p><p class="pq312-confirm-help">${adding?'You are adding to your existing '+esc(side)+' prediction.':'You may add to the same outcome only before the market closes.'}</p><div class="pq312-confirm-actions"><button type="button" class="ghost" data-pq312-cancel>Go back</button><button type="button" class="primary" data-pq312-yes>${adding?'Confirm additional stake':'Confirm & lock'}</button></div></div>`;
  let ended=false;
  const finish=ok=>{if(ended)return;ended=true;predictionConfirmOpen312=false;try{if(dialog.open)dialog.close()}catch{}dialog.remove();resolve(ok)};
  dialog.querySelector('[data-pq312-cancel]').addEventListener('click',()=>finish(false));
  dialog.querySelector('[data-pq312-yes]').addEventListener('click',()=>finish(true));
  dialog.addEventListener('cancel',e=>{e.preventDefault();finish(false)});
  dialog.addEventListener('close',()=>finish(false));
  document.body.appendChild(dialog);
  if(typeof dialog.showModal==='function'){
   try{dialog.showModal();dialog.querySelector('[data-pq312-cancel]').focus()}
   catch{finish(window.confirm(message))}
  }else{finish(window.confirm(message))}
 });
}

async function stake(mid,side,isDemo){if(state.busy)return;let n=Number($('pqStakeAmount')?.value);if(!Number.isFinite(n)||n<=0||n>250||Math.round(n*100)!==Math.round(n*10000)/100)return msg('Invalid stake. Use up to two decimals, max 250.',true);const chosen=predictionSide312(mid,isDemo);if(chosen&&chosen!==side)return msg('Your '+chosen+' selection is locked. You cannot switch sides.',true);const market=(isDemo?state.demo:state.home)?.markets?.find(m=>Number(m.id)===Number(mid));if(!await confirmPrediction312(market?.question||'This prediction market',side,n,isDemo?'Demo USDT':'Q Predict Q',chosen===side))return;
 state.busy=true;try{let payload=isDemo?{market_id:mid,outcome:side,amount:n,request_key:crypto.randomUUID().replaceAll('-','_')}:{market_id:mid,outcome:side,amount_q:n,request_key:crypto.randomUUID().replaceAll('-','_')};await (isDemo?demo('/demo/stake',jpost(payload)):api('/stake',jpost(payload)));msg('Prediction recorded');await load();$('pqDetail').replaceChildren()}catch(e){msg(e.message,true)}finally{state.busy=false}}
async function buyQuote(){state.network=$('pqNetwork').value;state.qAmount=$('pqQAmount').value;try{state.quote=await api('/quote',jpost({network:state.network,q_amount:Number(state.qAmount)}));let q=state.quote;$('pqQuoteResult').innerHTML=`<div class="pq-price"><div>Reference: ${money(q.reference_usdt_per_q)} USDT/Q</div><div>Buy premium: +5%</div><strong>Estimated ${money(q.expected_usdt)} USDT for ${money(q.q_amount)} Q</strong><small>The exact order amount includes a unique deposit marker of less than 0.01 USDT. Copy the six-decimal amount shown at checkout.</small><small>Fees include the 5% spread; do not assume a separate $1 charge.</small></div>${state.home?.payments_enabled?'<button class="primary" id="pqCreateOrder">Create payment order</button>':'<p class="pq-note">Preview only — real payments remain disabled.</p>'}`;if($('pqCreateOrder'))$('pqCreateOrder').onclick=createOrder}catch(e){msg(e.message,true)}}
async function createOrder(){if(state.busy)return;state.busy=true;try{state.order=await api('/buy/orders',jpost({network:state.network,q_amount:Number(state.qAmount)}));$('pqDetail').innerHTML=orderMarkup(state.order);bindOrder()}catch(e){msg(e.message,true)}finally{state.busy=false}}
function bindMain(){for(let e of root()?.querySelectorAll('[data-pq-mode]')||[])e.onclick=()=>{state.mode=e.dataset.pqMode;route311=null;offset311=0;state.filter='ALL';state.sub='ALL';query304='';render();load()};$('pqRefresh')?.addEventListener('click',load);$('pqCategory')?.addEventListener('change',e=>{state.filter=e.target.value;state.sub='ALL';render()});$('pqSub')?.addEventListener('change',e=>{state.sub=e.target.value;render()});bindMarkets(state.mode==='DEMO');bindFilter304();$('pqBuy')?.addEventListener('click',()=>{let el=$('pqDetail');el.innerHTML=formBuy();$('pqNetwork').value=state.network;$('pqQuote').onclick=buyQuote;$('pqClose').onclick=()=>el.replaceChildren();el.scrollIntoView({behavior:'smooth',block:'start'})});$('pqActivity')?.addEventListener('click',()=>{let el=$('pqDetail');el.innerHTML=activityPanel();$('pqClose').onclick=()=>el.replaceChildren()})}
function render(){if(!root())return;let isDemo=state.mode==='DEMO';let h=isDemo?state.demo:state.home;root().innerHTML=`<div class="pq-head"><div><h2>Q Predict</h2><small>Separate wallet · No Q Economy transfers</small></div><button class="ghost" id="pqRefresh">↻ Refresh</button></div><div class="pq304-mode-label">Wallet mode</div><div class="pq-tabs" aria-label="Prediction wallet mode"><button data-pq-mode="DEMO" class="${isDemo?'on':''}">Demo</button><button data-pq-mode="REAL_Q" class="${!isDemo?'on':''}">Q Wallet</button></div>${!isDemo&&!h?'<p>Loading Q Wallet…</p>':!isDemo&&h&&!h.verified_access?'<section class="pq-panel"><h3>Verification Required</h3><p>Real Q Predict access is restricted to approved verified users, subject to applicable authorisation.</p><button class="ghost" data-pq-support>Contact LEMMIQ Support</button></section>':(isDemo?demoHeader():wallet())+'<div id="pqDetail"></div>'+tabs311()+(tab311==='history'?historyShell311():marketsPanel(h?.markets||[],isDemo))}<div class="pq-note">${isDemo?'Practise freely with simulated Demo USDT.':'Q purchases and Q wagering remain server-gated. Buy/sell fees and market rules must be disclosed before any authorized live launch.'}</div>`;bindMain();bind311();tick312()}
let loading300=new Map();
async function load(){if(!$('view-q-predict')?.classList.contains('active')||mode303==='trading')return;const mode=state.mode,token=session303(),key=JSON.stringify([token,mode]);if(loading300.has(key))return loading300.get(key);const work=(async()=>{try{const h=await (mode==='DEMO'?demo('/home'):api('/home'));if(token!==session303())return;if(mode==='DEMO')state.demo=h;else state.home=h;if(state.mode===mode&&mode303==='predict')render()}catch(e){if(root()&&state.mode===mode&&mode303==='predict'&&token===session303())root().innerHTML=`<div class="pq-note">Unable to load Q Predict: ${esc(e.message)}</div>`}})();loading300.set(key,work);try{await work}finally{loading300.delete(key)}}
window.v300PredictReference=async()=>{const h=await api('/ui-config');return h.reference_usdt_per_q};
window.v300LoadPredict=load;
window.v302PredictConfig=()=>api('/ui-config');
async function loadIssues312(){
 const box=$('pq312Issues');if(!box)return;
 try{
  const [status,issues]=await Promise.all([window.api('/v312/cricket/admin/status'),window.api('/v312/cricket/admin/issues')]);
  if(!box.isConnected)return;
  box.innerHTML=`<h3>International cricket automation</h3><p class="micro">Demo and licensed verified Q · Real Q ${status.real_q_cricket_enabled?'ON':'OFF'} · ${status.enabled?'Running':'Disabled'} · Auto-publish ${status.auto_publish?'ON':'OFF'}. API usage ${Number(status.quota_used||0)} / ${Number(status.quota_limit||80)}; tracked ${Number(status.tracked_matches||0)} matches.</p><h4>Open result issues (${Number(status.open_issues||0)})</h4>${(issues||[]).filter(x=>x.status==='OPEN').map(x=>`<article class="pq-admin-order"><strong>Market #${Number(x.market_id)} · ${esc(x.type)}</strong><p>${esc(x.reason)}</p><small>Case #${Number(x.id)}</small><button type="button" class="ghost" data-pq312-close="${Number(x.id)}">Mark reviewed</button></article>`).join('')||'<p>No outstanding result issues.</p>'}<button class="ghost" id="pq312Reload">Refresh cricket status</button>`;
  box.querySelectorAll('[data-pq312-close]').forEach(b=>b.onclick=async()=>{
   const note=prompt('Review note (at least 10 characters). Closing an issue does not change any result or balance.');
   if(!note)return;if(note.trim().length<10)return msg('Provide a review note.',true);
   try{await window.api('/v312/cricket/admin/issues/'+Number(b.dataset.pq312Close)+'/close',{method:'POST',body:JSON.stringify({note:note.trim()})});msg('Issue marked reviewed');loadIssues312()}catch(e){msg(e.message||'Unable to close issue',true)}
  });
  $('pq312Reload')?.addEventListener('click',loadIssues312);
 }catch(e){if(box.isConnected)box.innerHTML=`<h4>Cricket automation</h4><p class="micro">Monitoring unavailable: ${esc(e.message||'Unable to load')}</p>`}
}

async function adminLoad(){let host=$('pqAdmin');if(!host)return;try{state.admin=await api('/admin');renderAdmin();loadIssues312()}catch(e){host.textContent='Master Admin permission required for Q Predict treasury controls.'}}
async function loadWithdrawals313(){
 const host=$('pq313Withdrawals');if(!host)return;
 try{
  const data=await window.api('/v21311/redeem/admin/requests');
  if(!host.isConnected)return;
  const requests=(data.requests||[]);
  host.innerHTML=requests.map(o=>`<article class="pq-admin-order"><strong>${esc(o.code)} · ${esc(o.status)} · ${esc(o.network)}</strong><p>User #${Number(o.user_id)} · ${money(o.q_amount)} Q → ${Number(o.payout_usdt||0).toFixed(6)} USDT</p><small>Recipient: ${esc(o.destination)}</small>${o.status==='PENDING'?`<div class="pq-actions"><button class="ghost" data-pq-withdraw-complete="${Number(o.id)}">Verify outgoing TXID & mark paid</button><button class="ghost" data-pq-withdraw-reject="${Number(o.id)}">Reject and refund Q</button></div>`:''}</article>`).join('')||'<p>No withdrawal requests.</p>';
  host.querySelectorAll('[data-pq-withdraw-complete]').forEach(b=>b.onclick=async()=>{
   const tx=prompt('Enter the actual outgoing USDT transaction hash. Withdrawal completion always requires blockchain verification.');
   if(!tx)return;
   try{await window.api(`/v21311/redeem/admin/requests/${Number(b.dataset.pqWithdrawComplete)}/complete`,jpost({tx_hash:tx.trim()}));msg('Outgoing transfer verified; withdrawal marked PAID');adminLoad()}catch(e){msg(e.message||'Withdrawal verification failed',true)}
  });
  host.querySelectorAll('[data-pq-withdraw-reject]').forEach(b=>b.onclick=async()=>{
   const reason=prompt('Rejection reason (at least eight characters; held Q will be refunded)');
   if(!reason||reason.trim().length<8)return;
   if(!confirm('Reject withdrawal and return held Q to user?'))return;
   try{await window.api(`/v21311/redeem/admin/requests/${Number(b.dataset.pqWithdrawReject)}/reject`,jpost({reason:reason.trim()}));msg('Withdrawal rejected and Q hold refunded');adminLoad()}catch(e){msg(e.message||'Withdrawal rejection failed',true)}
  });
 }catch(e){if(host.isConnected)host.textContent='Withdrawals unavailable: '+(e.message||'Request failed')}
}
function renderAdmin(){
 const a=state.admin,host=$('pqAdmin');if(!a||!host)return;
 const orders=(a.orders||[]),manual=!!a.manual_approval_enabled;
 host.innerHTML=`<section class="pq-panel pq313-payments-top"><h3>USDT Deposits & Withdrawals</h3><p class="micro">Q Predict wallet only · independent of Q Economy. Incoming deposits and outgoing withdrawals are separate processes.</p><h4>USDT Deposits · ${orders.filter(o=>o.status==='PENDING').length} pending</h4><div class="pq-admin-list">${orders.map(o=>`<div class="pq-admin-order" data-pq-order-id="${Number(o.id)}" data-pq-status="${esc(o.status)}" data-pq-has-hash="${o.tx_hash?'1':'0'}"><strong>${esc(o.code)} · ${esc(o.status)} · ${esc(o.network)}</strong><p>User #${Number(o.user_id)} · ${money(o.q_amount)} Q · ${Number(o.expected_usdt||0).toFixed(6)} USDT</p><small>${esc(o.tx_hash||'No TXID submitted · user proof optional')}</small>${o.status==='PENDING'?`<div class="pq-actions"><button class="primary" data-pq-approve="${Number(o.id)}">Verify chain & approve</button>${manual?`<button class="ghost" data-pq-manual="${Number(o.id)}">Approve without TXID (unverified)</button>`:''}<button class="ghost" data-pq-reject="${Number(o.id)}">Reject</button></div>`:''}${o.notes?`<small>${esc(o.notes)}</small>`:''}</div>`).join('')||'<p>No purchase orders yet.</p>'}</div><p class="micro">${manual?`Manual approval limit: ${money(a.manual_approval_max_usdt)} USDT per order. Only Master Admin can issue unverified credits, with a recorded reason.`:'Manual approval without blockchain proof is disabled by default. Enable it only under an approved operator policy.'}</p><h4>USDT Withdrawals</h4><div id="pq313Withdrawals">Loading withdrawal requests…</div></section><section class="pq-panel"><h3>USDT Treasury Settings</h3><p class="micro">Dedicated Q Predict receiving addresses — do not use Q Economy wallets.</p><div class="pq-form">${['TRC20','BEP20'].map(n=>{let t=(a.treasury||[]).find(x=>x.network===n);return `<label>${n} Admin receiving address<input id="pqAdminAddress${n}" value="${esc(t?.address||'')}" placeholder="Dedicated ${n} treasury address"><button type="button" class="ghost" data-pq-save="${n}">Save ${n} address</button></label>`}).join('')}</div></section><section class="pq-panel" id="pq312Issues"><h4>Cricket automation & result disputes</h4><p>Loading exceptions…</p></section>`;
 host.querySelectorAll('[data-pq-save]').forEach(b=>b.onclick=async()=>{const n=b.dataset.pqSave;try{await api(`/admin/treasury/${n}`,{method:'PUT',body:JSON.stringify({address:$('pqAdminAddress'+n).value,active:true})});msg('Treasury saved');adminLoad()}catch(e){msg(e.message,true)}});
 host.querySelectorAll('[data-pq-approve]').forEach(b=>b.onclick=async()=>{
  if(!confirm('Verify one confirmed on-chain USDT transfer before crediting Q?'))return;
  try{await api(`/admin/buy/${Number(b.dataset.pqApprove)}/approve`,jpost({}));msg('Transfer verified and Q credited');adminLoad()}catch(e){msg(e.message||'Blockchain verification failed',true)}
 });
 host.querySelectorAll('[data-pq-manual]').forEach(b=>b.onclick=async()=>{
  const id=Number(b.dataset.pqManual),o=orders.find(x=>Number(x.id)===id);
  if(!o)return;
  const reason=prompt('MANDATORY: Reason for issuing Q WITHOUT verified blockchain payment (20+ characters).');
  if(!reason||reason.trim().length<20)return msg('Manual approval requires a reason of at least 20 characters.',true);
  const confirmText=prompt(`This will credit ${money(o.q_amount)} Q to user #${Number(o.user_id)} WITHOUT proof of USDT payment. Type MANUAL APPROVE to authorise this unverified credit.`);
  if(confirmText!=='MANUAL APPROVE')return msg('Manual approval cancelled. No Q credited.',true);
  try{await api(`/admin/buy/${id}/manual-approve`,jpost({reason:reason.trim(),confirmation:'MANUAL_APPROVE_UNVERIFIED'}));msg('MANUAL UNVERIFIED CREDIT issued and audited. No blockchain payment was confirmed.');adminLoad()}catch(e){msg(e.message||'Manual approval failed',true)}
 });
 host.querySelectorAll('[data-pq-reject]').forEach(b=>b.onclick=async()=>{let reason=prompt('Reason for rejecting purchase (minimum 8 characters)');if(!reason||reason.trim().length<8)return;try{await api(`/admin/buy/${Number(b.dataset.pqReject)}/reject`,jpost({reason:reason.trim()}));msg('Order rejected');adminLoad()}catch(e){msg(e.message,true)}});
 loadWithdrawals313();
}
window.v307LoadPredictTreasury=async()=>{mount();if($('pqAdmin'))await adminLoad()};
function mount(){const host=$('view-q-predict');if(host&&root()){host.classList.remove('v2138-active');host.classList.add('v21310-active');init303()}const existing=$('v29PredictAutomation');if(existing&&!$('pqAdmin')){let n=document.createElement('section');n.id='pqAdmin';n.className='pq-admin';existing.before(n);/* V307: selected-section load only */}}
document.addEventListener('DOMContentLoaded',()=>{mount();document.body.addEventListener('click',e=>{if(e.target.closest('[data-view="q-predict"]'))setTimeout(()=>{if($('view-q-predict')?.classList.contains('active')&&!root()?.childElementCount&&mode303==='predict')refresh303()},140);/* V307: no eager treasury load */});let observer=new MutationObserver(()=>{if(!root()||($('v29PredictAutomation')&&!$('pqAdmin')))mount()});observer.observe(document.body,{childList:true,subtree:true})});
})();
// V300_INSTALLED
// V302_INSTALLED
// V303_INSTALLED
// V304_INSTALLED
