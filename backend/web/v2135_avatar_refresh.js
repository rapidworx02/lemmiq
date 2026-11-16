/* LEMMIQ V2.13.5: refresh current user's stale session avatar after sign in. */
(()=>{'use strict';
  async function refresh(){
    const token=window.lemmiqState?.token;
    if(!token||!window.lemmiqState?.user)return;
    try{
      const response=await fetch('/me',{headers:{Authorization:'Bearer '+token,'Cache-Control':'no-cache'},cache:'no-store'});
      if(!response.ok)return;
      const fresh=await response.json();
      if(!fresh?.id||fresh.id!==window.lemmiqState.user.id)return;
      const previous=window.lemmiqState.user;
      window.lemmiqState.user={...previous,...fresh};
      localStorage.setItem('lemmiq_user',JSON.stringify(window.lemmiqState.user));
      if(typeof renderMeAvatar==='function')renderMeAvatar();
      if((fresh.avatar_url||'')!==(previous.avatar_url||'')){
        if(typeof loadChats==='function')await loadChats(true).catch(()=>{});
      }
    }catch{}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    // If an old object is missing, remove only its failed <img> so initials remain.
    document.addEventListener('error',event=>{
      const img=event.target;
      if(!(img instanceof HTMLImageElement))return;
      if(img.closest('.v2135-avatar')){img.remove();return}
      // Covers locally customised avatarHtml or renderMeAvatar implementations too.
      const wrapper=img.closest('.avatar, .profile-avatar');
      if(wrapper && !wrapper.querySelector('.v2135-fallback')){
        const row=wrapper.closest('.chat-row');
        const name=row?.querySelector('.body strong')?.textContent?.trim() ||
          document.getElementById('chatName')?.textContent?.trim() || '?';
        const fallback=document.createElement('span');
        fallback.className='v2135-fallback';
        fallback.textContent=name.slice(0,1).toUpperCase();
        wrapper.appendChild(fallback);
        img.remove();
      }
    },true);
    setTimeout(refresh,1400);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
    const card=document.getElementById('callCard');
    const stage=document.getElementById('callVideoStage');
    const state=document.getElementById('callState');
    if(card&&stage&&state){
      const update=()=>card.classList.toggle('v2135-video-connected',!stage.classList.contains('hidden')&&state.textContent.trim()==='Connected');
      const observer=new MutationObserver(update);
      observer.observe(state,{subtree:true,childList:true,characterData:true});
      observer.observe(stage,{attributes:true,attributeFilter:['class']});
      update();
    }
  });
})();
