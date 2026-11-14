/* LEMMIQ V2.12.2 — Edit with Q on existing direct/group chat images. */
(()=>{
  'use strict';
  const $=id=>document.getElementById(id);
  const apiHeaders=()=>typeof authHeaders==='function'?authHeaders():{};
  let ui=null;
  function release(){
    if(ui){for(const url of ui.urls)URL.revokeObjectURL(url);ui.urls=[];ui=null;}
  }
  function info(v){const e=$('v2122-note');if(e)e.textContent=v;}
  async function preview(path, slot, label){
    const r=await fetch(path,{headers:apiHeaders()});
    if(!r.ok)throw Error('Photo preview unavailable ('+r.status+')');
    const url=URL.createObjectURL(await r.blob());
    ui.urls.push(url);
    const host=$(slot),image=document.createElement('img');
    image.src=url;image.alt=label;image.className='v2122-preview';
    host.replaceChildren(image);
  }
  async function start(kind,mid){
    if(!window.lemmiqState?.token){toast('Sign in to edit with Q',true);return}
    release();
    const dest=kind==='direct'
      ? {chat_id:window.lemmiqState?.activeChat?.id}
      : {group_id:window.lemmiqState?.activeGroup?.id};
    if(!Object.values(dest)[0])return toast('Open the chat first',true);
    ui={kind,mid,dest,urls:[],draft:null,ready:false,working:false};
    openModal(`<div class="v2122-studio">
      <h3>✨ Edit with Q</h3>
      <p class="micro">Edit a shared photo with a prompt. The original chat photo stays unchanged.</p>
      <div class="v2122-comparison"><div><strong>Original</strong><div id="v2122-original"></div></div>
        <div><strong>Edited preview</strong><div id="v2122-result" class="v2122-empty">Your private edit will appear here</div></div></div>
      <label>Describe your edit<textarea id="v2122-prompt" maxlength="1500" rows="3" placeholder="Change the background to a beach. Keep the person and their face unchanged."></textarea></label>
      <label>Output size<select id="v2122-size"><option value="1024x1024">Square</option>
        <option value="1536x1024">Wide</option><option value="1024x1536">Tall</option></select></label>
      <p class="micro" id="v2122-price">Checking availability…</p>
      <p id="v2122-note" role="status" aria-live="polite"></p>
      <div class="v2122-actions"><button type="button" id="v2122-edit" class="primary">Generate edit</button>
       <button type="button" id="v2122-send" class="primary" disabled>Send to this chat</button>
       <button type="button" id="v2122-save" class="ghost" disabled>Save</button></div>
       <p class="micro">The posted photo will be processed by an AI provider. Get permission before editing others' photos. Each attempt may use Q after charging is enabled. Unsuccessful edits refund any charged Q. Sending always requires your tap.</p></div>`);
    $('v2122-edit').onclick=edit;
    $('v2122-send').onclick=send;
    $('v2122-save').onclick=save;
    try{
      const [cfg]=await Promise.all([
        api('/v2122/image-edits/config'),
        preview(kind==='direct'?`/media/${mid}`:`/v24/group-media/${mid}`,'v2122-original','Original chat photo')
      ]);
      if(!ui || ui.mid!==mid || ui.kind!==kind)return;
      ui.ready=Boolean(cfg.enabled&&cfg.configured);
      $('v2122-edit').disabled=!ui.ready;
      $('v2122-price').textContent=ui.ready
        ? `Edit price: ${Number(cfg.q_price||0)} Q ${cfg.charging_enabled?'(charging enabled)':'(feature charging off)'} · daily limit ${cfg.daily_limit}`
        : 'Edit with Q is disabled or not configured on Render.';
      if(!ui.ready)info('Ask the LEMMIQ administrator to enable AI image editing.');
    }catch(e){if(ui){$('v2122-edit').disabled=true;info(e.message||String(e));}}
  }
  async function edit(){
    if(!ui||!ui.ready||ui.working)return;
    const prompt=$('v2122-prompt').value.trim();
    if(prompt.length<5){info('Describe what to edit in at least 5 characters.');return}
    const current=ui;current.working=true;
    $('v2122-edit').disabled=true;$('v2122-send').disabled=true;$('v2122-save').disabled=true;
    $('v2122-result').textContent='Editing photo…';
    info('Q is editing this photo privately. The original will not change.');
    try{
      const payload={prompt,size:$('v2122-size').value,source_kind:current.kind,
        source_message_id:current.mid,request_id:crypto.randomUUID()};
      const draft=await api('/v2122/image-edits/edit',{method:'POST',body:JSON.stringify(payload)});
      if(ui!==current)return;
      current.draft=draft;
      await preview(`/v212/images/${draft.id}/file`,'v2122-result','Edited photo');
      $('v2122-send').disabled=false;$('v2122-save').disabled=false;
      info('Your edited image is ready. Review it and tap Send if you like it.');
    }catch(e){if(ui===current){info(e.message||String(e));$('v2122-result').textContent='No edited image available.';}}
    finally{if(ui===current){current.working=false;$('v2122-edit').disabled=false;}}
  }
  async function send(){
    if(!ui?.draft||ui.working)return;
    const current=ui;current.working=true;$('v2122-send').disabled=true;
    try{
      await api(`/v212/images/${current.draft.id}/send`,{method:'POST',body:JSON.stringify(current.dest)});
      if(typeof closeModal==='function')closeModal();release();toast('Edited photo sent');
      if(current.dest.chat_id)await openChat(current.dest.chat_id,false);
      else await openGroup(current.dest.group_id);
    }catch(e){if(ui===current){info(e.message||String(e));$('v2122-send').disabled=false;}}
    finally{if(ui===current)current.working=false}
  }
  async function save(){
    if(!ui?.draft)return;
    try{
      const r=await fetch(`/v212/images/${ui.draft.id}/file`,{headers:apiHeaders()});
      if(!r.ok)throw Error('Download failed');
      const u=URL.createObjectURL(await r.blob());
      const a=document.createElement('a');a.href=u;a.download=`LEMMIQ-Edit-${ui.draft.id}.png`;a.click();
      setTimeout(()=>URL.revokeObjectURL(u),1500);
    }catch(e){info(e.message||String(e))}
  }
  // Messages are rendered by stable app.js; attach unobtrusive edit buttons after render.
  function decorate(hostId,kind){
    const host=$(hostId),state=window.lemmiqState;
    if(!host||!state)return;
    const rows=kind==='direct'?state.messages:state.groupMessages;
    if(!Array.isArray(rows))return;
    const photos=rows.filter(m=>m.attachment?.media_id && (
      String(m.attachment?.kind||'').toUpperCase()==='PHOTO'||
      /^image\/(png|jpeg|webp)$/i.test(String(m.attachment?.mime_type||''))));
    for(const m of photos){
      if(kind==='direct'&&m.deleted_for_everyone)continue;
      const msg=kind==='direct'?host.querySelector(`.msg[data-mid="${m.id}"]`):null;
      const target=msg || Array.from(host.querySelectorAll('.msg')).find(x=>{
        const btn=x.querySelector('.chat-photo-preview,.lemmiq-media-preview,.v211-photo-wrap');
        return btn && (btn.dataset.mediaEndpoint||"").endsWith("/"+m.id);
      });
      if(!target||target.querySelector(`.v2122-edit-trigger[data-source="${m.id}"]`))continue;
      const btn=document.createElement('button');btn.type='button';btn.className='mini v2122-edit-trigger';
      btn.textContent='✨ Edit with Q';btn.dataset.source=String(m.id);
      btn.onclick=e=>{e.stopPropagation();start(kind,m.id)};
      const body=target.querySelector('.chat-photo-preview,.lemmiq-media-preview,.v211-photo-wrap');
      if(body)body.insertAdjacentElement('afterend',btn);else target.appendChild(btn);
    }
  }
  function setup(){
    for(const [id,kind] of [['messageList','direct'],['groupMessageList','group']]){
      const host=$(id);if(!host)continue;
      let scheduled=false;
      const update=()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{
        scheduled=false;decorate(id,kind);
      })};
      new MutationObserver(update).observe(host,{childList:true,subtree:false});
      update();
    }
    document.addEventListener('close',e=>{if(e.target?.id==='modal')release()},true);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
})();
