/* LEMMIQ V2.13.6 — navigation hubs and lightweight Creator Studio shortcuts.
   No global MutationObserver, no polling, no new backend routes. */
(()=>{'use strict';
  const $=id=>document.getElementById(id);
  const views=[['agent','✨ Ask Q'],['q-economy','Q Wallet'],['q-predict','◈ Q Predict']];
  function visit(name){
    if(typeof setView!=='function')return;
    setView(name);
    if(location.hash!=='#'+name)history.pushState({view:name},'', '#'+name);
  }
  function qSwitcher(){
    for(const id of ['agent']){
      const view=$('view-'+id);if(!view||view.querySelector('.v2136-q-switcher'))continue;
      const row=document.createElement('nav');row.className='v2136-q-switcher';
      row.setAttribute('aria-label','Q workspace navigation');
      for(const [route,label] of views){
        const button=document.createElement('button');button.type='button';button.textContent=label;
        button.className=route===id?'active':'';button.dataset.v2136Route=route;
        if(route===id)button.setAttribute('aria-current','page');row.append(button);
      }
      view.prepend(row);
    }
  }
  function creatorReady(){ /* V304: creator home owns all visible shortcuts. */ }
  window.v2136CreatorReady=creatorReady;
  document.addEventListener('click',e=>{
    const route=e.target.closest('[data-v2136-route]');
    if(route){visit(route.dataset.v2136Route);return}
    const button=e.target.closest('[data-v2136-creator]');if(!button)return;
    if(button.dataset.v2136Creator==='studio'){
      const b=document.querySelector('#v213CreatorsApp [data-mode="studio"]');
      if(b)b.click();
    }else if(button.dataset.v2136Creator==='gallery'){
      if(window.LEMMIQCreatorGalleryV21341?.openManager)window.LEMMIQCreatorGalleryV21341.openManager();
      else if(typeof toast==='function')toast('Creator gallery manager unavailable',true);
    }else if(button.dataset.v2136Creator==='inbox'){
      if(window.openCreatorProfessionalInbox)window.openCreatorProfessionalInbox('inbox');
      else if(typeof toast==='function')toast('Professional inbox unavailable',true);
    }
  });
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',qSwitcher,{once:true});
  else qSwitcher();
})();
// V304_INSTALLED
