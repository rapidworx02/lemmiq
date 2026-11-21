/* LEMMIQ 2.13.14 – admin-reviewed Test/ODI/T20 cricket markets, Demo-only. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const api=(p,o)=>window.api('/v21314/cricket'+p,o);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const notice=s=>{let e=$('pq14Status');if(e)e.textContent=String(s)};
const state={templates:[],fixtures:[],markets:[],busy:false};
let mounted=false;
function selectedTemplate(){return state.templates.find(x=>x.code===$('pq14Template')?.value)}
function currentFixture(){return state.fixtures.find(x=>x.id===$('pq14Fixture')?.value)}
function safeLocalToISO(value){if(!value)return '';const d=new Date(value);return Number.isFinite(d.getTime())?d.toISOString():''}
function fields(){const template=selectedTemplate();const m=currentFixture();const manual=!m;const root=$('v21314CricketAdmin');if(!root)return;
 root.querySelectorAll('[data-pq14-manual]').forEach(el=>el.hidden=!manual);
 root.querySelectorAll('[data-pq14-team]').forEach(el=>el.hidden=!template?.needs_team);
 root.querySelectorAll('[data-pq14-player]').forEach(el=>el.hidden=!template?.needs_player);
 root.querySelectorAll('[data-pq14-threshold]').forEach(el=>el.hidden=!template||!['TEAM_INNINGS_RUNS','BATTER_RUNS','BOWLER_WICKETS','DAY_WICKETS','DAY_RUNS'].includes(template.code));
 root.querySelectorAll('[data-pq14-day]').forEach(el=>el.hidden=!['DAY_WICKETS','DAY_RUNS'].includes(template?.code));
 root.querySelectorAll('[data-pq14-innings]').forEach(el=>el.hidden=!['TEAM_INNINGS_RUNS','BATTER_RUNS','BOWLER_WICKETS','PLAYER_CENTURY'].includes(template?.code));
 const team=$('pq14Team');if(team){const prev=team.value;const teams=m?[m.team_a,m.team_b]:[$('pq14A')?.value?.trim(),$('pq14B')?.value?.trim()].filter(Boolean);team.replaceChildren();for(const name of teams){let opt=document.createElement('option');opt.value=name;opt.textContent=name;team.append(opt)}if(teams.includes(prev))team.value=prev;}
 if(template && $('pq14Threshold') && document.activeElement!==$('pq14Threshold'))$('pq14Threshold').value=String(template.default_threshold);
 if(m && $('pq14FormatText'))$('pq14FormatText').textContent=`${m.format} · ${m.series} · ${new Date(m.start_at).toLocaleString()}`;
 else if($('pq14FormatText'))$('pq14FormatText').textContent='Manual fixture: enter both teams, start, series and official source';
}
function renderMarkets(){let el=$('pq14Markets');if(!el)return;
 el.innerHTML=(state.markets.length?state.markets.map(m=>`<article class="pq14-card"><b>#${m.id} · ${safe(m.status)} · ${safe(m.template)}</b><p>${safe(m.question)}</p><p class="pq14-muted">Closes ${safe(new Date(m.close_at).toLocaleString())} · ${m.reviewed?'Pre-approved':'Needs review'} · DEMO ONLY</p><div class="pq14-actions"><button class="ghost" data-v306-manage="${m.id}">Manage market</button>${(['WRITE','FULL'].includes(window.v307PredictLevel?.())&&(m.status==='REVIEW'||m.status==='DRAFT'))?`<button class="ghost" data-pq14-publish="${m.id}">Review & publish</button>`:''}${window.v307PredictLevel?.()==='FULL'&&['LIVE','CLOSED','SUSPENDED'].includes(m.status)&&Date.parse(m.close_at)<=Date.now()?`<button class="ghost" data-pq14-resolve="${m.id}">Record official Demo result</button>`:''}</div></article>`).join(''):'<div class="pq14-muted">No new cricket performance markets drafted yet.</div>');
 el.querySelectorAll('[data-v306-manage]').forEach(b=>b.onclick=()=>window.v306OpenMarket?.(+b.dataset.v306Manage));
 el.querySelectorAll('[data-pq14-publish]').forEach(b=>b.onclick=()=>publish(Number(b.dataset.pq14Publish)));
 el.querySelectorAll('[data-pq14-resolve]').forEach(b=>b.onclick=()=>resolve(Number(b.dataset.pq14Resolve)));
}
function render(){const host=$('v21314CricketAdmin');if(!host)return;
 host.innerHTML=`<h3>🏏 Cricket Performance Market Studio · V2.13.14</h3><p class="pq14-muted">TEST, ODI and T20. Eight YES/NO templates. Drafts are <b>REVIEW only</b>; results require an official scorecard and manual admin verification. New markets are <b>Demo-only</b> — not eligible for real Q staking.</p>
 <div class="pq14-grid"><label>Upcoming fixture<select id="pq14Fixture"><option value="">Manual fixture entry</option>${state.fixtures.map(x=>`<option value="${safe(x.id)}">${safe(x.format)} · ${safe(x.team_a)} vs ${safe(x.team_b)} (${safe(x.series)})</option>`).join('')}</select></label><label>Market template<select id="pq14Template">${state.templates.map(x=>`<option value="${safe(x.code)}">${safe(x.name)}${x.test_only?' · TEST only':''}</option>`).join('')}</select></label></div>
 <p class="pq14-muted" id="pq14FormatText"></p>
 <div class="pq14-grid"><label data-pq14-manual>Team A<input id="pq14A" placeholder="India" maxlength="90"></label><label data-pq14-manual>Team B<input id="pq14B" placeholder="New Zealand" maxlength="90"></label><label data-pq14-manual>Series<input id="pq14Series" placeholder="Official Test series name" maxlength="120"></label><label data-pq14-manual>Format<select id="pq14Format"><option>TEST</option><option>ODI</option><option>T20</option></select></label><label data-pq14-manual>Start (local time)<input id="pq14Start" type="datetime-local"></label><label>Official result / scorecard URL<input id="pq14Url" type="url" placeholder="https://official-source.example/match-scorecard" maxlength="450"></label><label data-pq14-team>Team<select id="pq14Team"></select></label><label data-pq14-player>Player name (verify playing XI)<input id="pq14Player" maxlength="90" placeholder="Full official player name"></label><label data-pq14-threshold>At least (runs/wickets)<input id="pq14Threshold" type="number" min="1" max="700" value="300"></label><label data-pq14-innings>Team innings<select id="pq14Innings"><option value="1">First</option><option value="2">Second</option></select></label><label data-pq14-day>Test day<select id="pq14Day"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label></div>
 <div class="pq14-actions"><button class="primary" id="pq14Draft">Create review draft</button><button class="ghost" id="pq14Import">Import upcoming TEST markets</button><button class="ghost" id="pq14Reload">Refresh fixtures & drafts</button></div>
 <p class="pq14-status" role="status" id="pq14Status"></p><h4>Generated cricket markets</h4><div id="pq14Markets"></div>`;
 $('pq14Fixture').onchange=fields;$('pq14Template').onchange=fields;
 $('pq14A').oninput=fields;$('pq14B').oninput=fields;
 $('pq14Draft').onclick=draft;$('pq14Import').onclick=importTests;$('pq14Reload').onclick=reload;
 fields();renderMarkets();
}
function payload(){const f=currentFixture();const src=$('pq14Start')?.value||'';return {
 match_id:f?.id||'',team_a:f?.team_a||$('pq14A')?.value.trim()||'',team_b:f?.team_b||$('pq14B')?.value.trim()||'',
 format:f?.format||$('pq14Format')?.value||'TEST',series:f?.series||$('pq14Series')?.value.trim()||'',
 start_at:f?.start_at||safeLocalToISO(src),official_url:$('pq14Url')?.value.trim()||'',
 template:$('pq14Template')?.value||'',team:$('pq14Team')?.value||'',player:$('pq14Player')?.value.trim()||'',
 threshold:Number($('pq14Threshold')?.value||0),innings:Number($('pq14Innings')?.value||1),day:Number($('pq14Day')?.value||1)
}}
async function draft(){if(state.busy)return;const data=payload();if(!data.official_url.startsWith('https://'))return notice('Enter a genuine HTTPS official scorecard URL.');if(!data.match_id&&!data.start_at)return notice('Enter the fixture start time in your local timezone.');state.busy=true;
 try{const r=await api('/admin/draft',{method:'POST',body:JSON.stringify(data)});notice(`${r.created?'Draft created':'Already drafted'}: #${r.id} · ${r.question}`);await listMarkets()}
 catch(e){notice(`Draft failed: ${e.message}`)}finally{state.busy=false}}
async function importTests(){if(state.busy)return;const url=$('pq14Url')?.value.trim()||'';if(!url.startsWith('https://'))return notice('Enter a real official result/scorecard URL before importing Test drafts.');if(!confirm('Import 7 review-only Demo markets for the selected (or next upcoming) TEST fixture? This does not publish or enable betting.'))return;state.busy=true;
 try{const r=await api('/admin/import-tests',{method:'POST',body:JSON.stringify({official_url:url,match_id:currentFixture()?.id||"",max_fixtures:1})});notice(`${r.drafted} Test review drafts created (${r.eligible_test_fixtures} upcoming fixtures found). Publish only after checking match dates, teams and scorecard.`);await listMarkets()}
 catch(e){notice(`Test import failed: ${e.message}`)}finally{state.busy=false}}
async function publish(id){if(!confirm(`Have you personally verified match, players, market rule, official scorecard and close time for #${id}? Publish this DEMO-only market?`))return;
 try{await window.api(`/v29/predict/admin/markets/${id}/publish`,{method:'POST',body:'{}'});notice(`Market #${id} published for Demo. Review settlement evidence when it closes.`);await listMarkets()}
 catch(e){notice(`Cannot publish #${id}: ${e.message}`)}}
async function resolve(id){const m=state.markets.find(x=>x.id===id);if(!m)return;
 const url=prompt(`Official scorecard URL for #${id}`,m.official_url||'');if(!url)return;
 const evidence_note=prompt('Evidence note: checked scorecard, innings, day and player. Minimum 16 characters.');if(!evidence_note||evidence_note.length<16)return notice('Detailed evidence note required.');
 const data={market_id:id,official_url:url.trim(),evidence_note};
 const voided=confirm('Was this market voided because of abandonment, missing scorecard, no play or another qualifying condition? OK=VOID, Cancel=continue to numeric result.');
 if(voided){const reason=prompt('Why VOID? (minimum 15 characters)');if(!reason||reason.length<15)return;data.void_reason=reason}
 else if(m.template==='MATCH_DRAW'){const result=prompt('Official Test result: DRAW, DECIDED, TIE, or ABANDONED')?.trim().toUpperCase();if(!['DRAW','DECIDED','TIE','ABANDONED'].includes(result))return notice('Invalid result');data.result=result}
 else if(m.template==='FIRST_INNINGS_LEAD'){
   const a=prompt('First-listed team first-innings total (official scorecard)');const b=prompt('Second-listed team first-innings total');if(!/^\d+$/.test(a||'')||!/^\d+$/.test(b||''))return notice('Two valid inning totals required');data.team_a_runs=Number(a);data.team_b_runs=Number(b)}
 else{const n=prompt('Observed official statistic (team runs, batter runs, bowler wickets, day total, or 100 for a century)');if(!/^\d+$/.test(n||''))return notice('An official integer statistic is required');data.observed=Number(n)}
 if(!confirm(`Finalize Demo market #${id} with official scorecard evidence? This is irreversible.`))return;
 try{const r=await api('/admin/resolve-demo-stat',{method:'POST',body:JSON.stringify(data)});notice(`Demo result ${r.result} recorded for #${id}. ${r.settled_demo_markets} pooled markets settled.`);await listMarkets()}
 catch(e){notice(`Could not settle #${id}: ${e.message}`)}}
async function listMarkets(){try{const r=await api('/admin/markets');state.markets=r.markets||[];renderMarkets()}catch(e){notice('Unable to load markets: '+e.message)}}
let reloadFlight=null,loadedToken=null;
function statusNode(text){const host=$('v21314CricketAdmin');if(!host)return;let target=$('pq14Status');if(!target){target=document.createElement('p');target.id='pq14Status';target.setAttribute('role','status');host.append(target)}target.textContent=text}
function retryShell(){const host=$('v21314CricketAdmin');if(!host)return;host.replaceChildren();const h=document.createElement('h3');h.textContent='Cricket Performance Market Studio';const p=document.createElement('p');p.id='pq14Status';p.setAttribute('role','status');p.textContent='Loading cricket catalog and markets…';const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent='Retry / refresh cricket studio';b.onclick=()=>reload();host.append(h,p,b)}
async function reload(){
 const token=window.lemmiqState?.token;if(!token||!window.v307CanPredict?.())return;
 if(reloadFlight&&loadedToken===token)return reloadFlight;
 loadedToken=token;
 const host=$('v21314CricketAdmin');if(!host)return;
 if(!$('pq14Fixture'))retryShell();
 const valid=()=>window.lemmiqState?.token===token&&window.v307CanPredict?.();
 const bounded=(path,ms=12000)=>{const ctrl=new AbortController();const t=setTimeout(()=>ctrl.abort(),ms);return api(path,{signal:ctrl.signal}).finally(()=>clearTimeout(t))};
 const work=(async()=>{
   // Catalog and market list do not depend on the external fixture provider.
   const [c,m]=await Promise.allSettled([bounded('/admin/catalog'),bounded('/admin/markets')]);
   if(!valid())return;
   const problems=[];
   if(c.status==='fulfilled'&&Array.isArray(c.value?.templates)){state.templates=c.value.templates}else{state.templates=[];problems.push('Catalog: '+(c.reason?.message||'invalid response'))}
   if(m.status==='fulfilled'&&Array.isArray(m.value?.markets)){state.markets=m.value.markets}else{state.markets=[];problems.push('Markets: '+(m.reason?.message||'invalid response'))}
   state.fixtures=[];render();
   $('pq14Draft').disabled=!state.templates.length||!['WRITE','FULL'].includes(window.v307PredictLevel?.());$('pq14Import').disabled=true;
   statusNode([...problems,'Loading optional fixtures…'].join(' · '));
   try{const f=await bounded('/admin/fixtures');if(!valid())return;state.fixtures=Array.isArray(f?.fixtures)?f.fixtures:[];
     // Update just the fixture picker, not the form or generated market cards.
     const picker=$('pq14Fixture');if(picker){const old=picker.value;picker.replaceChildren(new Option('Manual fixture entry',''));for(const x of state.fixtures)picker.add(new Option(`${x.format} · ${x.team_a} vs ${x.team_b} (${x.series})`,x.id));if([...picker.options].some(o=>o.value===old))picker.value=old;fields()}
     $('pq14Import').disabled=!state.templates.length||!state.fixtures.length||!['WRITE','FULL'].includes(window.v307PredictLevel?.());
     if(f?.error||!f?.configured)problems.push(f?.error||'Licensed cricket feed not configured. Manual fixture entry remains available.');
   }catch(e){if(valid())problems.push('Fixtures unavailable: '+(e.message||'request failed')+'. Manual entry remains available.');}
   if(valid())statusNode(problems.join(' · ')||'Cricket studio ready.');
 })().catch(e=>{if(valid()){retryShell();statusNode('Cricket Studio: '+(e.message||'request failed'))}});
 reloadFlight=work;try{await work}finally{if(reloadFlight===work)reloadFlight=null}
}
function mount(){const dest=document.querySelector('#view-q-admin[data-v307-ready="delegated"]')||document.querySelector('[data-v2124-admin-panel="predict"]');if(!dest||!window.v307CanPredict?.())return;let box=$('v21314CricketAdmin');if(!box){box=document.createElement('section');box.id='v21314CricketAdmin';box.className='pq-admin';dest.append(box);retryShell()}else if(box.parentElement!==dest)dest.append(box);return reload()}
window.v307LoadCricket=mount;
})();
