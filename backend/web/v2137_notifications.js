/* V2137_NOTIFICATIONS_CRICKET — automatic existing-permission push registration, settings and cricket previews */
(()=>{
 'use strict';
 const root=document.createElement('div'); root.id='v2137Panel';
 const apiCall=(p,o)=>window.api('/v2137'+p,o);
 const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&quot;'}[c]));
 let stored={};try{stored=JSON.parse(localStorage.getItem('lemmiq_v2137_preferences')||'{}')}catch{}
 const st={settings:stored,registered:'',busy:false};
 const defaults={messages:true,groups:true,calls:true,updates:true,q:true,sound:true,preview:true};
 st.settings={...defaults,...st.settings};
 const save=()=>localStorage.setItem('lemmiq_v2137_preferences',JSON.stringify(st.settings));
 let audioCtx;
 function tone(){if(!st.settings.sound)return;try{audioCtx=audioCtx||new (window.AudioContext||window.webkitAudioContext)();if(audioCtx.state==='suspended')audioCtx.resume();let o=audioCtx.createOscillator(),g=audioCtx.createGain();o.type='sine';o.frequency.value=880;g.gain.setValueAtTime(.045,audioCtx.currentTime);g.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+.18);o.connect(g);g.connect(audioCtx.destination);o.start();o.stop(audioCtx.currentTime+.19)}catch{}}
 function permission(){return 'Notification' in window?Notification.permission:'unsupported'}
 function token(){return localStorage.getItem('lemmiq_token')||''}
 function status(t){const x=document.getElementById('v2137PushStatus');if(x)x.textContent=t}
 async function register(){
   if(st.busy||!token()||permission()!=='granted')return;
   st.busy=true;
   try{
     const cfg=await window.api('/app-config');
     if(!cfg.web_push_configured||!window.firebase?.messaging){status('Firebase web push is not configured or unavailable');return}
     const sw=await navigator.serviceWorker.register('/web/sw.js?v=2.13.7');
     if(!firebase.apps.length)firebase.initializeApp(cfg.firebase_web_config);
     const msg=firebase.messaging();
     const id=await msg.getToken({vapidKey:cfg.firebase_web_vapid_key,serviceWorkerRegistration:sw});
     if(!id)throw Error('No FCM token');
     const key=token()+'|'+id;
     // Always renew on login/reload; never infer successful server delivery from local permission.
     if(st.registered!==key){await window.api('/push/register',{method:'POST',body:JSON.stringify({token:'WEB:'+id})});st.registered=key}
     status('Permission allowed · browser device registered. Delivery still requires a test.');
     if(!st.msgHook){msg.onMessage(payload=>{
       const d=payload.data||{},type=String(d.type||'chat');
       const k=type==='chat'?'messages':type==='group'?'groups':type==='call'?'calls':type.startsWith('q_')?'q':'updates';
       if(st.settings[k]){if(typeof window.toast==='function')window.toast(`${d.sender_name||d.title||'LEMMIQ'}: ${st.settings.preview?(d.body||'New activity'):'New notification'}`);tone()}
       if(document.visibilityState==='visible')resync();
     });st.msgHook=true}
   }catch(e){status('Registration failed: '+(e.message||String(e)))}
   finally{st.busy=false}
 }
 let refreshRunning=false;
 async function resync(){
   if(!token()||document.visibilityState!=='visible'||refreshRunning)return;
   refreshRunning=true;
   try{
     const rt=window.LEMMIQV2137;
     if(rt?.state?.socket && rt.state.socket.readyState>1)rt.connectSocket();
     if(typeof window.loadChats==='function')await window.loadChats(true);
     if(rt?.state?.activeChat && typeof window.openChat==='function')await window.openChat(rt.state.activeChat.id,false);
     if(rt?.state?.activeGroup && typeof window.openGroup==='function')await window.openGroup(rt.state.activeGroup.id,false);
   }catch(e){console.warn('LEMMIQ foreground resync',e)}finally{refreshRunning=false}
 }
 async function requestNotifications(){
   if(!('Notification' in window))return status('This browser does not support notifications.');
   if(permission()==='default')await Notification.requestPermission();
   if(permission()==='granted')await register();else status('Permission '+permission()+' · enable site notifications in browser settings');
 }
 async function testPush(){try{const r=await apiCall('/notifications/test',{method:'POST',body:'{}'});status('Sent to '+r.attempted_devices+' registered device(s); verify notification centre.')}catch(e){status('Test failed: '+e.message)}}
 async function diagnostics(){try{const r=await apiCall('/notifications/status');status('Browser: '+permission()+' · web devices: '+r.web_devices+' · Android devices: '+r.android_devices+' · Firebase sender: '+(r.firebase_server?'ready':'not configured'))}catch(e){status('Status unavailable: '+e.message)}}
 function panel(){
   const more=document.querySelector('#view-more .more-grid');if(!more||document.getElementById('v2137Panel'))return;
   root.className='v2137-card';root.innerHTML=`<h3>🔔 Notification management</h3><p class="micro">Automatically reconnects after you approve browser notifications. Background alert sound is controlled by your device.</p><p id="v2137PushStatus" role="status">Checking device…</p><div class="v2137-actions"><button id="v2137Enable" class="primary">Allow notifications</button><button id="v2137Test" class="ghost">Send test</button><button id="v2137Check" class="ghost">Check status</button><button id="v2137Tone" class="ghost">Preview in-app tone</button></div><div id="v2137Options"></div><p class="micro">Browser background notifications use Chrome/OS sound settings. Settings here control foreground alerts; OS permission can be changed in system settings.</p>`;
   more.prepend(root);
   // Old manual activation button is no longer needed; keep older code intact for rollback.
   document.querySelectorAll('[data-v211-push]').forEach(b=>b.hidden=true);
   document.getElementById('v2137Enable').onclick=requestNotifications;
   document.getElementById('v2137Test').onclick=testPush;
   document.getElementById('v2137Check').onclick=diagnostics;
   document.getElementById('v2137Tone').onclick=tone;
   const opts=document.getElementById('v2137Options');
   for(const [key,label] of [['messages','Direct messages'],['groups','Groups'],['calls','Incoming calls'],['updates','Updates / Status'],['q','Q alerts'],['sound','In-app sounds'],['preview','Message previews']]){
     let row=document.createElement('label');row.className='v2137-toggle';
     const input=document.createElement('input');input.type='checkbox';input.checked=!!st.settings[key];input.addEventListener('change',()=>{st.settings[key]=input.checked;save()});
     row.append(document.createTextNode(label),input);opts.append(row);
   }
   if(permission()==='granted'){document.getElementById('v2137Enable').hidden=true;register()}else status('Permission: '+permission()+' — tap Allow notifications once');
 }
 async function fixtures(){
   const host=document.getElementById('v2137Cricket');if(!host)return;
   host.textContent='Loading cricket fixtures…';
   try{
     const response=await apiCall('/cricket/fixtures');const items=response.fixtures||[];
     host.innerHTML=`<strong>🏏 Global cricket fixtures</strong><p class="micro">${escape(items.length?`${response.count} upcoming fixtures · markets require Admin approval`:'No feed configured or no upcoming fixtures.')}</p>`;
     for(const m of items.slice(0,24)){
       const row=document.createElement('div');row.className='v2137-fixture';
       row.innerHTML=`<b>${escape(m.team_a)} vs ${escape(m.team_b)}</b><span>${escape(m.series)} · ${escape(m.format)} · ${escape(new Date(m.start_at).toLocaleString())}</span>`;
       host.append(row)
     }
   }catch(e){host.textContent='Cricket feed is unavailable: '+e.message}
 }
 function cricketUI(){
   const container=document.querySelector('#view-q-predict');if(!container||document.getElementById('v2137Cricket'))return;
   const c=document.createElement('article');c.id='v2137Cricket';c.className='card glass v2137-cricket';container.append(c);fixtures();
 }
 async function adminUI(){
   const host=document.getElementById('v29PredictAutomation');if(!host||document.getElementById('v2137Admin'))return;
   const box=document.createElement('div');box.id='v2137Admin';box.className='v2137-admin';
   box.innerHTML=`<label>Real Q staking (server-authorized only) <select id="v2137RealQ"><option value="false">OFF</option><option value="true">ON (requires authorization)</option></select></label><button id="v2137SaveRealQ" class="ghost">Save staking status</button><button id="v2137DraftCricket" class="ghost">Import cricket drafts for review</button><small id="v2137AdminStatus">Loading control…</small>`;
   host.after(box);
   try{const c=await window.api('/v29/predict/admin/config');document.getElementById('v2137RealQ').value=String(!!c.real_q_enabled);document.getElementById('v2137AdminStatus').textContent=c.real_q_enabled?'Requested ON; backend legal guard still applies.':'OFF — no new real-Q stakes.'}catch(e){box.remove();return}
   document.getElementById('v2137SaveRealQ').onclick=async()=>{
     const on=document.getElementById('v2137RealQ').value==='true';if(on&&!confirm('Only enable real-Q sports wagering if legally authorized in every eligible jurisdiction. Continue?'))return;
     try{const r=await window.api('/v29/predict/admin/config',{method:'PUT',body:JSON.stringify({real_q_enabled:on})});document.getElementById('v2137AdminStatus').textContent='Saved: '+(r.real_q_enabled?'ON':'OFF')+' · Server authorization controls real staking.'}catch(e){document.getElementById('v2137AdminStatus').textContent=e.message}}
   document.getElementById('v2137DraftCricket').onclick=async()=>{try{const r=await apiCall('/cricket/admin/draft',{method:'POST',body:'{}'});document.getElementById('v2137AdminStatus').textContent=`${r.drafted} cricket drafts queued for admin approval.`}catch(e){document.getElementById('v2137AdminStatus').textContent=e.message}}
 }
 document.addEventListener('DOMContentLoaded',()=>{
   panel();cricketUI();
   const obs=new MutationObserver(()=>{panel();cricketUI();if(document.getElementById('view-q-admin')?.classList.contains('active'))adminUI()});
   obs.observe(document.body,{childList:true,subtree:true});
   if(permission()==='granted')register();
   document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){resync();register()}});
   window.addEventListener('online',()=>{resync();register()});
   window.addEventListener('focus',()=>resync());
   let last='';setInterval(()=>{const current=token();if(current!==last){last=current;st.registered='';if(current)register()}},2500);
   setTimeout(()=>{if(token())resync()},1200);
 });
})();
