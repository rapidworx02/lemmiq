/* LEMMIQ V2.13.17: bounded, on-demand engagement; no polling, no client-side scheduler. */
(()=>{
  'use strict';
  const $=id=>document.getElementById(id);
  async function api317(path,options={}){
    const token=localStorage.getItem('lemmiq_token')||'';
    const headers={...(options.headers||{}),...(token?{'Authorization':`Bearer ${token}`}:{})};
    if(options.body)headers['Content-Type']='application/json';
    const r=await fetch(path,{...options,headers});
    if(!r.ok)throw new Error(`Request failed (HTTP ${r.status})`);
    return r.json();
  }
  const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function activeTabs(target){
    document.querySelectorAll('[data-home317-target]').forEach(b=>b.classList.toggle('active',b.dataset.home317Target===target));
  }
  function openTab(target){
    if(target==='q-creators'&&typeof window.openCreatorProfessionalInbox==='function')window.openCreatorProfessionalInbox('inbox');
    else if(typeof window.setView==='function')window.setView(target);
    activeTabs(target);
  }
  async function catchup(){
    const result=$('q317Summary');if(result)result.textContent='Checking your conversations…';
    try{
      const data=await api317('/v21317/q/catch-up');
      if(result)result.textContent=data.body||'You are all caught up.';
    }catch{if(result)result.textContent='Catch-up is temporarily unavailable.'}
  }
  async function preferences(){
    try{
      const pref=await api317('/v21317/q/preferences');
      const tz=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';
      const options=['OFF','LOW','DAILY'].map(v=>`<option value="${v}" ${pref.frequency===v?'selected':''}>${v==='OFF'?'Off':v==='LOW'?'Low · every 3 days':'Daily · when useful'}</option>`).join('');
      if(typeof window.openModal!=='function')return;
      const hourOptions=(selected)=>Array.from({length:24},(_,hour)=>`<option value="${hour}" ${selected===hour?'selected':''}>${String(hour).padStart(2,'0')}:00</option>`).join('');
      window.openModal(`<h3>Q Assistant preferences</h3><p>Helpful in-app catch-ups. No unsolicited push notifications.</p><label>Proactive digests <select id="q317Freq">${options}</select></label><label>Quiet hours start <select id="q317QuietStart">${hourOptions(pref.quiet_start)}</select></label><label>Quiet hours end <select id="q317QuietEnd">${hourOptions(pref.quiet_end)}</select></label><p class="micro">Times are in ${safe(tz)}. No scheduled promotional pushes.</p><div class="suggestion-actions"><button class="ghost" id="q317Cancel">Cancel</button><button class="primary" id="q317Save">Save</button></div>`);
      $('q317Cancel').onclick=()=>window.closeModal?.();
      $('q317Save').onclick=async()=>{
        const freq=$('q317Freq').value;
        try{await api317('/v21317/q/preferences',{method:'PUT',body:JSON.stringify({enabled:freq!=='OFF',frequency:freq,quiet_start:Number($('q317QuietStart').value),quiet_end:Number($('q317QuietEnd').value),timezone_name:tz})});window.closeModal?.()}
        catch(e){$('q317Save').textContent='Could not save: '+e.message}
      };
    }catch{const result=$('q317Summary');if(result)result.textContent='Preferences are temporarily unavailable.'}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('[data-home317-target]').forEach(btn=>btn.addEventListener('click',()=>openTab(btn.dataset.home317Target)));
    $('q317Catchup')?.addEventListener('click',catchup);
    $('q317Prefs')?.addEventListener('click',preferences);
    $('q317Unread')?.addEventListener('click',()=>{
      openTab('chats');
      const filter=document.querySelector('[data-chat-filter="UNREAD"]');
      if(filter)filter.click();
    });
    document.addEventListener('click',e=>{
      const btn=e.target.closest('[data-home317-target]');if(btn)activeTabs(btn.dataset.home317Target);
    });
  });
})();
// V300_INSTALLED
