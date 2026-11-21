/* V3.0 UI: single navigation owner for compact mobile conversations. No market polling. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),S=()=>window.lemmiqState;
 function menu(actions){openModal('<h3>Chat tools</h3><div class="v300-action-list"></div>');const host=document.querySelector('#modalContent .v300-action-list');for(const [label,action] of actions){const b=document.createElement('button');b.className='ghost';b.textContent=label;b.onclick=()=>{closeModal();action()};host.append(b)}}
 const click=id=>()=>$(id)?.click();
 function initChat(){for(const [id,kind] of [['activeChat','direct'],['activeGroup','group'],['activeQThread','q']]){const root=$(id),head=root?.querySelector('.chat-head'),actions=head?.querySelector('.chat-head-actions');if(!head||head.querySelector('.v300-back'))continue;
  const back=document.createElement('button');back.type='button';back.className='v300-back ghost';back.textContent='‹';back.setAttribute('aria-label','Back to chats');back.onclick=()=>chatsHome(true);head.prepend(back);
  if(kind==='q'){
    const ask=document.createElement('form');ask.className='v300-ask-row';ask.innerHTML='<input aria-label="Ask Q" placeholder="Ask Q about your chats" maxlength="1600"><button class="primary" type="submit">Send</button>';const response=document.createElement('div');response.className='v300-q-response';response.hidden=true;response.setAttribute('role','status');root.append(response,ask);
    ask.onsubmit=async e=>{e.preventDefault();const input=ask.querySelector('input'),btn=ask.querySelector('button'),question=input.value.trim(),token=S()?.token;if(!question||btn.disabled)return;btn.disabled=true;response.hidden=false;response.textContent='Q is thinking…';try{const result=await api('/agent/ask',{method:'POST',body:JSON.stringify({question,days:30,external_context:[]})});if(token!==S()?.token)return;response.textContent=result.answer||'No answer available.';input.value=''}catch(err){response.textContent=err.message||'Q unavailable'}finally{btn.disabled=false}};
    continue;
  }
  const q=document.createElement('button');q.type='button';q.className='v300-qmenu ghost';q.textContent='Q';q.setAttribute('aria-label','Q assistant tools');q.onclick=()=>menu(kind==='direct'?[...(S()?.activeChat?.ai_mode==='ASSIST'?[['Suggest reply',click('assistBarBtn')]]:[]),['Summarise conversation',click('summaryBtn')],['Chat AI settings',click('chatAiBtn')],['Generate image',()=>{const button=$('activeChat')?.querySelector('.composer [title*="image" i],.composer [title*="Q Image" i]');if(button)button.click();else toast('Use the existing image action to generate an image')}]]:[...(S()?.activeGroup?.ai_mode==='ASSIST'?[['Suggest reply',click('groupSuggestTop')]]:[]),['Summarise group',click('groupCatchupBtn')],['Ask Q',click('groupQBtn')]]);actions.append(q);
  const more=document.createElement('button');more.type='button';more.className='v300-chatmenu ghost';more.textContent='⋮';more.setAttribute('aria-label','Conversation options');more.onclick=()=>menu(kind==='direct'?[['Search messages',click('chatSearchBtn')],['Chat AI settings',click('chatAiBtn')],['Conversation settings',click('chatMoreBtn')],['Business tools',click('businessChatBtn')]]:[['Group settings',click('groupSettingsBtn')]]);actions.append(more);
 }}
 function layout(){const chats=$('view-chats')?.classList.contains('active'),pane=document.querySelector('.chat-layout'),open=!!pane?.classList.contains('open-chat');const active=!!chats&&open;document.body.classList.toggle('v300-conversation',active);document.body.classList.toggle('v305-chat-list',!!chats&&!open);if(chats)pane?.style.removeProperty('height');viewport()}
 function viewport(){document.documentElement.style.setProperty('--v300-vh',`${Math.round(window.visualViewport?.height||window.innerHeight)}px`)}
 function init(){initChat();viewport();layout();
  document.addEventListener('click',e=>{const b=e.target.closest('[data-v300-file]');if(!b)return;const id=Number(b.dataset.v300File),name=b.dataset.name||'Attachment';if(b.dataset.kind==='group')downloadGroupMedia(id,name);else downloadMedia(id,name)});

  const admin=$('view-q-admin');if(admin){const sel=document.createElement('select');sel.setAttribute('aria-label','Jump to admin section');const choices=[['','Jump to admin section'],['v29PredictAutomation','Q Predict'],['v29OperationsStats','Operations'],['q28AdminTeamCard','Roles'],['q28WalletMatrix','Receiving wallets'],['q28AdminUsers','Users and packages'],['q28AdminPayments','Payment review'],['q28AdminTreasury','Treasury'],['q28AdminMarketOrders','Marketplace'],['q28AdminLedger','Ledger'],['q28AdminAudit','Audit']];for(const [id,label] of choices){const o=document.createElement('option');o.value=id;o.textContent=label;sel.append(o)}sel.onchange=()=>$(sel.value)?.closest('article')?.scrollIntoView({block:'start',behavior:'smooth'});admin.prepend(sel)}
  const grid=$('view-more')?.querySelector('.more-grid');const profile=grid?.querySelector('[data-more-view="me"]');if(profile)grid.prepend(profile);grid?.querySelector('[data-more-view="updates"]')?.remove();
const list=document.querySelector('[data-q28-tab]')?.parentElement;list?.classList.add('v300-wallet-tabs');const observer=new MutationObserver(layout);for(const e of [$('view-chats'),document.querySelector('.chat-layout')])if(e)observer.observe(e,{attributes:true,attributeFilter:['class']});window.visualViewport?.addEventListener('resize',viewport);window.addEventListener('resize',viewport);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();

})();
// V301_INSTALLED
// V302_INSTALLED
// V303_INSTALLED
// V305_INSTALLED
