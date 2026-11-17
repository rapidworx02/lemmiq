/* V21356_STUDIO_DELETE */
/* LEMMIQ V2.13.4.1 — professional gallery picker and private media management.
   Only professional threads may receive an offer. Never use personal /chats endpoints.
   Prices and media access are authorised by the backend. */
(()=>{
  'use strict';
  const ROOT='/v2131/exclusives';
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const amount=s=>Number(s||0).toLocaleString(undefined,{maximumFractionDigits:2});
  const key=()=>crypto.randomUUID();
  const req=(path,opts)=>api(ROOT+path,opts||{});
  const post=(path,body)=>req(path,{method:'POST',body:JSON.stringify(body)});
  const s={thread:null,done:null,tab:'gallery',gallery:[],library:[],selected:null,blobs:new Set(),busy:false};
  const el=id=>document.getElementById(id);
  const msg=(message,error=false)=>{const node=el('v21341Feedback');if(node){node.textContent=message;node.classList.toggle('error',error)}else if(typeof toast==='function')toast(message,error)};
  function clearBlobs(){for(const url of s.blobs)URL.revokeObjectURL(url);s.blobs.clear()}
  function dialog(){
    let box=el('v21341GalleryDialog');
    if(!box){
      box=document.createElement('dialog');box.id='v21341GalleryDialog';box.className='v21341-dialog';
      box.innerHTML='<div id="v21341Root"></div>';
      document.body.append(box);
      box.addEventListener('close',clearBlobs);
      box.addEventListener('click',async e=>{
        const btn=e.target.closest('[data-gallery-action]');if(!btn||!box.contains(btn))return;
        const action=btn.dataset.galleryAction;
        try{
          if(action==='close')return box.close();
          if(action==='reload')return await load();
          if(action==='choose'){s.selected=Number(btn.dataset.item);return render()}
          if(action==='tab'){s.tab=btn.dataset.tab;return render()}
          if(action==='send')return await send();
        }catch(ex){msg(ex.message,true)}
      });
      box.addEventListener('submit',async e=>{
        const f=e.target;if(!['v21341Upload','v21341Publish'].includes(f.id))return;
        e.preventDefault();try{
          if(f.id==='v21341Upload')await upload(f);else await publish(f)
        }catch(ex){msg(ex.message,true)}
      });
      box.addEventListener('change',e=>{if(e.target.id==='v21341Visibility'){
        const p=el('v21341PublishPrice');if(p){p.disabled=e.target.value!=='PPV';p.value=e.target.value==='PPV'?'50':'0'}
      }});
    }
    return box;
  }
  function galleryCard(item){
    const selected=item.id===s.selected;
    const pending=item.review!=='APPROVED';
    return `<button type="button" class="v21341-item ${selected?'selected':''}" data-gallery-action="choose" data-item="${item.id}" ${pending?'disabled':''}>
      <span class="v21341-thumb" data-v21341-thumb="${item.id}" aria-hidden="true">${item.kind==='VIDEO'?'▶':item.kind==='ALBUM'?'▣':'▧'}</span>
      <span class="v21341-item-detail"><strong>${escape(item.title)}</strong><small>${escape(item.kind)} · ${item.media_count} file(s)</small><small>${item.visibility==='PPV'?amount(item.price_q)+' Q gallery price':'Subscriber included'}</small><small class="${pending?'v21341-pending':''}">${escape(item.review)}</small></span><span>${selected?'✓':''}</span>
    </button>`;
  }
  function assetCard(a){return `<label class="v21341-asset"><input type="checkbox" name="asset_ids" value="${a.id}" data-kind="${escape(a.kind)}"><span>▧</span><strong>${escape(a.title)}</strong><small>${escape(a.kind)}</small></label>`}
  function render(){
    const root=el('v21341Root');if(!root)return;
    const approved=s.gallery.filter(x=>x.review==='APPROVED');
    const chosen=approved.find(x=>x.id===s.selected);
    const approvedAssets=s.library.filter(x=>x.review==='APPROVED');
    root.innerHTML=`<header class="v21341-header"><div><span class="eyebrow">✦ PROFESSIONAL CREATOR IDENTITY</span><h2>${s.thread?'Choose Exclusive Media':'My Creator Gallery'}</h2><p>Private creator media is reviewed before publication. No personal chat media is shared.</p></div><button class="ghost" data-gallery-action="close" aria-label="Close gallery">✕</button></header>
      <nav class="v21341-tabs" aria-label="Creator gallery management"><button class="${s.tab==='gallery'?'active':''}" data-gallery-action="tab" data-tab="gallery">My gallery (${approved.length})</button><button class="${s.tab==='upload'?'active':''}" data-gallery-action="tab" data-tab="upload">Upload new</button><button class="${s.tab==='publish'?'active':''}" data-gallery-action="tab" data-tab="publish">Create item</button></nav>
      <p id="v21341Feedback" role="status" class="v21341-feedback">${s.busy?'Processing…':'Only approved gallery items can be sent as paid offers.'}</p>
      ${s.tab==='gallery'?`<div class="v21341-grid">${s.gallery.map(galleryCard).join('')||'<p>No gallery items yet. Upload media, await approval, then create an exclusive item.</p>'}</div>
        <div class="v21341-actions">${s.thread?`<label>Private offer price (Q)<input type="number" id="v21341OfferPrice" min="0.01" max="100000" step="0.01" value="${chosen?chosen.price_q>0?chosen.price_q:25:25}"></label><button class="primary" data-gallery-action="send" ${chosen?'':'disabled'}>🔒 Send locked PPV to this fan</button>`:''}<button class="ghost" data-gallery-action="reload">↻ Refresh gallery</button></div>`:
      s.tab==='upload'?`<form id="v21341Upload" class="v21341-form"><h3>Upload from phone gallery or files</h3><label>Media title<input name="title" minlength="3" maxlength="140" required placeholder="My exclusive photo"></label><label>Content category<select name="level"><option value="MAINSTREAM">Mainstream</option><option value="GLAMOUR">Non-explicit glamour</option></select></label><label>Choose photo / video from device<input name="file" type="file" accept="image/*,video/*" required></label><p class="micro">Photos up to 20 MB · videos up to 100 MB. Step 1: Upload → Master Admin approves the FILE. Step 2: Create an exclusive gallery item → Admin approves the ITEM. Step 3: Select it and send a paid offer. Uploading alone does not send anything.</p><button class="primary" type="submit" ${s.busy?'disabled':''}>Upload for approval</button></form><div class="v21341-library"><h4>My media library</h4>${s.library.map(x=>`<p>${escape(x.title)} · ${escape(x.kind)} · <strong>${escape(x.review)}</strong></p>`).join('')||'<p>No uploads yet.</p>'}</div>`:
      `<form id="v21341Publish" class="v21341-form"><h3>Create an exclusive photo, video or album</h3><label>Title<input name="title" minlength="3" maxlength="140" required></label><label>Public teaser<input name="teaser" maxlength="240" placeholder="Description only, no private media"></label><label>Type<select name="kind"><option value="PHOTO">Single photo</option><option value="VIDEO">Single video</option><option value="ALBUM">Photo/video album (2–20 files)</option></select></label><label>Visibility<select name="visibility" id="v21341Visibility"><option value="PPV">Pay to unlock</option><option value="SUBSCRIBERS">Included for subscribers</option></select></label><label>Gallery price (Q)<input id="v21341PublishPrice" name="price_q" type="number" min="0" max="100000" step="0.01" value="50" required></label><fieldset><legend>Choose approved files</legend><div class="v21341-assets">${approvedAssets.map(assetCard).join('')||'<p>No approved files yet. Upload media and await review.</p>'}</div></fieldset><button type="submit" class="primary" ${approvedAssets.length?'':'disabled'}>Submit gallery item for approval</button></form>`}
      <footer>LEMMIQ can inspect uploaded creator media for moderation and compliance. Explicit material is not available in this app.</footer>`;
    if(s.tab==='gallery')hydrateThumbnails(root).catch(()=>{});
  }
  async function hydrateThumbnails(root){
    const picks=s.gallery.filter(x=>x.review==='APPROVED'&&(x.kind==='PHOTO'||x.kind==='ALBUM')).slice(0,16);
    for(const item of picks){
      const target=root.querySelector(`[data-v21341-thumb="${item.id}"]`);if(!target)continue;
      try{
        const assets=await req(`/gallery/${item.id}/assets`);if(!assets.length||assets[0].kind!=='PHOTO')continue;
        const r=await fetch(ROOT+`/gallery/${item.id}/assets/${assets[0].id}/media`,{headers:authHeaders(),cache:'no-store'});
        if(!r.ok)continue;
        const type=r.headers.get('content-type')||'';if(!type.startsWith('image/'))continue;
        const blob=await r.blob();if(blob.size>20*1024*1024)continue;
        const url=URL.createObjectURL(blob);s.blobs.add(url);
        if(!target.isConnected){URL.revokeObjectURL(url);s.blobs.delete(url);continue}
        const img=document.createElement('img');img.src=url;img.alt='';img.loading='lazy';target.replaceChildren(img);
      }catch{/* maintain static placeholder when network or permission unavailable */}
    }
  }
  async function load(){
    if(s.busy)return;s.busy=true;msg('Loading approved gallery…');
    try{
      const [gallery,library]=await Promise.all([req('/gallery/mine'),req('/library')]);
      if(!Array.isArray(gallery)||!Array.isArray(library))throw Error('Unexpected gallery response');
      s.gallery=gallery;s.library=library;
      if(!gallery.some(x=>x.id===s.selected&&x.review==='APPROVED'))s.selected=null;
      clearBlobs();render();
    }finally{s.busy=false}
  }
  async function send(){
    if(!s.thread)throw Error('Open a professional conversation to send PPV.');
    const item=s.gallery.find(x=>x.id===s.selected&&x.review==='APPROVED');
    if(!item)throw Error('Select an approved photo, video or album first.');
    const price=Number(el('v21341OfferPrice')?.value);
    if(!Number.isFinite(price)||price<=0||price>100000)throw Error('Enter a valid Q price between 0.01 and 100,000.');
    if(!confirm(`Send “${item.title}” as a locked professional offer for ${amount(price)} Q?`))return;
    if(s.busy)return;s.busy=true;msg('Sending locked offer…');
    try{
      await api(`/v2134/chats/${encodeURIComponent(s.thread)}/offers`,{method:'POST',body:JSON.stringify({item_id:item.id,price_q:price,request_key:key()})});
      dialog().close();if(typeof s.done==='function')await s.done();
      if(typeof toast==='function')toast('Locked creator offer sent');
    }finally{s.busy=false}
  }
  async function upload(form){
    if(s.busy)return;
    const f=new FormData(form),file=f.get('file');
    if(!file||!file.size)throw Error('Choose a photo or video.');
    const types=['image/jpeg','image/png','image/webp','video/mp4','video/webm'];
    // V21342_UPLOAD_ERRORS: browser/phone gallery may provide HEIC/MOV or empty MIME.
    const ext=(file.name||'').split('.').pop().toLowerCase();
    const inferred={'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp','mp4':'video/mp4','webm':'video/webm'}[ext];
    const mime=file.type||inferred;
    if(!types.includes(mime))throw Error('This phone file is '+(file.type||ext||'unknown')+'. Choose JPG/PNG/WebP for photos or MP4/WebM for videos. HEIC and MOV need conversion first.');
    if(!file.type&&inferred)f.set('file',new File([file],file.name,{type:inferred}),file.name);
    if(file.size>(file.type.startsWith('image/')?20:100)*1024*1024)throw Error('Selected file exceeds size limit.');
    s.busy=true;msg('Uploading privately…');
    try{await req('/library/upload',{method:'POST',body:f});await loadAfterAction('Upload submitted. Await Master Admin approval.','upload')}
    finally{s.busy=false}
  }
  async function publish(form){
    if(s.busy)return;
    const f=new FormData(form),kind=String(f.get('kind')),visibility=String(f.get('visibility'));
    const ids=f.getAll('asset_ids').map(Number);
    if(kind==='ALBUM'&&(ids.length<2||ids.length>20))throw Error('Albums require 2–20 approved files.');
    if(kind!=='ALBUM'&&ids.length!==1)throw Error('Choose exactly one approved file.');
    const files=s.library.filter(x=>ids.includes(x.id));
    if(files.length!==ids.length||files.some(x=>x.review!=='APPROVED'))throw Error('All selected files must be approved.');
    if((kind==='PHOTO'||kind==='VIDEO')&&files[0].kind!==kind)throw Error('Media does not match the selected type.');
    const price=visibility==='SUBSCRIBERS'?0:Number(f.get('price_q'));
    if(!Number.isFinite(price)||(visibility==='PPV'&&price<=0)||price>100000)throw Error('Enter a valid gallery price.');
    s.busy=true;msg('Creating gallery item…');
    try{await post('/gallery',{title:String(f.get('title')).trim(),teaser:String(f.get('teaser')||''),kind,visibility,price_q:price,asset_ids:ids});await loadAfterAction('Exclusive item submitted for moderation.','gallery')}
    finally{s.busy=false}
  }
  async function loadAfterAction(note,tab){
    const [gallery,library]=await Promise.all([req('/gallery/mine'),req('/library')]);
    s.gallery=gallery;s.library=library;s.tab=tab;s.selected=null;clearBlobs();render();msg(note);
  }
  async function open(thread=null,done=null){
    s.thread=thread;s.done=done;s.tab='gallery';s.selected=null;
    const box=dialog();if(!box.open)box.showModal();
    try{await load()}catch(e){msg('Cannot load gallery: '+e.message,true)}
  }
  window.LEMMIQCreatorGalleryV21341={openPicker:(id,onSent)=>open(id,onSent),openManager:()=>open()};

  // V21356_STUDIO_DELETE: markup-independent creator-owned deletion controls.
  // The upstream gallery manager may use a different library row template.
  function v21356DecorateManager(){
    const root=document.getElementById('v21341Root');
    const dlg=document.getElementById('v21341GalleryDialog');
    if(!root||!dlg||!dlg.open)return;
    const mode=s.tab;
    if(mode!=='gallery'&&mode!=='upload')return;
    const entries=mode==='gallery'?s.gallery:s.library;
    if(!Array.isArray(entries))return;
    let panel=root.querySelector('#v21356DeletePanel');
    if(!panel){panel=document.createElement('section');panel.id='v21356DeletePanel';panel.style.cssText='margin:14px 0;padding:12px;border:1px solid rgba(145,144,198,.4);border-radius:12px;display:grid;gap:8px';root.appendChild(panel)}
    const signature=mode+'|'+entries.map(x=>String(x.id)+':'+String(x.title)).join('|');
    if(panel.dataset.renderSignature===signature)return;
    panel.dataset.renderSignature=signature;
    panel.replaceChildren();
    const title=document.createElement('strong');
    title.textContent=mode==='gallery'?'Manage my gallery items':'Manage my library files';
    panel.appendChild(title);
    const hint=document.createElement('small');
    hint.textContent='Deleting stops new sales and removes this item from your studio. Existing paid access and admin audit records remain available.';
    panel.appendChild(hint);
    if(!entries.length){const empty=document.createElement('p');empty.textContent='No items to manage.';panel.appendChild(empty)}
    for(const item of entries){
      const row=document.createElement('div');row.style.cssText='display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap';
      const name=document.createElement('span');name.textContent='#'+item.id+' · '+(item.title||'Untitled');
      name.style.cssText='overflow-wrap:anywhere;min-width:0;flex:1';
      const button=document.createElement('button');button.type='button';button.className='danger';button.textContent='Delete';
      button.style.cssText='padding:7px 11px';
      button.onclick=async()=>{
        if(s.busy)return;
        const gallery=mode==='gallery';
        const text=gallery?'this gallery item':'this library file and its linked gallery items';
        if(!confirm('Delete “'+(item.title||'Untitled')+'”? This removes '+text+' from your studio and new sales. Existing paid unlocks and audit records remain accessible. There is no self-service undo.'))return;
        button.disabled=true;
        try{
          await req(gallery?'/gallery/'+item.id:'/library/'+item.id,{method:'DELETE'});
          if(s.selected===item.id)s.selected=null;
          await load();
          msg('Deleted from Creator Studio.');
        }catch(e){msg(e.message||'Deletion failed',true)}
        finally{button.disabled=false}
      };
      row.append(name,button);panel.appendChild(row);
    }
    // Earlier manager strings must not imply an unnecessary second approval.
    const headline=root.querySelector('.v21341-header p');
    if(headline&&/reviewed before publication/i.test(headline.textContent||''))
      headline.textContent='Approved creators can publish immediately; admins may audit content later.';
    for(const node of root.querySelectorAll('button')){
      const label=node.textContent.trim();
      if(label==='Upload for approval')node.textContent='Upload to library';
      if(label==='Submit gallery item for approval')node.textContent='Publish gallery item';
    }
    for(const node of root.querySelectorAll('p')){
      if(/Master Admin approves the FILE/.test(node.textContent||''))
        node.textContent='Photos up to 20 MB · videos up to 100 MB. Uploaded media can be published immediately by approved creators. Admins may review and remove content later.';
    }
  }
  // Watch only for DOM replacement; the signature check avoids re-render loops.
  function v21356StartManagerEnhancement(){
    const observer=new MutationObserver(v21356DecorateManager);
    observer.observe(document.body,{childList:true,subtree:true});
    v21356DecorateManager();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',v21356StartManagerEnhancement,{once:true});
  else v21356StartManagerEnhancement();
})();
