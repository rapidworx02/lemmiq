/* V2.13.18 image viewer. Only authenticated private media routes; no persistent full-size cache. */
(()=>{
 'use strict';
 let viewer=null, sequence=0, busyVision=false;
 const S=()=>window.lemmiqState;
 function msg(kind,id){return (kind==='group'?S()?.groupMessages:S()?.messages)?.find(m=>Number(m.id)===id)}
 function allowed(kind,id){const m=msg(kind,id);return !!(S()?.token && m?.attachment?.media_id && !m.deleted_for_everyone && !String(m.text||'').includes('[[QCREATORS_'))}
 function path(kind,id){return kind==='group'?`/v24/group-media/${id}`:`/media/${id}`}
 function photoName(blob,id){const ext=({'image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/gif':'gif'})[blob.type]||'img';return `LEMMIQ-${id}.${ext}`}
 async function original(kind,id){
   if(!allowed(kind,id))throw Error('Photo unavailable');
   const token=S().token;
   const r=await fetch(path(kind,id),{headers:authHeaders(),cache:'no-store'});
   if(!r.ok)throw Error(`Photo unavailable (${r.status})`);
   const blob=await r.blob();
   if(token!==S()?.token || !allowed(kind,id))throw Error('Photo no longer available');
   if(!/^image\/(jpeg|png|webp|gif)$/i.test(blob.type)||!blob.size||blob.size>24*1024*1024)throw Error('Unsupported photo');
   return blob;
 }
 function close(){sequence++;if(viewer){if(viewer.url)URL.revokeObjectURL(viewer.url);viewer.root.remove();viewer=null}}
 function download(blob,id){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=photoName(blob,id);document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('Download requested — check your device downloads')}
 async function vision(kind,id){
   if(busyVision)return;
   busyVision=true;
   try{const blob=viewer?.id===id&&viewer?.kind===kind&&viewer.blob?viewer.blob:await original(kind,id);if(!allowed(kind,id))throw Error('Photo unavailable');close();await uploadQVision(new File([blob],photoName(blob,id),{type:blob.type}));}
   catch(e){toast(e.message||'Unable to analyse photo',true)}finally{busyVision=false}
 }
 function edit(kind,id){if(!allowed(kind,id))return toast('Photo unavailable',true);close();if(window.lemmiqEditPhotoV21318)window.lemmiqEditPhotoV21318(kind,id);else toast('Image editor unavailable',true)}
 function forward(kind,id){const m=msg(kind,id);if(!m||!allowed(kind,id))return;close();openForwardDialog(m,kind)}
 function show(kind,id){const m=msg(kind,id);if(!m||!allowed(kind,id))return;close();const seq=++sequence,token=S().token;
   const root=document.createElement('div');root.className='v318-view';root.setAttribute('role','dialog');root.setAttribute('aria-modal','true');root.setAttribute('aria-label','Photo viewer');
   root.innerHTML='<header><button data-act="close" aria-label="Back">‹</button><div class="v318-heading"><strong></strong><small></small></div><button data-act="forward">Forward</button><button data-act="menu" aria-label="More options">⋮</button></header><div class="v318-options" hidden><button data-act="save">Save photo / download</button><button data-act="share">Share</button><button data-act="forward">Forward</button><button data-act="vision">Ask Q Vision</button><button data-act="edit">Edit with Q</button><button data-act="rotate">Rotate preview</button><button data-act="close">Show in chat</button></div><div class="v318-stage"><img alt="Chat photo"/><span class="v318-loading">Loading original…</span></div><footer><button data-act="save" disabled>Download</button><button data-act="vision">Q Vision</button><button data-act="edit">Edit with Q</button></footer>';
   const sender=m.sender_id===S().user?.id?'You':kind==='group'?(m.sender?.display_name||'Group member'):(S().activeChat?.other_user?.display_name||'Contact');
   root.querySelector('strong').textContent=sender;root.querySelector('small').textContent=new Date(m.created_at).toLocaleString();
   document.body.append(root);const img=root.querySelector('img'),loading=root.querySelector('.v318-loading');
   const thumb=S().mediaBlobUrls.get(kind==='group'?`/v24/group-media/${id}/thumb`:`/v21316/media/thumb/${id}`);if(thumb)img.src=thumb;
   viewer={root,kind,id,url:null,blob:null};let angle=0,zoom=1;
   function update(){img.style.transform=`rotate(${angle}deg) scale(${zoom})`}
   img.addEventListener('dblclick',()=>{zoom=zoom===1?2:1;update()});
   root.addEventListener('click',async e=>{const a=e.target.closest('[data-act]')?.dataset.act;if(!a)return;
     if(a==='close')return close();if(token!==S()?.token||!allowed(kind,id))return close();
     const menu=root.querySelector('.v318-options');if(a==='menu'){menu.hidden=!menu.hidden;return}menu.hidden=true;
     if(a==='rotate'){angle=(angle+90)%360;update();return}if(a==='vision')return vision(kind,id);if(a==='edit')return edit(kind,id);if(a==='forward')return forward(kind,id);
     if(!viewer?.blob)return toast('Original photo is still loading',true);
     const b=viewer.blob;if(a==='save')return download(b,id);
     if(a==='share'){
       const f=new File([b],photoName(b,id),{type:b.type});
       try{if(navigator.canShare?.({files:[f]}))await navigator.share({files:[f]});else download(b,id)}catch(err){if(err.name!=='AbortError')toast('Sharing unavailable. Use Download.',true)}
     }
   });
   original(kind,id).then(blob=>{if(sequence!==seq||token!==S()?.token)return;viewer.blob=blob;viewer.url=URL.createObjectURL(blob);img.src=viewer.url;loading.hidden=true;root.querySelectorAll('[data-act="save"],[data-act="share"]').forEach(b=>b.disabled=false)}).catch(e=>{if(sequence===seq){loading.textContent=e.message||'Original unavailable';root.querySelectorAll('[data-act="save"],[data-act="share"]').forEach(b=>b.disabled=true)}});
 }
 function bind(host){host.querySelectorAll('.v318-photo-wrap').forEach(w=>{if(w.dataset.bound318)return;w.dataset.bound318='1';const kind=w.dataset.kind,id=Number(w.dataset.id);w.querySelector('[data-v318-vision]').onclick=()=>vision(kind,id);w.querySelector('[data-v318-edit]').onclick=()=>edit(kind,id);w.querySelector('[data-v318-menu]').onclick=()=>kind==='direct'?openMessageMenu(id):show(kind,id)})}
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&viewer){e.preventDefault();close()}});
 window.v318Media={show,bind,close,vision,edit,forward};
})();
