/* LEMMIQ V2.10.7.4 — Q Economy Engine UI
   Extension-only: preserves stable v28.js / v29.js. */
(()=>{
  const LEVEL={NONE:0,READ:1,WRITE:2,FULL:3};
  const previousLoadQEconomy=window.loadQEconomy;
  const previousLoadQAdmin=window.loadQAdmin;
  let adminAccess=null, withdrawalConfig=null, rebuyOptions=null;

  const byId=id=>document.getElementById(id);
  const esc=x=>escapeHtml(String(x??""));
  const num=(x,d=6)=>Number(x||0).toLocaleString(undefined,{maximumFractionDigits:d});
  const usd=(x,d=2)=>`US$${Number(x||0).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:6})}`;
  const q=(x,d=6)=>`${num(x,d)} Q`;
  const dt=x=>{try{return x?new Date(x).toLocaleString():"—"}catch{return "—"}};
  const stat=(label,value)=>`<div class="q28-stat"><small>${esc(label)}</small><strong>${value}</strong></div>`;

  function ensureQrLightbox(){
    if(byId("q21074QrLightbox"))return;
    const node=document.createElement("div");
    node.id="q21074QrLightbox";
    node.className="q21074-qr-lightbox hidden";
    node.innerHTML=`<button class="q21074-qr-close" aria-label="Close enlarged QR">×</button><div class="q21074-qr-stage"><img alt="Enlarged wallet QR"><p>Tap × or outside the QR to close</p></div>`;
    document.body.appendChild(node);
    const close=()=>node.classList.add("hidden");
    node.querySelector(".q21074-qr-close").onclick=close;
    node.addEventListener("click",ev=>{if(ev.target===node)close()});
    document.addEventListener("keydown",ev=>{if(ev.key==="Escape"&&!node.classList.contains("hidden"))close()});
  }

  function installQrEnlarge(){
    ensureQrLightbox();
    if(document.body.dataset.q21074QrHandler)return;
    document.body.dataset.q21074QrHandler="1";
    document.addEventListener("click",ev=>{
      const img=ev.target?.closest?.("#modalContent img");
      if(!img)return;
      const src=img.getAttribute("src")||"";
      const modalText=byId("modalContent")?.textContent||"";
      const isWalletQr=src.includes("/payment-wallets/")&&src.includes("/qr");
      const saysQr=/QR\s+to\s+enlarge/i.test(modalText)||/wallet address/i.test(modalText);
      if(!isWalletQr&&!saysQr)return;
      ev.preventDefault();ev.stopPropagation();
      const box=byId("q21074QrLightbox");
      box.querySelector("img").src=src;
      box.classList.remove("hidden");
    },true);
  }

  function ensureEconomyCards(){
    const walletTab=byId("q28Tab-wallet"), packageTab=byId("q28Tab-packages");
    if(walletTab&&!byId("q21074WithdrawCard")){
      const wrap=document.createElement("div");
      wrap.innerHTML=`<div class="grid two q21074-economy-grid">
        <article class="card glass" id="q21074WeeklyCard"><div class="section-head"><div><span class="eyebrow">ACTIVE Q</span><h3>Weekly active reward</h3></div><button id="q21074WeeklyClaim" class="primary hidden">Claim</button></div><p id="q21074WeeklyInfo" class="micro">Loading…</p></article>
        <article class="card glass" id="q21074WithdrawCard"><div class="section-head"><div><span class="eyebrow">Q → USDT</span><h3>Withdraw Q</h3></div><span id="q21074WithdrawState" class="q21074-pill">—</span></div>
          <p id="q21074WithdrawInfo" class="micro">Loading withdrawal settings…</p>
          <div id="q21074WithdrawForm" class="q21074-form hidden">
            <label>Q to withdraw<input id="q21074WithdrawAmount" type="number" min="0.000001" step="0.01" placeholder="Q amount"></label>
            <div class="q21074-inline"><select id="q21074WithdrawNetwork"><option>TRC20</option><option>BEP20</option></select><input id="q21074WithdrawAddress" placeholder="Destination USDT wallet address"></div>
            <div id="q21074WithdrawQuote" class="q21074-quote"></div>
            <button id="q21074WithdrawSubmit" class="primary full">Request withdrawal</button>
          </div>
          <div id="q21074WithdrawalHistory" class="q21074-mini-list"></div>
        </article>
      </div>`;
      walletTab.insertBefore(wrap.firstElementChild,walletTab.firstElementChild?.nextSibling||null);
    }
    if(packageTab&&!byId("q21074CycleCard")){
      const wrap=document.createElement("div");
      wrap.innerHTML=`<article class="card glass" id="q21074CycleCard"><div class="section-head"><div><span class="eyebrow">200% EARNING CAP</span><h3>Package earning cycles</h3><p class="micro">Package accrual, active rewards, referrals and qualifying bonuses count toward the cycle.</p></div><button id="q21074RefreshCycles" class="ghost">↻</button></div><div id="q21074Cycles" class="q21074-cycle-list"></div></article>
        <article class="card glass" id="q21074RebuyCard"><div class="section-head"><div><span class="eyebrow">REBUY / UPGRADE</span><h3>Use Q + USDT</h3><p class="micro">Completed package cycles remain in history. A rebuy or upgrade creates a new earning cycle.</p></div></div><div id="q21074RebuyBody"><p class="micro">Loading…</p></div><div id="q21074RebuyHistory" class="q21074-mini-list"></div></article>`;
      const nodes=[...wrap.children];
      const subs=byId("q28Subscriptions")?.closest("article");
      const anchor=subs||packageTab.firstElementChild?.nextSibling||null;
      nodes.forEach(n=>packageTab.insertBefore(n,anchor));
    }
  }

  function renderCycles(data){
    const host=byId("q21074Cycles");if(!host)return;
    const cycles=data.cycles||[];
    if(!cycles.length){host.innerHTML='<p class="micro">No package earning cycle yet.</p>';return}
    host.innerHTML=cycles.slice(0,8).map(c=>{
      const cap=Number(c.earning_cap_usd||c.cap_usd||0),used=Number(c.earning_cap_used_usd||c.accrued_usd||0);
      const pct=cap?Math.min(100,(used/cap)*100):0;
      const breakdown=c.earning_cap_breakdown||{};
      const chips=Object.entries(breakdown).map(([k,v])=>`<span>${esc(k.replaceAll("_"," "))}: ${usd(v.usd_reference||0)}</span>`).join("");
      return `<div class="q21074-cycle"><div class="q21074-cycle-head"><div><strong>${esc(c.package_name||c.package_code||"Package")}</strong><small>${esc(c.status||"")}</small></div><b>${num(pct,1)}%</b></div><div class="q21074-progress"><span style="width:${pct}%"></span></div><div class="q21074-cycle-numbers"><span>${usd(used)} used</span><span>${usd(cap)} ceiling</span><span>${usd(c.earning_cap_remaining_usd||0)} remaining</span></div><div class="q21074-chips">${chips||'<span>No qualifying rewards yet</span>'}</div></div>`;
    }).join("") + (Number(data.unassigned_rewards_q||0)>0?`<div class="q21074-notice">Qualifying rewards waiting for the next earning cycle: <strong>${q(data.unassigned_rewards_q)}</strong> (${usd(data.unassigned_rewards_usd_reference||0)} reference)</div>`:"");
  }

  async function loadCycles(){
    try{renderCycles(await api("/v21074/earning-cycles"))}catch(err){if(byId("q21074Cycles"))byId("q21074Cycles").innerHTML=`<p class="micro">${esc(err.message||err)}</p>`}
  }

  async function loadWeekly(){
    const info=byId("q21074WeeklyInfo"),btn=byId("q21074WeeklyClaim");if(!info||!btn)return;
    try{
      const d=await api("/v21074/weekly-active");
      btn.classList.toggle("hidden",!d.enabled||d.claimed);
      btn.disabled=!!d.claimed;
      info.textContent=!d.enabled?"Weekly active Q is currently 0 Q.":d.claimed?`${d.weekly_q} Q already claimed for ${d.week_key}.`:`${d.weekly_q} Q available for ${d.week_key}. This qualifying reward counts toward an active package earning cap.`;
      btn.onclick=async()=>{try{btn.disabled=true;await api("/v21074/weekly-active/claim",{method:"POST",body:"{}"});toast("Weekly active Q claimed");await refreshEconomy()}catch(e){toast(e.message,true);btn.disabled=false}};
    }catch(err){info.textContent=err.message||String(err)}
  }

  function withdrawalQuote(){
    if(!withdrawalConfig)return;
    const amount=Number(byId("q21074WithdrawAmount")?.value||0),feePct=Number(withdrawalConfig.fee_percent||10);
    const fee=amount*feePct/100,net=Math.max(0,amount-fee),payout=net*Number(withdrawalConfig.q_reference_usd||0);
    const host=byId("q21074WithdrawQuote");if(!host)return;
    host.innerHTML=`<span>Requested <strong>${q(amount)}</strong></span><span>Fee ${num(feePct,2)}%: <strong>${q(fee)}</strong></span><span>Net Q: <strong>${q(net)}</strong></span><span>Estimated payout: <strong>${usd(payout)}</strong></span>`;
  }

  async function loadWithdrawal(){
    const card=byId("q21074WithdrawCard");if(!card)return;
    try{
      withdrawalConfig=await api("/v21074/withdrawals/config");
      const stateEl=byId("q21074WithdrawState"),info=byId("q21074WithdrawInfo"),form=byId("q21074WithdrawForm");
      stateEl.textContent=withdrawalConfig.enabled?"ON":"OFF";stateEl.classList.toggle("active",withdrawalConfig.enabled);
      form.classList.toggle("hidden",!withdrawalConfig.enabled);
      info.textContent=withdrawalConfig.enabled
        ?`10% fee is deducted in Q. Minimum final payout is ${withdrawalConfig.minimum_net_usdt} USDT. Current reference: 1 Q = ${usd(withdrawalConfig.q_reference_usd,4)}. Minimum gross at this reference ≈ ${num(withdrawalConfig.minimum_gross_q_at_current_reference)} Q.`
        :"Q withdrawal is currently turned off by LEMMIQ Admin.";
      const amount=byId("q21074WithdrawAmount");if(amount){amount.oninput=withdrawalQuote;amount.max=withdrawalConfig.wallet_balance_q;amount.placeholder=`Up to ${num(withdrawalConfig.wallet_balance_q)} Q`}
      withdrawalQuote();
      const submit=byId("q21074WithdrawSubmit");if(submit)submit.onclick=async()=>{
        const body={amount_q:Number(amount.value||0),network:byId("q21074WithdrawNetwork").value,destination_address:byId("q21074WithdrawAddress").value.trim()};
        if(!body.amount_q||!body.destination_address)return toast("Enter Q amount and destination wallet",true);
        submit.disabled=true;submit.textContent="Submitting…";
        try{const out=await api("/v21074/withdrawals",{method:"POST",body:JSON.stringify(body)});toast(`Withdrawal ${out.request_id} submitted`);amount.value="";byId("q21074WithdrawAddress").value="";await refreshEconomy()}catch(e){toast(e.message,true)}finally{submit.disabled=false;submit.textContent="Request withdrawal"}
      };
      await loadMyWithdrawals();
    }catch(err){byId("q21074WithdrawInfo").textContent=err.message||String(err)}
  }

  async function loadMyWithdrawals(){
    const host=byId("q21074WithdrawalHistory");if(!host)return;
    try{
      const rows=await api("/v21074/withdrawals");
      host.innerHTML=rows.length?`<h4>Recent withdrawals</h4>${rows.slice(0,5).map(x=>`<div class="q21074-mini-row"><div><strong>${esc(x.request_id)}</strong><small>${q(x.requested_q)} → ${num(x.payout_usdt)} USDT · ${esc(x.network)} · ${dt(x.requested_at)}</small></div><span class="q21074-status ${esc(x.status.toLowerCase())}">${esc(x.status)}</span>${x.status==="PENDING"?`<button class="ghost" data-q21074-cancel-withdraw="${x.id}">Cancel</button>`:""}</div>`).join("")}`:"";
      host.querySelectorAll("[data-q21074-cancel-withdraw]").forEach(btn=>btn.onclick=async()=>{if(!confirm("Cancel this pending withdrawal and release the locked Q?"))return;try{await api(`/v21074/withdrawals/${btn.dataset.q21074CancelWithdraw}/cancel`,{method:"POST",body:"{}"});toast("Withdrawal cancelled; Q released");await refreshEconomy()}catch(e){toast(e.message,true)}});
    }catch(err){host.innerHTML=`<p class="micro">${esc(err.message||err)}</p>`}
  }

  function renderRebuyForm(d){
    rebuyOptions=d;const host=byId("q21074RebuyBody");if(!host)return;
    if(!d.enabled){host.innerHTML='<p class="micro">Q + USDT rebuy is currently disabled.</p>';return}
    if(d.blocked_by_active_cycle){host.innerHTML='<p class="micro">Your current package earning cycle is still active. Rebuy/upgrade becomes available after the cycle is completed or expired.</p>';return}
    if(!d.can_rebuy||!(d.plans||[]).length){host.innerHTML='<p class="micro">A completed or expired package is required before Q + USDT rebuy/upgrade.</p>';return}
    host.innerHTML=`<div class="q21074-form"><div class="q21074-inline"><label>Package<select id="q21074RebuyPlan">${d.plans.map((p,i)=>`<option value="${esc(p.package_code)}" ${i===0?"selected":""}>${esc(p.action)} · ${esc(p.name)} · US$${num(p.price_usd,0)}</option>`).join("")}</select></label><label>Network<select id="q21074RebuyNetwork">${d.networks.map(n=>`<option>${esc(n)}</option>`).join("")}</select></label></div><label>Q to use<input id="q21074RebuyQ" type="number" min="0.000001" step="0.01" placeholder="Q amount"></label><div id="q21074RebuyQuote" class="q21074-quote"></div><div class="q21074-inline"><button id="q21074RebuyMax" class="ghost">Use maximum Q</button><button id="q21074RebuySubmit" class="primary">Create Q + USDT order</button></div></div>`;
    const calc=()=>{
      const plan=d.plans.find(p=>p.package_code===byId("q21074RebuyPlan").value)||d.plans[0];
      const maxQ=Math.min(Number(plan.max_q_at_current_reference||0),Number(d.wallet_balance_q||0));
      const entered=Math.max(0,Number(byId("q21074RebuyQ").value||0));
      const qUsed=Math.min(entered,maxQ),qValue=qUsed*Number(d.q_reference_usd||0),due=Math.max(0,Number(plan.price_usd)-qValue);
      byId("q21074RebuyQ").max=maxQ;
      byId("q21074RebuyQuote").innerHTML=`<span>Max Q: <strong>${q(maxQ)}</strong> (${num(plan.max_q_percent,0)}%)</span><span>Q value: <strong>${usd(qValue)}</strong></span><span>USDT due: <strong>${num(due)} USDT</strong></span><span>New earning ceiling: <strong>${usd(Number(plan.price_usd)*2)}</strong></span>`;
      return {plan,maxQ,qUsed,due};
    };
    byId("q21074RebuyPlan").onchange=calc;byId("q21074RebuyQ").oninput=calc;
    byId("q21074RebuyMax").onclick=()=>{const c=calc();byId("q21074RebuyQ").value=c.maxQ;calc()};
    byId("q21074RebuySubmit").onclick=async()=>{const c=calc();if(!c.qUsed)return toast("Enter Q amount to use",true);const btn=byId("q21074RebuySubmit");btn.disabled=true;btn.textContent="Creating…";try{const out=await api("/v21074/packages/rebuy/orders",{method:"POST",body:JSON.stringify({target_package_code:c.plan.package_code,network:byId("q21074RebuyNetwork").value,q_amount:c.qUsed})});toast(`${out.action} order created — submit the USDT transaction in Payment Orders`);await refreshEconomy()}catch(e){toast(e.message,true)}finally{btn.disabled=false;btn.textContent="Create Q + USDT order"}};
    calc();
  }

  async function loadRebuy(){
    try{
      const [options,orders]=await Promise.all([api("/v21074/packages/rebuy/options"),api("/v21074/packages/rebuy/orders")]);
      renderRebuyForm(options);
      const host=byId("q21074RebuyHistory");
      if(host)host.innerHTML=orders.length?`<h4>Q + USDT orders</h4>${orders.slice(0,5).map(x=>`<div class="q21074-mini-row"><div><strong>${esc(x.action)} · ${esc(x.target_package_name)}</strong><small>${q(x.q_locked)} + ${num(x.usdt_due)} USDT · ${esc(x.status)} · ${dt(x.created_at)}</small></div>${["CREATED","PENDING"].includes(x.status)&&x.payment?.status!=="PENDING"?`<button class="ghost" data-q21074-cancel-rebuy="${x.id}">Cancel</button>`:""}</div>`).join("")}`:"";
      host?.querySelectorAll("[data-q21074-cancel-rebuy]").forEach(btn=>btn.onclick=async()=>{if(!confirm("Cancel this Q + USDT order and release locked Q?"))return;try{await api(`/v21074/packages/rebuy/orders/${btn.dataset.q21074CancelRebuy}/cancel`,{method:"POST",body:"{}"});toast("Rebuy order cancelled; Q released");await refreshEconomy()}catch(e){toast(e.message,true)}});
    }catch(err){if(byId("q21074RebuyBody"))byId("q21074RebuyBody").innerHTML=`<p class="micro">${esc(err.message||err)}</p>`}
  }

  async function load21074Economy(){ensureEconomyCards();installQrEnlarge();await Promise.all([loadCycles(),loadWeekly(),loadWithdrawal(),loadRebuy()])}
  async function refreshEconomy(){if(previousLoadQEconomy)await previousLoadQEconomy();await load21074Economy()}

  // ---------- Admin ----------
  async function getAdminAccess(){return adminAccess=await api("/v28/admin/access/me")}
  const has=(section,level="READ")=>LEVEL[adminAccess?.permissions?.[section]||"NONE"]>=LEVEL[level];

  function ensureAdminCards(){
    const view=byId("view-q-admin");if(!view)return;
    if(!byId("q21074FeaturePricingCard")){
      const card=document.createElement("article");card.className="card glass";card.id="q21074FeaturePricingCard";
      card.innerHTML=`<div class="section-head"><div><span class="eyebrow">GLOBAL AI Q PRICING</span><h3>AI feature Q charges</h3><p class="micro">One global Q price per feature — the same for every subscription package.</p></div><label class="q21074-switch"><input id="q21074ChargingSwitch" type="checkbox"><span></span><b id="q21074ChargingText">OFF</b></label></div><div id="q21074FeaturePrices" class="q21074-price-grid"></div>`;
      const usage=byId("q21072UsageCard"); if(usage?.parentElement===view)view.insertBefore(card,usage);else view.appendChild(card);
    }
    if(!byId("q21074AdminEconomyCard")){
      const card=document.createElement("article");card.className="card glass";card.id="q21074AdminEconomyCard";
      card.innerHTML=`<div class="section-head"><div><span class="eyebrow">EARNING & REBUY</span><h3>Package economy controls</h3><p class="micro">Controls new-cycle rebuy/upgrade limits and optional weekly active reward.</p></div></div><div id="q21074AdminEconomyControls" class="q21074-admin-controls"></div>`;
      const rules=byId("q28PackageMasterRules")?.closest("article"); if(rules?.parentElement===view)view.insertBefore(card,rules);else view.appendChild(card);
    }
    if(!byId("q21074WithdrawAdminCard")){
      const card=document.createElement("article");card.className="card glass";card.id="q21074WithdrawAdminCard";
      card.innerHTML=`<div class="section-head"><div><span class="eyebrow">PAYMENTS / USDT</span><h3>Q → USDT Withdrawals</h3><p class="micro">Manual payout workflow. The global withdrawal switch is OFF by default.</p></div><label class="q21074-switch"><input id="q21074AdminWithdrawSwitch" type="checkbox"><span></span><b id="q21074AdminWithdrawSwitchText">OFF</b></label></div><div id="q21074WithdrawalStats" class="q28-admin-stats"></div><div class="q21074-admin-filters"><select id="q21074AdminPeriod"><option value="TODAY">Today</option><option value="WEEK">Week</option><option value="MONTH">Month</option><option value="YEAR">Year</option><option value="ALL" selected>All</option></select><select id="q21074AdminStatus"><option value="">All statuses</option><option>PENDING</option><option>APPROVED</option><option>PAID</option><option>REJECTED</option><option>FAILED</option><option>CANCELLED</option></select><select id="q21074AdminNetwork"><option value="">All networks</option><option>TRC20</option><option>BEP20</option></select><input id="q21074AdminUser" placeholder="@username"><button id="q21074AdminFilterBtn" class="ghost">Filter</button><button id="q21074AdminExportBtn" class="ghost">Export CSV</button></div><div id="q21074AdminWithdrawals" class="q21074-withdraw-list"></div>`;
      const pending=byId("q28AdminPayments")?.closest("article"); if(pending?.parentElement===view)view.insertBefore(card,pending);else view.appendChild(card);
    }
  }

  async function loadFeaturePricing(){
    const card=byId("q21074FeaturePricingCard");if(!card)return;
    if(!has("Q_FEATURE_PRICING","READ")){card.classList.add("hidden");return} card.classList.remove("hidden");
    try{
      const d=await api("/v2105/admin/q-features"),canFull=has("Q_FEATURE_PRICING","FULL");
      const sw=byId("q21074ChargingSwitch");sw.checked=!!d.charging_enabled;sw.disabled=!canFull;byId("q21074ChargingText").textContent=d.charging_enabled?"ON":"OFF";
      sw.onchange=async()=>{const desired=sw.checked;sw.disabled=true;try{await api("/v2105/admin/q-features/settings",{method:"PUT",body:JSON.stringify({charging_enabled:desired})});toast(`AI Q charging ${desired?"ON":"OFF"}`);await loadFeaturePricing()}catch(e){sw.checked=!desired;toast(e.message,true)}finally{sw.disabled=!canFull}};
      byId("q21074FeaturePrices").innerHTML=(d.features||[]).map(f=>`<div class="q21074-price-row" data-feature="${esc(f.feature_key)}"><div><strong>${esc(f.feature_name)}</strong><small>${esc(f.feature_key)}</small></div><input type="number" min="0" step="0.01" value="${esc(f.q_cost)}" ${canFull?"":"disabled"}><label><input type="checkbox" data-enabled ${f.enabled?"checked":""} ${canFull?"":"disabled"}> Enabled</label>${canFull?'<button class="ghost" data-save>Save</button>':''}</div>`).join("");
      byId("q21074FeaturePrices").querySelectorAll("[data-save]").forEach(btn=>btn.onclick=async()=>{const row=btn.closest("[data-feature]"),key=row.dataset.feature,qCost=Number(row.querySelector('input[type="number"]').value||0),enabled=row.querySelector("[data-enabled]").checked;btn.disabled=true;try{await api(`/v2105/admin/q-features/${encodeURIComponent(key)}`,{method:"PUT",body:JSON.stringify({q_cost:qCost,enabled})});toast(`${key} global price saved`)}catch(e){toast(e.message,true)}finally{btn.disabled=false}});
    }catch(err){byId("q21074FeaturePrices").innerHTML=`<p class="micro">${esc(err.message||err)}</p>`}
  }

  async function loadAdminEconomyControls(){
    const card=byId("q21074AdminEconomyCard");if(!card)return;
    if(!has("PACKAGES_REFERRALS","READ")){card.classList.add("hidden");return}card.classList.remove("hidden");
    try{
      const d=await api("/v21074/admin/economy-controls"),canFull=has("PACKAGES_REFERRALS","FULL");
      byId("q21074AdminEconomyControls").innerHTML=`<label class="q21074-control-check"><input id="q21074RebuyEnabledAdmin" type="checkbox" ${d.rebuy_enabled?"checked":""} ${canFull?"":"disabled"}> Q + USDT rebuy/upgrade enabled</label><label>Same-package rebuy: max Q %<input id="q21074RebuyPercentAdmin" type="number" min="0" max="95" step="1" value="${esc(d.rebuy_same_max_percent)}" ${canFull?"":"disabled"}></label><label>Upgrade: max Q %<input id="q21074UpgradePercentAdmin" type="number" min="0" max="95" step="1" value="${esc(d.upgrade_max_percent)}" ${canFull?"":"disabled"}></label><label>Weekly active reward Q<input id="q21074WeeklyAdmin" type="number" min="0" step="0.01" value="${esc(d.weekly_active_q)}" ${canFull?"":"disabled"}></label>${canFull?'<button id="q21074EconomySave" class="primary">Save economy controls</button>':''}`;
      if(canFull)byId("q21074EconomySave").onclick=async()=>{const btn=byId("q21074EconomySave");btn.disabled=true;try{await api("/v21074/admin/economy-controls",{method:"PUT",body:JSON.stringify({rebuy_enabled:byId("q21074RebuyEnabledAdmin").checked,rebuy_same_max_percent:Number(byId("q21074RebuyPercentAdmin").value),upgrade_max_percent:Number(byId("q21074UpgradePercentAdmin").value),weekly_active_q:Number(byId("q21074WeeklyAdmin").value)})});toast("Package economy controls saved")}catch(e){toast(e.message,true)}finally{btn.disabled=false}};
    }catch(err){byId("q21074AdminEconomyControls").innerHTML=`<p class="micro">${esc(err.message||err)}</p>`}
  }

  function adminWithdrawalQs(){const p=new URLSearchParams({period:byId("q21074AdminPeriod")?.value||"ALL"}),s=byId("q21074AdminStatus")?.value,n=byId("q21074AdminNetwork")?.value,u=byId("q21074AdminUser")?.value.trim();if(s)p.set("status",s);if(n)p.set("network",n);if(u)p.set("username",u);return p.toString()}

  function withdrawalDetails(x){
    openModal(`<span class="eyebrow">OUTGOING USDT</span><h2>${esc(x.request_id)}</h2><div class="q21074-detail-grid">${stat("User",`@${esc(x.user?.username||"")}`)}${stat("Requested",q(x.requested_q))}${stat("10% fee",q(x.fee_q))}${stat("Net Q",q(x.net_q))}${stat("Locked Q rate",usd(x.q_reference_usd,4))}${stat("USDT payout",`${num(x.payout_usdt)} USDT`)}${stat("Network",esc(x.network))}${stat("Status",esc(x.status))}</div><h4>Destination wallet</h4><div class="q21074-address">${esc(x.destination_address)}</div><p class="micro">Requested: ${dt(x.requested_at)}<br>Reviewer: ${esc(x.reviewer?.username||"—")} · ${dt(x.reviewed_at)}<br>TX: ${esc(x.tx_hash||"—")}<br>Note: ${esc(x.admin_note||"—")}</p><button id="q21074DetailClose" class="ghost full">Close</button>`);byId("q21074DetailClose").onclick=closeModal;
  }

  async function withdrawalAction(id,action){
    try{
      if(action==="approve")await api(`/v21074/admin/withdrawals/${id}/approve`,{method:"POST",body:"{}"});
      else if(action==="reject"){const note=prompt("Reason for rejection")||"Rejected by Admin";await api(`/v21074/admin/withdrawals/${id}/reject`,{method:"POST",body:JSON.stringify({note})})}
      else if(action==="failed"){const note=prompt("Reason / payout failure note")||"USDT payout failed";await api(`/v21074/admin/withdrawals/${id}/failed`,{method:"POST",body:JSON.stringify({note})})}
      else if(action==="paid"){const tx=prompt("USDT transaction hash");if(!tx)return;const note=prompt("Optional note")||"";await api(`/v21074/admin/withdrawals/${id}/mark-paid`,{method:"POST",body:JSON.stringify({tx_hash:tx.trim(),note})})}
      toast(`Withdrawal ${action} updated`);await loadAdminWithdrawals();
    }catch(e){toast(e.message,true)}
  }

  async function loadAdminWithdrawals(){
    const card=byId("q21074WithdrawAdminCard");if(!card)return;
    if(!has("PAYMENTS","READ")){card.classList.add("hidden");return}card.classList.remove("hidden");
    const canWrite=has("PAYMENTS","WRITE"),canFull=has("PAYMENTS","FULL");
    try{
      const [settings,summary,rows]=await Promise.all([api("/v21074/admin/withdrawals/settings"),api(`/v21074/admin/withdrawals/summary?${adminWithdrawalQs()}`),api(`/v21074/admin/withdrawals?${adminWithdrawalQs()}`)]);
      const sw=byId("q21074AdminWithdrawSwitch");sw.checked=!!settings.withdrawal_enabled;sw.disabled=!canFull;byId("q21074AdminWithdrawSwitchText").textContent=settings.withdrawal_enabled?"ON":"OFF";
      sw.onchange=async()=>{const desired=sw.checked;sw.disabled=true;try{await api("/v21074/admin/withdrawals/settings",{method:"PUT",body:JSON.stringify({enabled:desired})});toast(`Q withdrawal ${desired?"ON":"OFF"}`);await loadAdminWithdrawals()}catch(e){sw.checked=!desired;toast(e.message,true)}finally{sw.disabled=!canFull}};
      byId("q21074WithdrawalStats").innerHTML=[stat("Pending Requests",num(summary.pending_requests,0)),stat("Pending USDT",`${num(summary.pending_usdt_value)} USDT`),stat("Paid Today",`${num(summary.paid_today_usdt)} USDT`),stat("Fees Collected",q(summary.fees_collected_q)),stat("Rejected / Failed",num(summary.rejected_failed,0)),stat("USDT Sent",`${num(summary.usdt_sent)} USDT`)].join("");
      byId("q21074AdminWithdrawals").innerHTML=rows.length?rows.map((x,i)=>`<div class="q21074-withdraw-row" data-index="${i}"><div class="q21074-withdraw-main"><div><strong>${esc(x.request_id)} · @${esc(x.user?.username||"")}</strong><small>${q(x.requested_q)} gross · ${q(x.fee_q)} fee · ${q(x.net_q)} net · ${num(x.payout_usdt)} USDT</small><small>${esc(x.network)} · ${dt(x.requested_at)} · rate ${usd(x.q_reference_usd,4)}</small></div><span class="q21074-status ${esc(x.status.toLowerCase())}">${esc(x.status)}</span></div><div class="q21074-address">${esc(x.destination_address)}</div><div class="q21074-actions"><button class="ghost" data-view>View Details</button>${canWrite&&x.status==="PENDING"?'<button class="ghost" data-approve>Approve</button><button class="ghost" data-reject>Reject</button>':''}${canWrite&&x.status==="APPROVED"?'<button class="primary" data-paid>Mark Paid + TX</button><button class="ghost" data-failed>Failed / Release Q</button>':''}</div></div>`).join(""):'<p class="micro">No withdrawal requests match these filters.</p>';
      const host=byId("q21074AdminWithdrawals");host.querySelectorAll("[data-index]").forEach(row=>{const x=rows[Number(row.dataset.index)];row.querySelector("[data-view]").onclick=()=>withdrawalDetails(x);row.querySelector("[data-approve]")?.addEventListener("click",()=>withdrawalAction(x.id,"approve"));row.querySelector("[data-reject]")?.addEventListener("click",()=>withdrawalAction(x.id,"reject"));row.querySelector("[data-paid]")?.addEventListener("click",()=>withdrawalAction(x.id,"paid"));row.querySelector("[data-failed]")?.addEventListener("click",()=>withdrawalAction(x.id,"failed"))});
      byId("q21074AdminFilterBtn").onclick=loadAdminWithdrawals;
      byId("q21074AdminExportBtn").onclick=async()=>{try{const r=await fetch(`/v21074/admin/withdrawals/export.csv?${adminWithdrawalQs()}`,{headers:authHeaders()});if(!r.ok){const b=await r.json().catch(()=>({detail:"Export failed"}));throw new Error(b.detail||"Export failed")}const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="lemmiq-outgoing-usdt.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){toast(e.message,true)}};
    }catch(err){byId("q21074AdminWithdrawals").innerHTML=`<p class="micro">${esc(err.message||err)}</p>`}
  }

  async function load21074Admin(){
    installQrEnlarge();ensureAdminCards();
    try{await getAdminAccess()}catch{return}
    await Promise.all([loadFeaturePricing(),loadAdminEconomyControls(),loadAdminWithdrawals()]);
  }

  // Wrap stable loaders after every previous extension has initialized.
  if(typeof previousLoadQEconomy==="function"){
    window.loadQEconomy=async function(){await previousLoadQEconomy();await load21074Economy()};
  }
  if(typeof previousLoadQAdmin==="function"){
    window.loadQAdmin=async function(){await previousLoadQAdmin();adminAccess=null;await load21074Admin()};
  }

  installQrEnlarge();
  if(location.hash==="#q-economy"&&state?.token)setTimeout(load21074Economy,180);
  if(location.hash==="#q-admin"&&state?.token)setTimeout(load21074Admin,220);
})();
