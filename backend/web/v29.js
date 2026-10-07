/* LEMMIQ V2.9 — Q Predict + passive analytics */
(()=>{
  const v29={home:null,category:"TRENDING",selected:null};
  const fmt=n=>new Intl.NumberFormat(undefined,{maximumFractionDigits:2}).format(Number(n||0));
  const esc=x=>escapeHtml(String(x??""));
  const when=x=>{try{return new Date(x).toLocaleString()}catch{return x||""}};
  async function pApi(path,opts={}){return api("/v29"+path,opts)}

  function marketCard(m){
    const result=m.result?`<span class="v29-result ${esc(m.result)}">${esc(m.result)}</span>`:"";
    const mine=(m.my_positions||[]).map(p=>`${p.outcome} ${fmt(p.stake_pc)} PC`).join(" · ");
    return `<article class="v29-market-card" data-v29-market="${m.id}">
      <div class="v29-market-meta"><span>${esc((m.category||"TRENDING").replace("TECH_AI","TECH & AI"))}</span>${result}<button class="v29-watch" data-v29-watch="${m.id}" title="Watch">${m.watched?"★":"☆"}</button></div>
      <h3>${esc(m.question)}</h3>
      <div class="v29-probability"><div><strong>${fmt(m.yes_percent)}%</strong><span>YES</span></div><div><strong>${fmt(m.no_percent)}%</strong><span>NO</span></div></div>
      <div class="v29-prob-bar"><span style="width:${Math.max(1,Math.min(99,Number(m.yes_percent||50)))}%"></span></div>
      <div class="v29-market-foot"><span>${fmt(m.pool_pc)} PC pool · ${m.participants||0} predictors</span><span>${m.status==="LIVE"?"Closes "+when(m.close_at):esc(m.status)}</span></div>
      ${mine?`<div class="v29-my-position">Your position · ${esc(mine)}</div>`:""}
    </article>`;
  }

  function render(){
    const h=v29.home;if(!h)return;
    $("v29PcBalance").textContent=`${fmt(h.wallet?.balance_pc)} PC`;
    $("v29PredictNotice").innerHTML=`<strong>Test mode</strong> · ${esc(h.notice||"")} · Simulated platform fee ${fmt(h.fee_percent)}% of winning profit.`;
    $("v29PredictCategories").innerHTML=(h.categories||[]).map(c=>`<button class="${v29.category===c?"active":""}" data-v29-category="${c}">${esc(c.replace("TECH_AI","Tech & AI").replace("TRENDING","Trending"))}</button>`).join("");
    const list=h.live||[];
    $("v29PredictMarkets").innerHTML=list.length?list.map(marketCard).join(""):`<div class="empty-state glass"><h3>No live markets yet</h3><p>Q Predict Agent drafts markets for Admin approval. Check back after the first drafts are published.</p></div>`;
    qsa("[data-v29-category]").forEach(b=>b.onclick=()=>{v29.category=b.dataset.v29Category;loadQPredict(v29.category)});
    qsa("[data-v29-market]").forEach(x=>x.onclick=e=>{if(e.target.closest("[data-v29-watch]"))return;openMarket(Number(x.dataset.v29Market))});
    qsa("[data-v29-watch]").forEach(b=>b.onclick=async e=>{e.stopPropagation();try{await pApi(`/predict/markets/${b.dataset.v29Watch}/watch`,{method:"POST",body:"{}"});await loadQPredict(v29.category)}catch(err){toast(err.message,true)}});
  }

  async function loadQPredict(category=v29.category){
    try{v29.home=await pApi(`/predict/home?category=${encodeURIComponent(category)}`);render()}catch(e){toast(e.message,true)}
  }
  window.loadQPredict=loadQPredict;

  async function openMarket(id){
    try{
      const m=await pApi(`/predict/markets/${id}`);v29.selected=m;
      const pos=(m.my_positions||[]).map(p=>`<div class="v29-position"><b>${esc(p.outcome)}</b><span>${fmt(p.stake_pc)} PC staked</span><span>${esc(p.status)}</span></div>`).join("");
      const comments=(m.discussion||[]).map(c=>`<div class="v29-comment"><b>${esc(c.user?.display_name||c.user?.username||"User")}</b><p>${esc(c.text)}</p><small>${when(c.created_at)}</small></div>`).join("");
      $("modalContent").innerHTML=`<div class="v29-market-detail">
        <div class="v29-detail-top"><span class="eyebrow">Q PREDICT · ${esc(m.category)}</span><button id="v29WatchDetail" class="ghost">${m.watched?"★ Watching":"☆ Watch"}</button></div>
        <h2>${esc(m.question)}</h2>
        <div class="v29-probability large"><div><strong>${fmt(m.yes_percent)}%</strong><span>YES</span></div><div><strong>${fmt(m.no_percent)}%</strong><span>NO</span></div></div>
        <div class="v29-market-foot"><span>${fmt(m.pool_pc)} PC pool · ${m.participants||0} predictors</span><span>Closes ${when(m.close_at)}</span></div>
        ${m.status==="LIVE"?`<div class="v29-stake-actions"><button id="v29PredictYes" class="v29-yes">Predict YES</button><button id="v29PredictNo" class="v29-no">Predict NO</button></div>`:""}
        <div class="v29-assistant-card"><div><b>Q market analysis</b><small>Open Q to research both sides before you predict.</small></div><button id="v29AskQMarket" class="primary">Ask Q</button></div>
        ${pos?`<h3>Your position</h3>${pos}`:""}
        <details class="v29-resolution"><summary>Resolution rules</summary><p>${esc(m.resolution_rule)}</p><small>Source: ${esc(m.resolution_source_name)} · ${esc(m.source_type)}</small>${m.resolution?`<p><b>Resolved ${esc(m.resolution.outcome)}</b> · ${esc(m.resolution.source_value)}</p>`:""}</details>
        <h3>Discussion · ${m.comments||0}</h3><div class="v29-comment-compose"><input id="v29CommentText" maxlength="1000" placeholder="Share your reasoning"><button id="v29PostComment" class="ghost">Post</button></div>
        <div class="v29-comments">${comments||'<p class="micro">No discussion yet.</p>'}</div>
      </div>`;
      $("modal").showModal();
      const stake=outcome=>{const amount=prompt(`Predict ${outcome} — amount in test Predict Credits`,`100`);if(amount===null)return;const n=Number(amount);if(!(n>0))return toast("Enter a valid Predict Credit amount",true);pApi(`/predict/markets/${id}/stake`,{method:"POST",body:JSON.stringify({outcome,amount_pc:n})}).then(async()=>{closeModal();toast(`Prediction placed: ${outcome} · ${fmt(n)} PC`);await loadQPredict(v29.category)}).catch(e=>toast(e.message,true))};
      if($("v29PredictYes"))$("v29PredictYes").onclick=()=>stake("YES");
      if($("v29PredictNo"))$("v29PredictNo").onclick=()=>stake("NO");
      $("v29WatchDetail").onclick=async()=>{await pApi(`/predict/markets/${id}/watch`,{method:"POST",body:"{}"});closeModal();await loadQPredict(v29.category)};
      $("v29AskQMarket").onclick=()=>{closeModal();setView("agent");const q=$("agentQuestion");if(q)q.value=`Analyse both sides of this Q Predict market: ${m.question} Resolution rule: ${m.resolution_rule}`};
      $("v29PostComment").onclick=async()=>{const text=$("v29CommentText").value.trim();if(!text)return;await pApi(`/predict/markets/${id}/comments`,{method:"POST",body:JSON.stringify({text})});closeModal();await openMarket(id)};
    }catch(e){toast(e.message,true)}
  }

  async function showMy(){
    try{const rows=await pApi("/predict/my");$("modalContent").innerHTML=`<span class="eyebrow">Q PREDICT</span><h2>My predictions</h2><div class="v29-review-list">${rows.length?rows.map(x=>`<button class="v29-mini-market" data-my-market="${x.market.id}"><b>${esc(x.outcome)} · ${fmt(x.stake_pc)} PC</b><span>${esc(x.market.question)}</span><small>${esc(x.status)}${x.payout_pc?` · payout ${fmt(x.payout_pc)} PC`:""}</small></button>`).join(""):'<p>No predictions yet.</p>'}</div>`;$("modal").showModal();qsa("[data-my-market]").forEach(b=>b.onclick=()=>{closeModal();openMarket(Number(b.dataset.myMarket))})}catch(e){toast(e.message,true)}
  }
  async function showLeaderboard(){
    try{const rows=await pApi("/predict/leaderboard");$("modalContent").innerHTML=`<span class="eyebrow">Q PREDICT</span><h2>Leaderboard</h2><div class="v29-leaderboard">${rows.length?rows.map(x=>`<div><b>#${x.rank}</b><span>${esc(x.user?.display_name||x.user?.username||"User")}</span><strong>${fmt(x.accuracy_percent)}%</strong><small>${fmt(x.net_won_pc)} PC net won</small></div>`).join(""):'<p>Leaderboard will appear after markets resolve.</p>'}</div>`;$("modal").showModal()}catch(e){toast(e.message,true)}
  }

  function stat(label,value){return `<div class="q28-stat"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`}
  async function loadV29Admin(){
    try{
      const period=$("v29AnalyticsPeriod")?.value||"7d";
      const [po,ops,mon,sim,pcfg]=await Promise.all([
        pApi(`/predict/admin/overview?period=${encodeURIComponent(period)}`),pApi(`/admin/operations?period=${encodeURIComponent(period)}`),pApi(`/admin/monetisation?period=${encodeURIComponent(period)}`),pApi("/admin/q-simulation"),pApi("/predict/admin/config")
      ]);
      $("v29PredictAdminStats").innerHTML=stat("Live",po.counts?.LIVE||0)+stat("Waiting approval",po.counts?.REVIEW||0)+stat("Predictors",po.active_predictors||0)+stat("Volume",`${fmt(po.volume_pc)} PC`)+stat("Test treasury",`${fmt(po.test_treasury_pc)} PC`);
      $("v29PredictAutomation").innerHTML=[
        ["discovery_enabled","Trend discovery",pcfg.discovery_enabled],
        ["auto_drafting","Auto drafting",pcfg.auto_drafting],
        ["auto_publish","Auto publish",pcfg.auto_publish],
        ["auto_settlement","Auto settlement",pcfg.auto_settlement]
      ].map(([k,l,v])=>`<label class="v29-auto-toggle"><input type="checkbox" data-v29-config="${k}" ${v?"checked":""}><span>${l}</span></label>`).join("")+`<span class="v29-mode-banner">REAL Q: OFF</span>`;
      qsa("[data-v29-config]").forEach(el=>el.onchange=async()=>{try{const body={};body[el.dataset.v29Config]=el.checked;await pApi("/predict/admin/config",{method:"PUT",body:JSON.stringify(body)});toast("Q Predict automation updated")}catch(e){el.checked=!el.checked;toast(e.message,true)}});
      $("v29OperationsStats").innerHTML=stat("New users",ops.new_users)+stat("New packages",ops.new_packages)+stat("Approved USDT",`US$${fmt(ops.approved_usdt)}`)+stat("Q ledger events",ops.q_ledger_events)+stat("Q Market orders",ops.q_market_orders)+stat("Referrals",ops.new_referrals);
      $("v29MonetisationStats").innerHTML=`<div class="v29-analysis-kpis"><b>${mon.requests||0}</b><span>AI actions tracked</span><b>US$${fmt(mon.estimated_ai_cost_usd)}</b><span>Estimated provider cost</span><b>${fmt(mon.simulated_q_fees)} Q</b><span>Would-be Q fees</span></div><div class="v29-feature-lines">${(mon.features||[]).map(x=>`<div><span>${esc(x.feature)}</span><b>${x.requests} uses · ${fmt(x.simulated_q)} Q</b></div>`).join("")}</div>`;
      const c=sim.current||{};$("v29QSimulation").innerHTML=`<div class="v29-price-compare"><div><small>Actual</small><strong>US$${Number(c.actual_price_usd||.05).toFixed(4)}</strong><span>Fixed</span></div><div><small>Simulated</small><strong>US$${Number(c.simulated_price_usd||.05).toFixed(4)}</strong><span>${Number(c.applied_change_percent||0)>=0?"+":""}${fmt(c.applied_change_percent)}%</span></div></div><p class="micro">Demand score ${fmt(c.demand_score)} · supply score ${fmt(c.supply_score)} · ±5% weekly simulation cap.</p>`;
      await loadReview(false);
    }catch(e){console.warn("V2.9 admin analytics",e)}
  }
  window.loadV29Admin=loadV29Admin;

  async function createManualMarket(){
    const closeDefault=new Date(Date.now()+24*3600*1000).toISOString().slice(0,16);
    $("modalContent").innerHTML=`<span class="eyebrow">Q PREDICT ADMIN</span><h2>Create test market</h2><p class="micro">Manual markets start in review. Use an objective rule/source. Predict Credits only.</p><div class="v29-manual-grid">
      <label class="full">Question<input id="v29NewQuestion" maxlength="260" placeholder="Will … ?"></label>
      <label>Category<select id="v29NewCategory"><option>ECONOMY</option><option>CRYPTO</option><option>TECH_AI</option><option>SPORTS</option><option>ENTERTAINMENT</option><option>WEATHER</option><option>LEMMIQ</option></select></label>
      <label>Close / resolve at<input id="v29NewClose" type="datetime-local" value="${closeDefault}"></label>
      <label class="full">Resolution source<input id="v29NewSource" placeholder="e.g. Reserve Bank of Australia"></label>
      <label class="full">Resolution rule<textarea id="v29NewRule" rows="3" placeholder="YES if …; otherwise NO."></textarea></label>
    </div><div class="dialog-actions"><button id="v29CreateCancel" class="ghost">Cancel</button><button id="v29CreateSave" class="primary">Create draft</button></div>`;
    $("modal").showModal();
    $("v29CreateCancel").onclick=closeModal;
    $("v29CreateSave").onclick=async()=>{
      const question=$("v29NewQuestion").value.trim(),rule=$("v29NewRule").value.trim(),source=$("v29NewSource").value.trim(),raw=$("v29NewClose").value;
      if(!question||!rule||!source||!raw)return toast("Question, source, rule and deadline are required",true);
      try{
        const iso=new Date(raw).toISOString();
        await pApi("/predict/admin/markets",{method:"POST",body:JSON.stringify({question,category:$("v29NewCategory").value,template_code:"MANUAL",close_at:iso,resolve_after:iso,resolution_source_name:source,resolution_source_url:"",resolution_rule:rule,source_type:"MANUAL",source_config:{},trend_score:50,resolution_confidence:80,auto_resolve:false})});
        closeModal();toast("Q Predict draft created");await loadV29Admin();await loadReview(true);
      }catch(e){toast(e.message,true)}
    };
  }

  async function loadReview(showAll=true){
    try{const rows=await pApi("/predict/admin/markets?status=REVIEW");$("v29PredictReview").innerHTML=rows.slice(0,showAll?100:6).map(m=>`<div class="v29-review-row"><div><b>${esc(m.question)}</b><small>${esc(m.category)} · closes ${when(m.close_at)} · ${esc(m.resolution_source_name)}</small></div><div><button class="primary" data-v29-publish="${m.id}">Approve</button><button class="ghost" data-v29-void="${m.id}">Reject</button></div></div>`).join("")||'<p class="micro">No market drafts waiting for approval.</p>';qsa("[data-v29-publish]").forEach(b=>b.onclick=async()=>{await pApi(`/predict/admin/markets/${b.dataset.v29Publish}/publish`,{method:"POST",body:"{}"});toast("Q Predict market published");loadV29Admin()});qsa("[data-v29-void]").forEach(b=>b.onclick=async()=>{if(!confirm("Reject/void this draft?"))return;await pApi(`/predict/admin/markets/${b.dataset.v29Void}/void`,{method:"POST",body:"{}"});toast("Draft removed from queue");loadV29Admin()})}catch(e){console.warn(e)}
  }

  document.addEventListener("DOMContentLoaded",()=>{
    if($("v29MyPredictionsBtn"))$("v29MyPredictionsBtn").onclick=showMy;
    if($("v29CreatePredictMarket"))$("v29CreatePredictMarket").onclick=createManualMarket;
    if($("v29LeaderboardBtn"))$("v29LeaderboardBtn").onclick=showLeaderboard;
    if($("v29RunPredictAgent"))$("v29RunPredictAgent").onclick=async()=>{try{const r=await pApi("/predict/admin/agent/run",{method:"POST",body:"{}"});toast(`${r.created||0} Q Predict draft(s) generated`);loadV29Admin()}catch(e){toast(e.message,true)}};
    if($("v29SettlePredictDue"))$("v29SettlePredictDue").onclick=async()=>{try{const r=await pApi("/predict/admin/settle-due",{method:"POST",body:"{}"});toast(`Closed ${r.closed||0} · resolved ${r.resolved||0}`);loadV29Admin()}catch(e){toast(e.message,true)}};
    if($("v29OpenPredictReview"))$("v29OpenPredictReview").onclick=()=>loadReview(true);
    if($("v29AnalyticsPeriod"))$("v29AnalyticsPeriod").onchange=loadV29Admin;
  });
})();
