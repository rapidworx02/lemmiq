/* LEMMIQ V2.12 — Q Create Image · direct, group and Q assistant · explicit Send */
(()=>{
  'use strict';
  let previewUrl=null, draft=null, origin={kind:'q',id:null};
  const el=id=>document.getElementById(id);
  const stopPreview=()=>{if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null}};
  const msg=message=>{const x=el('v212-info');if(x)x.textContent=message};
  async function attachPreview(id){
    stopPreview();
    const r=await fetch(`/v212/images/${id}/file`,{headers:authHeaders()});
    if(!r.ok)throw new Error(`Preview unavailable (${r.status})`);
    const blob=await r.blob();
    previewUrl=URL.createObjectURL(blob);
    const img=document.createElement('img');img.src=previewUrl;img.alt='Generated image preview';img.className='v212-preview';
    const host=el('v212-output');host.replaceChildren(img);host.hidden=false;
    el('v212-actions').hidden=false;
  }
  function renderModal(){
    stopPreview();draft=null;
    openModal(`<div class="v212-generator">
      <h3>✨ Create with Q</h3>
      <p class="micro">Describe an image. Review it privately, then choose whether to send it.</p>
      <label>Image prompt<textarea id="v212-prompt" rows="4" maxlength="1500" placeholder="e.g. A premium birthday invitation with gold balloons and a midnight blue background"></textarea></label>
      <label>Format<select id="v212-size"><option value="1024x1024">Square</option><option value="1536x1024">Landscape</option><option value="1024x1536">Portrait</option></select></label>
      <p class="micro" id="v212-price">Checking image availability…</p>
      <div id="v212-info" role="status" aria-live="polite"></div>
      <div id="v212-output" hidden></div>
      <div id="v212-actions" class="v212-actions" hidden>
        <button id="v212-send" class="primary">Send to chat</button>
        <button id="v212-save" class="ghost">Save image</button>
        <button id="v212-regenerate" class="ghost">Regenerate</button>
      </div>
      <button id="v212-generate" class="primary full">Generate image</button>
      <p class="micro">Generated images are AI-created. No image is sent automatically. If generation fails, an applicable Q charge is refunded.</p>
    </div>`);
    el('v212-generate').addEventListener('click',generate);
    el('v212-regenerate').addEventListener('click',generate);
    el('v212-send').addEventListener('click',sendImage);
    el('v212-save').addEventListener('click',saveImage);
    if(origin.kind==='q') el('v212-send').textContent='Select chat and send';
    api('/v212/images/config').then(cfg=>{
      const charge=Number(cfg.q_price||0);
      el('v212-price').textContent=(!cfg.enabled||!cfg.configured)
        ?'Image generation is not enabled on this server.'
        :`Q image price: ${charge} Q ${cfg.charging_enabled?'(when charging is enabled)':'(feature charging is off)'} · Daily limit ${cfg.max_attempts_per_day}`;
      if(!cfg.enabled||!cfg.configured){el('v212-generate').disabled=true}
    }).catch(()=>{msg('Please sign in and try again.')});
  }
  async function generate(){
    const prompt=el('v212-prompt')?.value.trim();
    if(!prompt||prompt.length<5){msg('Write at least five characters describing your image.');return}
    const button=el('v212-generate');button.disabled=true;el('v212-regenerate').disabled=true;
    el('v212-actions').hidden=true;msg('Q is creating your image…');
    try{
      const payload={prompt,size:el('v212-size').value,request_id:crypto.randomUUID()};
      const r=await api('/v212/images/generate',{method:'POST',body:JSON.stringify(payload)});
      draft=r;await attachPreview(r.id);
      msg('Image is ready. Preview it before sending.');
    }catch(e){msg(e.message||String(e));}
    finally {if(el('v212-generate'))el('v212-generate').disabled=false;
      if(el('v212-regenerate'))el('v212-regenerate').disabled=false;}
  }
  async function destination(){
    if(origin.kind==='direct')return {chat_id:origin.id};
    if(origin.kind==='group')return {group_id:origin.id};
    // Q assistant makes generation privately first, and asks the user where to send.
    const [chats,groups]=await Promise.all([api('/chats'),api('/v24/groups')]);
    const options=[...chats.map(c=>({id:c.id,kind:'chat_id',label:c.other_user?.display_name||`Chat ${c.id}`})),
                   ...groups.map(g=>({id:g.id,kind:'group_id',label:g.name||`Group ${g.id}`}))];
    if(!options.length)throw new Error('Start a chat or join a group before sharing');
    const select=el('v212-destination');
    if(select){const chosen=options.find(o=>`${o.kind}:${o.id}`===select.value);return chosen?{[chosen.kind]:chosen.id}:null}
    const area=document.createElement('div');area.className='v212-destinations';
    area.innerHTML='<label>Choose the chat to send to<select id="v212-destination"></select></label>';
    const sel=area.querySelector('select');options.forEach(o=>{
      const opt=document.createElement('option');opt.value=`${o.kind}:${o.id}`;opt.textContent=o.label;sel.appendChild(opt);
    });
    el('v212-actions').before(area);
    el('v212-send').textContent='Confirm send';
    msg('Select the recipient, then tap Confirm send.');
    return null;
  }
  async function sendImage(){
    if(!draft)return;
    const dest=await destination();if(!dest)return;
    const button=el('v212-send');button.disabled=true;
    try{
      const sent=await api(`/v212/images/${draft.id}/send`,{method:'POST',body:JSON.stringify(dest)});
      msg('Image sent successfully.');
      if(dest.chat_id){await openChat(dest.chat_id,false)}
      else if(dest.group_id){await openGroup(dest.group_id)}
      if(typeof closeModal==='function')closeModal();
      stopPreview();
      toast('Q image sent');
    }catch(e){msg(e.message||String(e));}
    finally{if(el('v212-send'))el('v212-send').disabled=false}
  }
  async function saveImage(){
    if(!draft)return;
    try{
      const res=await fetch(`/v212/images/${draft.id}/file`,{headers:authHeaders()});
      if(!res.ok)throw new Error('Download unavailable');
      const blob=await res.blob(),url=URL.createObjectURL(blob);
      const a=document.createElement('a');a.href=url;a.download=`LEMMIQ-Q-Image-${draft.id}.png`;
      a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(e){msg(e.message||String(e))}
  }
  function button(host,label,kind){
    if(!host||host.querySelector(`.v212-open[data-v212-kind="${kind}"]`))return;
    const b=document.createElement('button');b.type='button';b.className='ghost v212-open';
    b.dataset.v212Kind=kind;b.textContent=label;
    b.addEventListener('click',()=>{
      origin={kind,id:kind==='direct'?window.lemmiqState?.activeChat?.id : kind==='group'?window.lemmiqState?.activeGroup?.id:null};
      if(kind!=='q'&&!origin.id){toast('Open a chat first',true);return}
      renderModal();
    });
    host.appendChild(b);
  }
  function setup(){
    button(el('askAgentBtn')?.parentElement,'🎨 Create Image','q');
    button(el('sendBtn')?.parentElement,'🎨','direct');
    button(el('groupSendBtn')?.parentElement,'🎨','group');
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
  // Existing dialog can be closed while a preview is open.
  document.addEventListener('close',e=>{if(e.target?.id==='modal')stopPreview()},true);
})();
