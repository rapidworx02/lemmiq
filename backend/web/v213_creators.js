/* V2138_COMBINED */
/* V21361_NAV_TRANSFER_SCHEDULE */
/* V21360_CREATOR_UX */
/* V21354_CREATOR_AUTOPUBLISH */
/* LEMMIQ V2.13 Q Creators — public discovery, creator studio and Q transactions.
 * Frontend only calls existing-auth backend endpoints. Never calculates wallet debits.
 */
(()=>{
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=x=>Number(x||0).toLocaleString(undefined,{maximumFractionDigits:6});
  const dt=x=>x?new Date(x).toLocaleDateString():'';
  const req=(url,options={})=>api('/v213/creators'+url,options);
  const json=(method,body)=>({method,body:JSON.stringify(body)});
  const key=()=>crypto.randomUUID();
  const state={mode:'discover',mine:null,config:null,users:[],requests:[],selected:null,detail:null,earnings:null,filter:'',category:'',media:new Set()};
  const root=()=>$('v213CreatorsApp');
  const feedback=(msg,error=false)=>{const t=$('v213Status');if(t){t.textContent=msg;t.classList.toggle('error',error)}else if(typeof toast==='function')toast(msg,error)};
  function cleanMedia(){state.media.forEach(u=>URL.revokeObjectURL(u));state.media.clear()}
  const labels={PUBLIC:'Public',FOLLOWERS:'Followers only',SUBSCRIBERS:'Subscribers only',PPV:'Pay to unlock'};
  const header=()=>`<div class="v213-hero"><div><span class="eyebrow">ONE LEMMIQ Q ECONOMY</span><h2>Q Creators</h2><p>Discover professional creators, support their work and connect using Q.</p></div><div class="v213-hero-right"><span>Q Creators Beta</span><small>Creator payments ${state.config?.payments_enabled?'enabled':'not yet enabled'}</small></div></div>
   <nav class="v213-tabs" aria-label="Q Creators navigation">${[['discover','Discover'],['following','Following'],['studio','Creator Studio'],['requests','Requests'],['earnings','My Earnings']].map(([k,v])=>`<button type="button" data-mode="${k}" class="${state.mode===k?'active':''}">${v}</button>`).join('')}</nav>
   <p class="v213-notice" id="v213Status" role="status" aria-live="polite">Approved creators publish instantly. Admins can review content afterward. Explicit content and USDT cash-out are unavailable.</p>`;
  const avatar=(name,cls='',url='')=>url?`<img class="v213-avatar ${cls}" src="${esc(url)}" alt="${esc(name)}" loading="lazy">`:`<span class="v213-avatar ${cls}">${esc((name||'Q').split(/\s+/).map(x=>x[0]).slice(0,2).join('').toUpperCase())}</span>`;
  function card(c){return `<button type="button" class="v213-profile-card" data-profile="${c.id}"><span class="v213-profile-cover">${avatar(c.display_name,'',c.avatar_url)}</span><strong>${esc(c.display_name)}</strong><small>@${esc(c.username)} · ${esc(c.category)}</small><span class="v213-card-bio">${esc(c.bio||'New LEMMIQ creator')}</span><span class="v213-card-foot"><b>${c.monthly_q?num(c.monthly_q)+' Q/month':'Free subscription'}</b><small>${c.followers} followers</small></span></button>`}
  function discover(){return `<div class="v213-toolbar"><input type="search" id="v213Search" placeholder="Find creators by name or @username" value="${esc(state.filter)}"><select id="v213Category"><option value="">All categories</option>${['FASHION','LIFESTYLE','FITNESS','MUSIC','ART','EDUCATION','GAMING','GLAMOUR','OTHER'].map(k=>`<option ${state.category===k?'selected':''}>${k}</option>`).join('')}</select><button type="button" class="ghost" data-action="search">Search</button></div><div class="v213-grid">${state.users.map(card).join('')||'<div class="v213-empty">No creators found. Approved profiles will appear here.</div>'}</div>`}
  function post(p){return `<article class="v213-post"><div class="v213-post-meta"><span>${esc(p.kind)} · ${esc(labels[p.visibility]||p.visibility)}</span><small>${dt(p.created_at)}${p.review!=='APPROVED'?' · '+esc(p.review):''}</small></div><h4>${esc(p.title)}</h4>${p.teaser?`<p class="micro">${esc(p.teaser)}</p>`:''}${p.unlocked?`<div class="v213-post-body">${esc(p.body||'')}</div>${p.media_url?`<div class="v213-media" data-media-post="${p.id}"><span class="micro">Loading private media…</span></div>`:''}`:`<div class="v213-locked">🔒 ${p.visibility==='PPV'?`Unlock for ${num(p.price_q)} Q`:p.visibility==='SUBSCRIBERS'?'Subscribers only':'Follow to unlock'}</div>${p.visibility==='PPV'?`<button type="button" class="primary" data-action="unlock" data-post="${p.id}">Unlock · ${num(p.price_q)} Q</button>`:''}`}</article>`}
  function profile(){const d=state.detail,c=d?.profile;if(!c)return '<div class="v213-empty">Creator profile unavailable.</div>';
    return `<button type="button" class="ghost v213-back" data-action="back">← Back to ${state.mode==='following'?'Following':'Discover'}</button><div class="v213-profile-detail"><div class="v213-profile-identity">${avatar(c.display_name,'large',c.avatar_url)}<div><h3>${esc(c.display_name)}</h3><small>@${esc(c.username)} · ${esc(c.category)} · ${esc(c.level)}</small><p>${esc(c.bio)}</p><small>${num(c.followers)} followers · ${num(c.subscribers)} subscribers</small></div></div><div class="v213-actions"><button type="button" class="ghost" data-action="follow">${c.following?'Unfollow':'Follow'}</button>${c.mine?'':`<button type="button" class="primary" data-action="subscribe" ${c.subscribed?'disabled':''}>${c.subscribed?'Subscribed':c.monthly_q?`Subscribe · ${num(c.monthly_q)} Q / 30 days`:'Subscribe free'}</button>`}${c.tips_enabled&&!c.mine?'<button type="button" class="ghost" data-action="tip">Tip Q</button>':''}</div>${!c.mine?`<div class="v213-service-grid">${[['CHAT','Paid chat request',c.chat_q],['VOICE','Voice session request',c.voice_q],['VIDEO','Video session request',c.video_q]].filter(x=>x[2]>0).map(([kind,name,price])=>`<button type="button" class="ghost" data-service="${kind}">${esc(name)}<small>${num(price)} Q</small></button>`).join('')}</div>`:''}</div><h3>Creator posts</h3><div class="v213-posts">${d.posts.map(post).join('')||'<div class="v213-empty">No published posts yet.</div>'}</div>`;
  }
  function studio(){const c=state.mine?.profile||{};return `<article class="card glass v213-studio"><div class="section-head"><div><span class="eyebrow">BECOME A CREATOR</span><h3>Professional Profile</h3></div><span class="v213-status">${c.status||'NOT APPLIED'}</span></div><p class="micro">Your personal username stays separate. Set a professional username in Professional Identity. Both share one login and Q Economy. Submit your profile for Master Admin review. Adult privileges are a future separate verification process, not enabled here.</p>${c.id?'<button class="ghost" type="button" data-action="myprofile">Preview my public profile and posts</button>':''}<form data-form="profile" class="v213-form"><label>About your content<textarea name="bio" maxlength="900" rows="3" placeholder="Tell your community about your work">${esc(c.bio||'')}</textarea></label><div class="v213-two"><label>Category<select name="category">${['FASHION','LIFESTYLE','FITNESS','MUSIC','ART','EDUCATION','GAMING','GLAMOUR','OTHER'].map(x=>`<option ${c.category===x?'selected':''}>${x}</option>`).join('')}</select></label><label>Non-explicit content level<select name="level"><option value="MAINSTREAM" ${c.level==='MAINSTREAM'?'selected':''}>Mainstream</option><option value="GLAMOUR" ${c.level==='GLAMOUR'?'selected':''}>Glamour / Non-explicit</option></select></label></div><div class="v213-two"><label>Subscription (Q / 30 days)<input name="monthly_q" type="number" min="0" max="100000" step="0.01" value="${c.monthly_q??0}"></label><label>Paid chat (Q per request)<input name="chat_q" type="number" min="0" max="100000" step="0.01" value="${c.chat_q??0}"></label><label>Voice session price (Q)<input name="voice_q" type="number" min="0" max="100000" step="0.01" value="${c.voice_q??0}"></label><label>Video session price (Q)<input name="video_q" type="number" min="0" max="100000" step="0.01" value="${c.video_q??0}"></label></div><label class="v213-check"><input name="tips_enabled" type="checkbox" ${c.tips_enabled!==false?'checked':''}> Accept voluntary Q tips</label><label class="v213-check"><input name="adult_requested" type="checkbox" ${c.adult_requested?'checked':''}> Request information about a future separately verified 18+ service (not enabled)</label><button class="primary" type="submit">${c.status?'Save professional settings':'Apply for Professional Profile'}</button></form></article>${c.status==='APPROVED'?`<article class="card glass v213-studio"><h3>Publish content</h3><p class="micro">Approved creators publish immediately. Admins can audit and remove content later.</p><form data-form="post" class="v213-form"><label>Title<input required minlength="3" maxlength="140" name="title" placeholder="Post title"></label><label>Preview text<input name="teaser" maxlength="240" placeholder="What fans see before unlocking"></label><label>Content<textarea required name="body" maxlength="12000" placeholder="Write your post"></textarea></label><div class="v213-two"><label>Visibility<select name="visibility"><option value="PUBLIC">Public</option><option value="FOLLOWERS">Followers only</option><option value="SUBSCRIBERS">Subscribers only</option><option value="PPV">Pay to unlock</option></select></label><label>Unlock price (Q; only for PPV)<input name="price_q" type="number" min="0" step="0.01" value="0"></label></div><label>Optional photo/video (shown according to your access setting)<input name="media" type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm"></label><button type="submit" class="primary">Publish post</button></form></article>`:''}`}
  function requests(){return `<h3>Paid requests & sessions</h3><p class="micro">Q stays reserved until the fan confirms delivery. Creator replies and sessions are managed here. Live call billing is not automated in this release.</p><div class="v213-stack">${state.requests.map(r=>`<article class="v213-request"><div><strong>${esc(r.kind)} · ${esc(r.name)}</strong><small>@${esc(r.username)} · ${num(r.amount_q)} Q · ${esc(r.status)}</small></div><p>${esc(r.message||'Scheduled session')}</p>${r.scheduled_at?`<small>Requested: ${esc(new Date(r.scheduled_at).toLocaleString())}</small>`:''}${r.reply?`<blockquote>${esc(r.reply)}</blockquote>`:''}<div class="v213-actions">${r.role==='CREATOR'&&r.status==='REQUESTED'?`<button type="button" class="ghost" data-request="${r.id}" data-step="ACCEPT">Accept</button>`:''}${r.role==='CREATOR'&&r.kind==='CHAT'&&['REQUESTED','ACCEPTED'].includes(r.status)?`<button type="button" class="primary" data-request="${r.id}" data-step="REPLY">Send reply</button>`:''}${r.role==='CREATOR'&&['VOICE','VIDEO'].includes(r.kind)&&r.status==='ACCEPTED'?`<button type="button" class="ghost" data-request="${r.id}" data-step="DELIVERED">Mark session delivered</button>`:''}${r.role==='FAN'&&r.status==='DELIVERED'?`<button type="button" class="primary" data-request="${r.id}" data-step="CONFIRM">Confirm delivery and release Q</button>`:''}${(r.role==='CREATOR'&&['REQUESTED','ACCEPTED'].includes(r.status))||(r.role==='FAN'&&r.status==='REQUESTED')?`<button type="button" class="ghost" data-request="${r.id}" data-step="CANCEL">Cancel / refund</button>`:''}</div></article>`).join('')||'<div class="v213-empty">No paid requests yet.</div>'}</div>`}
  function earns(){const x=state.earnings||state.mine?.earnings||{};return `<article class="card glass v213-studio"><h3>Creator Earnings Wallet</h3><div class="v213-earnings-grid"><div><small>Available earnings</small><strong>${num(x.available_q)} Q</strong></div><div><small>Lifetime net earned</small><strong>${num(x.lifetime_q)} Q</strong></div><div><small>Moved to Q Wallet</small><strong>${num(x.transferred_q)} Q</strong></div></div><p class="micro">This is earned Q accounting, not a second token. Moving Q to your normal LEMMIQ wallet does not convert it to USDT.</p>${state.mine?.profile?.status==='APPROVED'?`<form data-form="transfer" class="v213-transfer"><label>Transfer available Q to normal wallet<input type="number" name="amount_q" min="0.000001" step="0.000001" max="100000" required placeholder="Amount Q"></label><button class="primary" type="submit">Transfer Q</button></form><p id="v213TransferStatus" role="status" aria-live="polite" class="micro" style="margin-top:12px"></p>`:''}</article><h3>Earnings history</h3><div class="v213-stack">${(x.transactions||[]).map(t=>`<div class="v213-line"><span>${esc(t.kind)} · ${esc(t.status)}<small>${dt(t.created_at)}</small></span><span>Gross ${num(t.gross_q)} Q<small>Fee ${num(t.fee_q)} Q · Net ${num(t.net_q)} Q</small></span></div>`).join('')||'<div class="v213-empty">No earnings recorded.</div>'}</div>`}
  function render(){const host=root();if(!host)return;cleanMedia();let inner='';if(state.selected)inner=profile();else if(state.mode==='discover'||state.mode==='following')inner=discover();else if(state.mode==='studio')inner=studio();else if(state.mode==='requests')inner=requests();else if(state.mode==='earnings')inner=earns();host.innerHTML=header()+'<div class="v213-main">'+inner+'</div>';window.v2136CreatorReady?.();loadMedia().catch(()=>{});if(window.v2131CreatorsDecorate)window.v2131CreatorsDecorate({selected:state.selected,mode:state.mode,mine:state.mine?.profile||null}).catch(e=>console.warn('Q Creator media:',e.message))}
  async function loadMedia(){for(const node of root()?.querySelectorAll('[data-media-post]')||[]){const id=node.dataset.mediaPost;try{const r=await fetch(`/v213/creators/posts/${id}/media`,{headers:authHeaders()});if(!r.ok)throw Error('Media unavailable');const type=r.headers.get('content-type')||'';const url=URL.createObjectURL(await r.blob());state.media.add(url);if(!node.isConnected){URL.revokeObjectURL(url);state.media.delete(url);continue}const el=document.createElement(type.startsWith('video/')?'video':'img');el.src=url;el.controls=type.startsWith('video/');el.loading='lazy';el.style.maxWidth='100%';node.replaceChildren(el)}catch{node.textContent='Media preview unavailable.'}}}
  async function reload(){if(!root())return;try{[state.config,state.mine]=await Promise.all([req('/config'),req('/me')]);if(state.selected){state.detail=await req(`/profile/${state.selected}`)}else if(['discover','following'].includes(state.mode)){state.users=await req('/discover?'+new URLSearchParams({qtext:state.filter,category:state.category,following:state.mode==='following'}))}else if(state.mode==='requests'){state.requests=await req('/requests')}else if(state.mode==='earnings'){state.earnings=await req('/earnings').catch(e=>({error:e.message}))}render()}catch(e){if(root())root().innerHTML='<div class="v213-empty">Unable to load Q Creators: '+esc(e.message)+'</div>'}}
  function confirmPay(label,amount){if(!state.config?.payments_enabled)throw Error('Q Creator payments are not enabled yet by LEMMIQ Admin.');return window.confirm(`${label}\nAmount: ${num(amount)} Q\nLEMMIQ will calculate commission automatically. Confirm payment?`)}
  async function action(b){const what=b.dataset.action;try{
    if(what==='back'){state.selected=null;state.detail=null;return reload()}
    if(what==='myprofile'){if(!state.mine?.profile)return;state.selected=state.mine.profile.id;return reload()}
    if(what==='search'){state.filter=$('v213Search')?.value.trim()||'';state.category=$('v213Category')?.value||'';return reload()}
    const c=state.detail?.profile;
    if(!c)return;
    if(what==='follow'){await req(`/profile/${c.id}/follow`,{method:c.following?'DELETE':'POST'});return reload()}
    if(what==='subscribe'){
      if(c.monthly_q && !confirmPay('Subscribe for 30 days',c.monthly_q))return;
      await req(`/profile/${c.id}/subscribe`,json('POST',{request_key:key()}));feedback('Subscription successful');return reload()}
    if(what==='unlock'){
      const p=state.detail?.posts.find(p=>p.id===Number(b.dataset.post));if(!p)return;
      if(!confirmPay('Unlock '+p.title,p.price_q))return;
      await req(`/posts/${p.id}/unlock`,json('POST',{request_key:key()}));feedback('Content unlocked');return reload()}
    if(what==='tip')return tipModal(c);
  }catch(e){feedback(e.message,true)}}
  function tipModal(c){openModal(`<h3>Tip @${esc(c.username)}</h3><p class="micro">Tips are voluntary, with an automatic LEMMIQ commission.</p><label>Q amount<input id="v213TipAmount" type="number" min="0.01" max="100000" step="0.01" value="10"></label><button id="v213TipSubmit" class="primary full" type="button">Pay tip</button>`);$('v213TipSubmit').onclick=async()=>{try{const amount=Number($('v213TipAmount').value);if(!Number.isFinite(amount)||amount<=0)throw Error('Enter a valid Q amount');if(!confirmPay('Send a creator tip',amount))return;await req(`/profile/${c.id}/tip`,json('POST',{amount_q:amount,request_key:key()}));closeModal();feedback('Tip sent');await reload()}catch(e){toast(e.message,true)}}}
  function serviceModal(kind){
    const c=state.detail.profile,price={CHAT:c.chat_q,VOICE:c.voice_q,VIDEO:c.video_q}[kind];
    const scheduled=kind!=='CHAT';
    const now=new Date(),initial=new Date(now.getTime()+86400000);
    initial.setHours(18,0,0,0);
    const toInput=d=>new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
    const min=new Date(now.getTime()+6*60000),max=new Date(now.getTime()+60*86400000);
    const tz=Intl.DateTimeFormat().resolvedOptions().timeZone||'your local timezone';
    openModal(`<h3>${esc(kind)} request · ${num(price)} Q</h3><p class="micro">Q is reserved until your session is confirmed or cancelled. Calls are arranged with the creator; automatic joining is not enabled yet.</p><label>Message to creator<textarea id="v213RequestMessage" rows="3" placeholder="What would you like to discuss?"></textarea></label>${scheduled?`<label>Choose a date and time (${esc(tz)})<input id="v213RequestDate" type="datetime-local" min="${toInput(min)}" max="${toInput(max)}" value="${toInput(initial)}" required></label><p class="micro">Choose a time between 5 minutes and 60 days from now. Your local time is converted automatically.</p>`:''}<p id="v213RequestError" role="alert" class="micro" style="color:#ff9cac"></p><button id="v213RequestSend" type="button" class="primary full">Reserve ${num(price)} Q & request</button>`);
    $('v213RequestSend').onclick=async()=>{
      const button=$('v213RequestSend'),out=$('v213RequestError');
      try{
        const message=$('v213RequestMessage')?.value?.trim()||'';
        if(message.length<3)throw Error('Please write a short message for the creator.');
        const payload={kind,message,request_key:key()};
        if(scheduled){
          const raw=$('v213RequestDate')?.value||'';
          const chosen=new Date(raw);
          if(!raw||!Number.isFinite(chosen.getTime()))throw Error('Please choose a valid date and time.');
          if(chosen.getTime()<=Date.now()+5*60000 || chosen.getTime()>Date.now()+60*86400000)throw Error('Choose a time between 5 minutes and 60 days from now.');
          payload.scheduled_at=chosen.toISOString();
        }
        if(!confirmPay('Reserve Q for '+kind.toLowerCase(),price))return;
        button.disabled=true;
        await req(`/profile/${c.id}/request`,json('POST',payload));
        closeModal();state.selected=null;state.mode='requests';await reload();
      }catch(e){if(out)out.textContent=e.message||'Could not submit request';else toast(e.message||String(e),true)}
      finally{if(button?.isConnected)button.disabled=false}
    };
  }
  async function requestAction(id,step){try{let reply='';if(step==='REPLY'){reply=prompt('Reply to the paid chat request:')||'';if(reply.trim().length<3)return;}if(['CONFIRM','CANCEL','DELIVERED'].includes(step)&&!confirm(`Confirm ${step.toLowerCase()} for this paid request?`))return;await req(`/requests/${id}/action`,json('POST',{action:step,reply}));await reload()}catch(e){feedback(e.message,true)}}
  async function submitForm(form){const f=Object.fromEntries(new FormData(form).entries());const btn=form.querySelector('[type=submit]');btn.disabled=true;try{
    if(form.dataset.form==='profile'){const payload={bio:f.bio||'',category:f.category||'LIFESTYLE',level:f.level||'MAINSTREAM',adult_requested:!!f.adult_requested,tips_enabled:!!f.tips_enabled,monthly_q:Number(f.monthly_q||0),chat_q:Number(f.chat_q||0),voice_q:Number(f.voice_q||0),video_q:Number(f.video_q||0)};await req('/me',json('PUT',payload));await reload();feedback('Professional profile saved. Only initial creator approval is required; approved creators can publish immediately.')}
    else if(form.dataset.form==='post'){const payload={title:f.title,teaser:f.teaser||'',body:f.body||'',visibility:f.visibility,price_q:Number(f.price_q||0),level:state.mine?.profile?.level||'MAINSTREAM'};const p=await req('/posts',json('POST',payload));if(f.media?.size){const fd=new FormData();fd.append('file',f.media);await req(`/posts/${p.id}/media`,{method:'POST',body:fd})}form.reset();feedback('Post published immediately. Admins may review it for compliance.')}
    else if(form.dataset.form==='transfer'){
      const amount=Number(f.amount_q),status=$('v213TransferStatus');
      const write=(message,error=false)=>{if(status){status.textContent=message;status.style.color=error?'#ff9cac':'#8be1b6'}else feedback(message,error)};
      if(!Number.isFinite(amount)||amount<=0){write('Enter a positive Q amount.',true);return}
      if(amount>Number(state.earnings?.available_q??state.mine?.earnings?.available_q??0)+0.0000001){write('Amount exceeds your available creator earnings.',true);return}
      if(!confirm(`Transfer ${num(amount)} earned Q into your main Q Wallet?`))return;
      write('Transferring Q…');
      try{
        const moved=await req('/earnings/transfer',json('POST',{amount_q:amount}));
        if(!moved||Math.abs(Number(moved.transferred_q)-amount)>0.0000001)throw Error('Transfer response could not be verified; refresh your balances before trying again.');
        form.reset();
        write(`Transferred ${num(amount)} Q. Refreshing balances…`);
        state.earnings=await req('/earnings');
        if(state.mine)state.mine.earnings=state.earnings;
        if(typeof window.loadQEconomy==='function')window.loadQEconomy().catch(()=>{});
        write(`Success: ${num(amount)} Q moved to your main wallet. Available creator earnings: ${num(state.earnings.available_q)} Q.`);
        const list=$('v213CreatorsApp');const old=list?.querySelector('.v213-earnings-grid');
        if(old){const items=old.querySelectorAll('strong');if(items[0])items[0].textContent=num(state.earnings.available_q)+' Q';if(items[2])items[2].textContent=num(state.earnings.transferred_q)+' Q'}
      }catch(err){write(err.message||'Transfer failed; your Q was not intentionally debited by this screen.',true)}
    }
  }catch(e){feedback(e.message,true)}finally{if(btn)btn.disabled=false}}
  document.addEventListener('DOMContentLoaded',()=>{const link=$('v213OpenCreators');if(link)link.addEventListener('click',()=>setView('q-creators'));const app=root();if(!app)return;
    const me=$('v213SwitchProfessional');if(me)me.addEventListener('click',()=>{state.mode='studio';state.selected=null;setView('q-creators')});
    app.addEventListener('click',async ev=>{const b=ev.target.closest('button');if(!b)return;
      if(b.dataset.mode){state.mode=b.dataset.mode;state.selected=null;state.category='';state.filter='';await reload();return}
      if(b.dataset.profile){state.selected=Number(b.dataset.profile);await reload();return}
      if(b.dataset.service){serviceModal(b.dataset.service);return}
      if(b.dataset.request){await requestAction(Number(b.dataset.request),b.dataset.step);return}
      if(b.dataset.action)await action(b);
    });
    app.addEventListener('submit',ev=>{if(!ev.target.matches('form[data-form]'))return;ev.preventDefault();submitForm(ev.target)});
  });
  window.loadQCreators=reload;
})();
