/* V2138_COMBINED Messenger UX: text links, auto-growing composers, transfer-all, compact notification settings. */
(()=>{'use strict';
const fields=['messageInput','groupMessageInput'];
function resize(el){if(!el)return;el.style.height='auto';el.style.height=Math.max(44,Math.min(150,el.scrollHeight))+'px';el.style.overflowY=el.scrollHeight>150?'auto':'hidden'}
function initInputs(){for(const id of fields){const el=document.getElementById(id);if(!el||el.dataset.v2138Grow)return;el.dataset.v2138Grow='1';el.addEventListener('input',()=>resize(el));el.addEventListener('focus',()=>resize(el));resize(el)}}
const urlPattern=/(https?:\/\/[^\s<>"']+|www\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:\/[^\s<>"']*)?)/ig;
function validLink(raw){try{let u=new URL(raw.startsWith('www.')?'https://'+raw:raw);if(!['https:','http:'].includes(u.protocol))return null;return u.href}catch{return null}}
function linkifyNode(n){if(!n.parentElement||n.parentElement.closest('a,button,textarea,input,script,style,[contenteditable="true"]'))return;const text=n.nodeValue||'';urlPattern.lastIndex=0;const matches=[...text.matchAll(urlPattern)];if(!matches.length)return;
 const fragment=document.createDocumentFragment();let start=0,linked=false;
 for(const m of matches){const pos=m.index,raw=m[0],trimmed=raw.replace(/[.,;:!?\])}]+$/g,'');const link=validLink(trimmed);if(!link)continue;fragment.append(document.createTextNode(text.slice(start,pos)));const a=document.createElement('a');a.href=link;a.target='_blank';a.rel='noopener noreferrer';a.className='v2138-chat-link';a.textContent=trimmed;a.title='Open link in browser';fragment.append(a);fragment.append(document.createTextNode(raw.slice(trimmed.length)));start=pos+raw.length;linked=true}
 if(!linked)return;fragment.append(document.createTextNode(text.slice(start)));n.replaceWith(fragment)
}
function enhanceMessages(){for(const selector of ['#messageList .msg','#groupMessageList .msg','#v2134Messages .v2134-bubble']){document.querySelectorAll(selector).forEach(root=>{const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);nodes.forEach(linkifyNode)})}}
function transferAll(e){const b=e.target.closest('#v2138TransferAll');if(!b)return;const form=b.closest('form');const input=form?.querySelector('input[name="amount_q"]');if(!input)return;const max=Number(b.dataset.available||0);const amount=Math.floor(Math.max(0,max)*1000000+1e-7)/1000000;if(amount<=0)return;input.value=amount.toFixed(6);input.dispatchEvent(new Event('input',{bubbles:true}))}
function enhanceTransfer(){for(const f of document.querySelectorAll('form[data-form="transfer"]')){if(f.querySelector('#v2138TransferAll'))continue;const input=f.querySelector('input[name="amount_q"]');if(!input)continue;input.min='0.000001';input.step='0.000001';const amountText=f.closest('.v213-studio')?.querySelector('.v213-earnings-grid strong')?.textContent||'0';const available=parseFloat(amountText.replace(/,/g,''))||0;const b=document.createElement('button');b.id='v2138TransferAll';b.type='button';b.className='ghost';b.dataset.available=String(available);b.textContent='Transfer all available Q';f.appendChild(b)}}
function compactNotifications(){const more=document.querySelector('#view-more .more-grid');const panel=document.getElementById('v2137Panel');if(!more||!panel||document.getElementById('v2138NotifOpen'))return;const wrapper=document.createElement('div');wrapper.id='v2138NotificationDetail';wrapper.hidden=true;wrapper.innerHTML='<button id="v2138NotifBack" class="ghost v2138-notif-back">‹ Back to More</button>';more.after(wrapper);wrapper.append(panel);
 const card=document.createElement('button');card.id='v2138NotifOpen';card.className='more-card v2138-notif-open';card.type='button';card.innerHTML='<span>🔔</span><strong>Notification management</strong><small>Permission, alerts, sounds and preferences</small>';more.prepend(card);
 card.onclick=()=>{more.hidden=true;wrapper.hidden=false;wrapper.scrollIntoView({block:'start'})};
 document.getElementById('v2138NotifBack').onclick=()=>{wrapper.hidden=true;more.hidden=false};
 const duplicated=[...more.querySelectorAll('.more-card')].filter(b=>/appearance\s*&\s*notifications|appearance and notifications/i.test(b.textContent));duplicated.forEach(b=>{if(!b.matches('#v2138NotifOpen'))b.hidden=true});
}
function run(){initInputs();enhanceMessages();enhanceTransfer();compactNotifications()}
let scheduled=false;const schedule=()=>{if(scheduled)return;scheduled=true;setTimeout(()=>{scheduled=false;run()},90)};
document.addEventListener('DOMContentLoaded',()=>{run();document.body.addEventListener('click',transferAll);new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});setInterval(()=>{for(const id of fields)resize(document.getElementById(id))},1900)})
})();
