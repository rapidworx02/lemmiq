/* LEMMIQ V2.12.4 — Organised Master Admin + independent secure password recovery.
 * All existing controls are MOVED (not cloned/replaced) to retain event handlers.
 * Delegated admin UI stays on the existing role-controlled implementation.
 */
(()=>{
  'use strict';
  const ROOT_ID='view-q-admin';
  const GROUPS=[
    ['overview','Overview','Dashboard and urgent actions'],
    ['users','Users & Support','Search, manage accounts and recovery'],
    ['creators','Q Creators','Applications, post review, Q earnings and commission'],
    ['economy','Q Economy','Packages, rewards, treasury and ledger'],
    ['payments','Payments & USDT','Incoming, withdrawals and wallets'],
    ['market','Q Market','Orders and disputes'],
    ['predict','Q Predict','Markets, drafts and settlements'],
    ['analytics','Reports & Activity','Usage, monitoring and audit history'],
    ['communication','Communication','Official announcements and broadcasts'],
    ['calling','Calling Controls','Voice and video policy'],
    ['settings','Settings & Security','Q settings, pricing and admin permissions']
  ];
  const NAME=Object.fromEntries(GROUPS.map(x=>[x[0],x[1]]));
  const byId=id=>document.getElementById(id);
  const esc=t=>String(t??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  let current='overview', isMaster=false, resetUser=null, lastPassword='';
  let installing=false;
  function host(){return byId(ROOT_ID)}
  function selectGroup(group){
    if(!NAME[group])group='overview';
    if(group!=='users')clearPassword();
    current=group;
    document.querySelectorAll('[data-v2124-admin-panel]').forEach(e=>e.hidden=e.dataset.v2124AdminPanel!==group);
    document.querySelectorAll('[data-v2124-admin-nav]').forEach(e=>{
      const active=e.dataset.v2124AdminNav===group;
      e.classList.toggle('active',active);
      e.setAttribute('aria-current',active?'page':'false');
    });
    document.dispatchEvent(new CustomEvent('lemmiq:admin-section',{detail:group}));
    const dropdown=byId('v2124AdminMobileMenu');if(dropdown)dropdown.value=group;
    const h=byId('v2124ActiveHeading');if(h)h.textContent=NAME[group];
  }
  function makeShell(){
    let shell=byId('v2124AdminShell');if(shell)return shell;
    const view=host(),hero=view?.querySelector('.q28-hero');if(!view||!hero)return null;
    shell=document.createElement('div');shell.id='v2124AdminShell';shell.className='v2124-admin-shell';
    const menu=GROUPS.map(([key,title])=>`<button class="v2124-admin-nav-btn" type="button" data-v2124-admin-nav="${key}">${esc(title)}</button>`).join('');
    const options=GROUPS.map(([key,title])=>`<option value="${key}">${esc(title)}</option>`).join('');
    shell.innerHTML=`<div class="v2124-admin-mobile"><label for="v2124AdminMobileMenu">Admin section</label><select id="v2124AdminMobileMenu">${options}</select></div>
      <div class="v2124-admin-layout"><nav class="v2124-admin-sidebar" aria-label="Q Admin sections">${menu}</nav>
      <main class="v2124-admin-main"><div class="v2124-admin-heading"><h3 id="v2124ActiveHeading">Overview</h3>
        <p>Choose a category, then expand only the controls you need.</p></div>
        ${GROUPS.map(([key,title,desc])=>`<section class="v2124-admin-panel" data-v2124-admin-panel="${key}" aria-label="${esc(title)}" hidden>
          <p class="v2124-admin-panel-desc">${esc(desc)}</p></section>`).join('')}
      </main></div>`;
    hero.after(shell);
    shell.querySelectorAll('[data-v2124-admin-nav]').forEach(b=>b.addEventListener('click',()=>selectGroup(b.dataset.v2124AdminNav)));
    byId('v2124AdminMobileMenu').addEventListener('change',e=>selectGroup(e.target.value));
    // Shortcuts are within Overview and survive future admin data refreshes.
    const shortcuts=document.createElement('div');shortcuts.className='v2124-admin-shortcuts';
    shortcuts.innerHTML='<button class="ghost" type="button" data-v2124-jump="users">User management / Reset password</button><button class="ghost" type="button" data-v2124-jump="payments">Pending USDT</button><button class="ghost" type="button" data-v2124-jump="predict">Q Predict</button><button class="ghost" type="button" data-v2124-jump="analytics">Activity & audits</button>';
    panel('overview').append(shortcuts);
    shortcuts.querySelectorAll('[data-v2124-jump]').forEach(b=>b.addEventListener('click',()=>{
      const g=b.dataset.v2124Jump;selectGroup(g);
      if(g==='users')openRecovery();
    }));
    return shell;
  }
  function panel(group){return document.querySelector(`[data-v2124-admin-panel="${group}"]`)}
  // Identify by stable element IDs, not the order of cards (which changes with feature modules).
  const CLASSIFY=[
    ['v306Admin','predict'],['v21314CricketAdmin','predict'],['v306Calling','calling'],['v301Communication','communication'],['v301SupportAdmin','users'],['v213CreatorAdminCard','creators'],['q28AdminOverview','overview'],['v29OperationsStats','overview'],
    ['q28AdminUsers','users'],
    ['q21074AdminEconomyCard','economy'],['q28PackageMasterRules','economy'],
    ['q28AdminTreasury','economy'],['q28AdminLedger','economy'],
    ['q28AdminPayments','payments'],['q21074WithdrawAdminCard','payments'],
    ['q28WalletMatrix','payments'],
    ['q28AdminMarketOrders','market'],
    ['v29PredictAdminStats','predict'],
    ['v29MonetisationStats','analytics'],['v29OperationsStats__duplicate','analytics'],
    ['v29QSimulation','analytics'],['q21072UsageCard','analytics'],
    ['q28AdminAudit','analytics'],
    ['q21074FeaturePricingCard','settings'],['q28AdminTeamCard','settings'],
    ['q28AdminPrice','settings'],['q28RefStarter','economy']
  ];
  function kind(node){
    for(const [id,g] of CLASSIFY)if(node.id===id || node.querySelector?.(`#${id}`))return g;
    return 'settings'; // no legacy card silently disappears
  }
  function titleOf(node){
    if(node.id==='q28AdminOverview')return 'Q overview';
    return node.querySelector?.('h3,h2')?.textContent?.trim() || node.querySelector?.('.eyebrow')?.textContent?.trim() || 'More controls';
  }
  function wrap(node){
    if(!node || node.id==='v2124AdminShell' || node.classList.contains('q28-hero') || node.id==='rbacDelegated')return;
    const g=kind(node),dest=panel(g);if(!dest)return;
    if(['v306Admin','v21314CricketAdmin','v306Calling','v301Communication','v301SupportAdmin'].includes(node.id)){dest.append(node);return;}
    if(node.id==='q28AdminOverview'){
      // Overview indicators are always visible.
      dest.insertBefore(node,dest.children[1]||null);
      return;
    }
    const detail=document.createElement('details');detail.className='v2124-admin-disclosure';
    detail.dataset.v2124Title=titleOf(node).toLowerCase();
    const summary=document.createElement('summary');summary.textContent=titleOf(node);
    const inside=document.createElement('div');inside.className='v2124-admin-disclosure-body';
    detail.append(summary,inside);inside.append(node);
    dest.append(detail);
    if(g==='users' && node.querySelector('#q28AdminUsers'))detail.open=true;
    if(g==='payments' && node.querySelector('#q28AdminPayments'))detail.open=true;
    addRecordFilter(detail,node);
  }
  function addRecordFilter(detail,node){
    const list=node.querySelector('#q28AdminLedger, #q28AdminAudit');if(!list)return;
    const label=document.createElement('label');label.className='v2124-local-filter';
    label.innerHTML='<span>Filter loaded records</span><input type="search" placeholder="Search user, action, amount or details" autocomplete="off"><small>Searches the records currently loaded. Full-history paging is a later backend enhancement.</small>';
    node.insertBefore(label,list);
    const input=label.querySelector('input');
    const apply=()=>{const text=input.value.toLowerCase().trim();list.querySelectorAll('.q28-row').forEach(r=>{r.hidden=!!text&&!r.textContent.toLowerCase().includes(text)})};
    input.addEventListener('input',apply);
    new MutationObserver(apply).observe(list,{childList:true});
  }
  function organiseCards(){
    const view=host();if(!view)return;
    // Some existing cards are grouped two per row. Separate the cards without recreating them.
    for(const item of [...view.children]){
      if(['v307Gate','v2124AdminShell','rbacDelegated'].includes(item.id)||item.classList.contains('q28-hero'))continue;
      if(item.classList.contains('grid')){
        for(const child of [...item.children])wrap(child);
        if(!item.children.length)item.remove();
      }else wrap(item);
    }
  }
  function clearPassword(){lastPassword='';const out=byId('v2124ResetResult');if(out)out.replaceChildren()}
  function showError(value){const box=byId('v2124RecoveryStatus');if(box){box.textContent=value;box.classList.add('error')}}
  function showStatus(value){const box=byId('v2124RecoveryStatus');if(box){box.textContent=value;box.classList.remove('error')}}
  function buildRecovery(){
    if(byId('v2124RecoveryCard'))return;
    const card=document.createElement('article');card.className='card glass v2124-recovery-card';card.id='v2124RecoveryCard';
    card.innerHTML=`<div class="section-head"><div><span class="eyebrow">MASTER ADMIN ONLY</span><h3>Account Recovery</h3>
      <p class="micro">Reset a verified user's password without collecting email addresses. Old passwords cannot be retrieved.</p></div></div>
      <div class="v2124-recovery-find"><label>Exact @username or numeric user ID<input id="v2124RecoveryQuery" type="text" autocomplete="off" placeholder="@username or 28"></label><button id="v2124FindUser" class="ghost" type="button">Find user</button></div>
      <p id="v2124RecoveryStatus" class="micro" role="status" aria-live="polite">Look up a user before resetting.</p>
      <form id="v2124RecoveryForm" class="v2124-recovery-form" hidden autocomplete="off">
        <div id="v2124RecoveryIdentity" class="v2124-recovery-identity"></div>
        <label>Verification reason (required)<textarea id="v2124ResetReason" minlength="8" maxlength="300" required rows="2" placeholder="Describe how you verified the account owner. Do not write passwords here."></textarea></label>
        <label>Confirm target @username<input id="v2124ConfirmTarget" required autocomplete="off" placeholder="Enter exact @username"></label>
        <label>Your Master Admin password<input id="v2124MasterPassword" type="password" minlength="6" required autocomplete="new-password" placeholder="Your password (not the user's)"></label>
        <button id="v2124ResetSubmit" type="submit" class="primary">Reset password and revoke sessions</button>
      </form><div id="v2124ResetResult" role="status" aria-live="polite"></div>`;
    // Recovery is first in Users & Support, the existing user directory stays below.
    const dest=panel('users');dest.insertBefore(card,dest.children[1]||null);
    byId('v2124FindUser').addEventListener('click',findUser);
    byId('v2124RecoveryQuery').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();findUser()}});
    byId('v2124RecoveryForm').addEventListener('submit',submitReset);
  }
  async function findUser(){
    const q=byId('v2124RecoveryQuery')?.value.trim()||'';
    resetUser=null;clearPassword();
    const form=byId('v2124RecoveryForm');if(form)form.hidden=true;
    if(!q){showError('Enter the exact username or user ID.');return}
    const btn=byId('v2124FindUser');btn.disabled=true;showStatus('Looking up account…');
    try{
      let d;
      if(/^\d+$/.test(q)){
        d=await api(`/v28/admin/users/${Number(q)}`);
      }else{
        const username=q.replace(/^@/,'').toLowerCase();
        const users=await api(`/v28/admin/users?q=${encodeURIComponent(username)}`);
        const match=(users||[]).find(x=>String(x.user?.username||'').toLowerCase()===username);
        if(!match)throw new Error('No exact matching username. Check spelling or search by user ID.');
        d=await api(`/v28/admin/users/${match.user.id}`);
      }
      if(!d?.user?.id)throw new Error('Unable to load the selected user.');
      resetUser=d.user;
      byId('v2124RecoveryIdentity').textContent=`Selected: User #${d.user.id} · ${d.user.display_name} · @${d.user.username}`;
      byId('v2124ConfirmTarget').value='';byId('v2124MasterPassword').value='';byId('v2124ResetReason').value='';
      form.hidden=false;showStatus('Confirm identity independently before issuing a replacement password.');
    }catch(e){showError(e.message||'Unable to find user.');}
    finally{btn.disabled=false}
  }
  async function submitReset(event){
    event.preventDefault();clearPassword();
    if(!isMaster){showError('Master Admin access is required.');return}
    if(!resetUser){showError('Find a user first.');return}
    const reason=byId('v2124ResetReason').value.trim();
    const confirmName=byId('v2124ConfirmTarget').value.trim().replace(/^@/,'').toLowerCase();
    const masterPass=byId('v2124MasterPassword').value;
    if(reason.length<8){showError('Verification reason must contain at least 8 characters.');return}
    if(confirmName!==resetUser.username.toLowerCase()){
      showError('Confirmation username does not match selected user.');return;
    }
    if(masterPass.length<6){showError('Enter your Master Admin password.');return}
    if(!window.confirm(`Reset User #${resetUser.id} @${resetUser.username}? All existing sessions will be revoked.`))return;
    const btn=byId('v2124ResetSubmit');btn.disabled=true;btn.textContent='Resetting…';
    byId('v2124MasterPassword').value='';
    try{
      const result=await api(`/v2123/admin/users/${resetUser.id}/reset-password`,{
        method:'POST',body:JSON.stringify({admin_password:masterPass,reason,confirm_username:resetUser.username})
      });
      if(!result?.temporary_password)throw new Error('Server did not return the one-time replacement password.');
      lastPassword=result.temporary_password;
      const out=byId('v2124ResetResult');
      const p=document.createElement('p');p.textContent='Password reset successful. Share the temporary password only with the verified account owner.';
      const code=document.createElement('code');code.className='v2124-once-password';code.textContent=lastPassword;
      const copy=document.createElement('button');copy.type='button';copy.className='ghost';copy.textContent='Copy temporary password';
      copy.onclick=async()=>{
        try{await navigator.clipboard.writeText(lastPassword);showStatus('Temporary password copied. Clear your clipboard after sharing.');}
        catch{showError('Clipboard unavailable. Select and copy the password manually.')}
      };
      out.append(p,code,copy);showStatus('Password reset recorded. Previous account sessions were revoked.');
      byId('v2124RecoveryForm').hidden=true;
    }catch(e){
      const msg=String(e.message||'Unable to reset password');
      showError(/Not Found|HTTP 404/i.test(msg)?'Password reset endpoint missing. Deploy backend V2.12.3 or later to Render.':msg);
    }finally{btn.disabled=false;btn.textContent='Reset password and revoke sessions'}
  }
  function openRecovery(query){
    if(!isMaster){if(typeof toast==='function')toast('Master Admin access required',true);return}
    selectGroup('users');
    const input=byId('v2124RecoveryQuery');
    if(query&&input){input.value=String(query).replace(/^@/,'');findUser()}
    else if(input)input.focus();
  }
  window.lemmiqAdminOpenRecovery=openRecovery;
  window.v307MountLayout=function(access){
    isMaster=access?.role==='MASTER_ADMIN';if(!isMaster)throw new Error('Master Admin required');
    const shell=makeShell();if(!shell)throw new Error('Admin layout unavailable');
    shell.hidden=false;shell.style.display='';host()?.querySelector('#rbacDelegated')?.remove();for(const n of host().querySelectorAll('[data-rbac-hidden="1"]')){n.style.display='';delete n.dataset.rbacHidden}organiseCards();buildRecovery();
    for(const id of ['q28AdminUsers','q28WalletMatrix','q28AdminPayments','q28PackageMasterRules','q28AdminTreasury','q28AdminLedger','q28RefStarter','q28AdminAudit','q28AdminMarketOrders','q28AdminPrice']){const card=byId(id)?.closest('article');if(card)card.inert=true;}
    selectGroup(current);
    const hero=host()?.querySelector('.q28-hero');if(hero){hero.querySelector('h2').textContent='Q Admin';hero.querySelector('.eyebrow').textContent='LEMMIQ · MANAGEMENT CONSOLE';}
    byId('q28AdminRole').textContent='MASTER ADMIN';
  };
  window.v307Organise=organiseCards;
  window.v307CurrentGroup=()=>current;
  window.v307SelectGroup=selectGroup;
})();
