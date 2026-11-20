/* LEMMIQ 2.13.17 Calls: compact recents, search, missed filter, call info, one-tap redial. */
(()=>{
  'use strict';
  const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let calls=[],filter='ALL',search='';
  const $=id=>document.getElementById(id);
  const missed=c=>['MISSED','RINGING'].includes(String(c.status||'').toUpperCase());
  const video=c=>String(c.call_type||'VOICE').toUpperCase()==='VIDEO';
  const stamp=c=>{const d=new Date(c.started_at);return Number.isNaN(+d)?'':d.toLocaleString()};
  function redraw(){
    const list=$('callsList');if(!list)return;
    const filtered=calls.filter(c=>(filter!=='MISSED'||missed(c))&&
      (!search||[c.other_user?.display_name,c.other_user?.username].join(' ').toLowerCase().includes(search)));
    list.innerHTML=filtered.map(c=>{
      const person=c.other_user||{display_name:'LEMMIQ user'},direction=c.caller_id===state.user?.id?'↗':'↙';
      return `<div class="calls317-row"><button class="calls317-person" data-call317-info="${safe(c.id)}">${avatarHtml(person)}<span class="body"><strong class="${missed(c)?'missed':''}">${safe(person.display_name)}</strong><small>${direction} ${video(c)?'Video':'Voice'} · ${missed(c)?'Missed':safe(c.status||'Completed')} · ${safe(stamp(c))}${c.duration_seconds?' · '+formatDuration(c.duration_seconds):''}</small></span></button><button class="calls317-redial" data-call317-retry="${safe(c.id)}" title="Call back">${video(c)?'▣':'☎'}</button></div>`;
    }).join('')||'<p class="micro">No matching calls.</p>';
    list.querySelectorAll('[data-call317-info]').forEach(b=>b.onclick=()=>showInfo(calls.find(c=>String(c.id)===b.dataset.call317Info)));
    list.querySelectorAll('[data-call317-retry]').forEach(b=>b.onclick=()=>{
      const c=calls.find(c=>String(c.id)===b.dataset.call317Retry);if(c)beginCall(c.chat_id,c.other_user,video(c)?'VIDEO':'VOICE');
    });
  }
  function showInfo(call){
    if(!call)return;
    const peer=call.other_user||{display_name:'LEMMIQ user'},related=calls.filter(c=>c.other_user?.id===peer.id).slice(0,20);
    openModal(`<div style="text-align:center">${avatarHtml(peer)}<h2>${safe(peer.display_name)}</h2><p class="micro">@${safe(peer.username||'')}</p></div><div class="suggestion-actions"><button class="ghost" id="call317Message">Message</button><button class="ghost" id="call317Voice">☎ Voice</button><button class="ghost" id="call317Video">▣ Video</button></div><h3>Call history</h3><div style="max-height:230px;overflow:auto">${related.map(c=>`<p class="micro">${video(c)?'Video':'Voice'} · ${safe(c.status)} · ${safe(stamp(c))}${c.duration_seconds?' · '+formatDuration(c.duration_seconds):''}</p>`).join('')}</div><div class="suggestion-actions"><button class="ghost" id="call317Close">Close</button></div>`);
    $('call317Close').onclick=closeModal;
    $('call317Message').onclick=()=>{closeModal();setView('chats');openChat(call.chat_id)};
    $('call317Voice').onclick=()=>{closeModal();beginCall(call.chat_id,peer,'VOICE')};
    $('call317Video').onclick=()=>{closeModal();beginCall(call.chat_id,peer,'VIDEO')};
  }
  async function chooseContact(){
    if(!state.chats?.length)await loadChats().catch(()=>{});
    const chats=(state.chats||[]).slice(0,80);
    openModal(`<h3>New LEMMIQ call</h3><p class="micro">Choose a conversation. Calls are available between LEMMIQ users.</p><div style="max-height:360px;overflow:auto">${chats.map(c=>`<div class="calls317-row"><span class="body" style="flex:1">${safe(c.other_user?.display_name||'LEMMIQ user')}</span><button class="ghost" data-call317-pick="${c.id}" data-type="VOICE">☎</button><button class="ghost" data-call317-pick="${c.id}" data-type="VIDEO">▣</button></div>`).join('')||'<p>No conversations yet. Start a chat first.</p>'}</div><button id="call317Close" class="ghost">Close</button>`);
    $('call317Close').onclick=closeModal;
    document.querySelectorAll('[data-call317-pick]').forEach(b=>b.onclick=()=>{
      const chat=chats.find(c=>c.id===Number(b.dataset.call317Pick));if(!chat)return;
      closeModal();beginCall(chat.id,chat.other_user,b.dataset.type);
    });
  }
  window.loadCalls=async function(){
    calls=await api('/v24/calls');state.callHistory=calls;
    redraw();
  };
  document.addEventListener('DOMContentLoaded',()=>{
    $('calls317All')?.addEventListener('click',()=>{filter='ALL';$('calls317All').classList.add('active');$('calls317Missed').classList.remove('active');redraw()});
    $('calls317Missed')?.addEventListener('click',()=>{filter='MISSED';$('calls317Missed').classList.add('active');$('calls317All').classList.remove('active');redraw()});
    $('calls317Search')?.addEventListener('input',e=>{search=(e.target.value||'').toLowerCase();redraw()});
    $('calls317New')?.addEventListener('click',chooseContact);
    // Replace the previous release's onclick handler rather than firing two loads.
    if($('refreshCallsBtn'))$('refreshCallsBtn').onclick=window.loadCalls;
  });
})();
