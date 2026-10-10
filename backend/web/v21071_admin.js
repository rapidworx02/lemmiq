/* LEMMIQ V2.10.7.1 — section Admin RBAC */
(()=>{
  const LEVEL={NONE:0,READ:1,WRITE:2,FULL:3};
  const legacyLoadQAdmin=window.loadQAdmin;
  let access=null, selected=null;

  const esc=x=>escapeHtml(String(x??""));
  const fmt=x=>Number(x||0).toLocaleString(undefined,{maximumFractionDigits:6});
  const can=(section,level="READ")=>(LEVEL[access?.permissions?.[section]||"NONE"]||0)>=(LEVEL[level]||99);
  const v28=(path,opts={})=>api("/v28"+path,opts);

  function hero(master){
    const view=$("view-q-admin"),h=view?.querySelector(".q28-hero");
    if(!h)return;
    h.querySelector(".eyebrow").textContent=master?"MASTER ADMIN":"DELEGATED ADMIN";
    h.querySelector("h2").textContent=master?"Q Economy Admin":"Q Admin";
    $("q28AdminRole").textContent=access?.role||"—";
  }

  function restoreLegacy(){
    const view=$("view-q-admin"); if(!view)return;
    [...view.children].forEach(x=>{if(x.dataset.rbacHidden==="1"){x.style.display="";delete x.dataset.rbacHidden}});
    $("rbacDelegated")?.remove();
    hero(true);
  }

  function delegatedHost(){
    const view=$("view-q-admin"),h=view?.querySelector(".q28-hero"); if(!view||!h)return null;
    [...view.children].forEach(x=>{if(x!==h && x.id!=="rbacDelegated"){x.dataset.rbacHidden="1";x.style.display="none"}});
    let host=$("rbacDelegated");
    if(!host){host=document.createElement("div");host.id="rbacDelegated";host.className="rbac-shell";h.insertAdjacentElement("afterend",host)}
    host.innerHTML="";
    hero(false);
    return host;
  }

  function pill(section,label){
    const level=access.permissions?.[section]||"NONE";
    return `<span class="rbac-pill ${level}"><b>${esc(label)}</b><em>${esc(level)}</em></span>`;
  }

  function card(title,sub,body){
    return `<article class="card glass rbac-card"><div class="section-head"><div><h3>${esc(title)}</h3>${sub?`<p class="micro">${esc(sub)}</p>`:""}</div></div>${body}</article>`;
  }

  async function loadDelegated(){
    const host=delegatedHost(); if(!host)return;
    const sections=access.sections||{};
    host.innerHTML=card("Your section access","Master Admin controls this access.",
      `<div class="rbac-pills">${Object.entries(sections).filter(([k])=>k!=="ADMIN_TEAM").map(([k,v])=>pill(k,v)).join("")}</div>`);

    if(can("OVERVIEW")){
      try{
        const e=await v28("/admin/economy");
        host.innerHTML+=card("Overview & Analytics","READ summary",
          `<div class="q28-admin-stats"><div class="q28-stat"><small>Circulating</small><strong>${fmt(e.circulating_q)} Q</strong></div><div class="q28-stat"><small>Active packages</small><strong>${e.subscriptions?.active||0}</strong></div><div class="q28-stat"><small>Pending USDT</small><strong>${e.subscriptions?.pending_payments||0}</strong></div></div>`);
      }catch(e){host.innerHTML+=card("Overview & Analytics","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("USERS")){
      try{
        const rows=await v28("/admin/users");
        host.innerHTML+=card("Users & Packages",access.permissions.USERS,
          `<div class="rbac-list">${rows.slice(0,30).map(x=>`<div class="rbac-row"><div><strong>${esc(x.user?.display_name||"User")}</strong><small>@${esc(x.user?.username||"")} · ${fmt(x.wallet_q)} Q · ${(x.packages||[]).length} package(s)</small></div></div>`).join("")||'<p class="micro">No users.</p>'}</div>`);
      }catch(e){host.innerHTML+=card("Users & Packages","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("PAYMENTS")){
      try{
        const rows=await v28("/admin/payment-orders");
        const pending=rows.filter(x=>x.status==="PENDING");
        host.innerHTML+=card("Payments / USDT",access.permissions.PAYMENTS,
          `<div class="rbac-list">${pending.slice(0,30).map(x=>`<div class="rbac-row"><div><strong>${esc(x.package_name)} · ${fmt(x.expected_usdt)} USDT</strong><small>@${esc(x.user?.username||"")} · ${esc(x.network)} · ${esc(x.order_code)}</small></div>${can("PAYMENTS","WRITE")?`<div class="q28-actions"><button class="primary" data-rbac-pay="${x.id}" data-act="approve">Approve</button><button class="danger" data-rbac-pay="${x.id}" data-act="reject">Reject</button></div>`:""}</div>`).join("")||'<p class="micro">No pending payments.</p>'}</div>`);
        qsa("[data-rbac-pay]").forEach(b=>b.onclick=async()=>{
          try{
            if(b.dataset.act==="approve"){
              if(!confirm("Confirm this USDT transaction was verified on-chain?"))return;
              await v28(`/admin/payment-orders/${b.dataset.rbacPay}/approve`,{method:"POST",body:"{}"});
            }else{
              const note=prompt("Reason for rejection"); if(!note)return;
              await v28(`/admin/payment-orders/${b.dataset.rbacPay}/reject`,{method:"POST",body:JSON.stringify({note})});
            }
            toast("Payment updated");window.loadQAdmin();
          }catch(e){toast(e.message,true)}
        });
      }catch(e){host.innerHTML+=card("Payments / USDT","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("Q_PREDICT")){
      try{
        const [o,markets]=await Promise.all([
          api("/v29/predict/admin/overview?period=7d"),
          api("/v29/predict/admin/markets?status=REVIEW")
        ]);
        host.innerHTML+=card("Q Predict",access.permissions.Q_PREDICT,
          `<div class="q28-admin-stats"><div class="q28-stat"><small>Live</small><strong>${o.counts?.LIVE||0}</strong></div><div class="q28-stat"><small>Review</small><strong>${o.counts?.REVIEW||0}</strong></div><div class="q28-stat"><small>Predictors</small><strong>${o.active_predictors||0}</strong></div></div>
          ${can("Q_PREDICT","WRITE")?'<button id="rbacDraftMarkets" class="primary">Generate drafts</button>':""}
          <div class="rbac-list">${markets.slice(0,20).map(m=>`<div class="rbac-row"><div><strong>${esc(m.question)}</strong><small>${esc(m.category)} · REVIEW</small></div>${can("Q_PREDICT","WRITE")?`<button class="ghost" data-rbac-publish="${m.id}">Approve</button>`:""}</div>`).join("")||'<p class="micro">No drafts waiting.</p>'}</div>`);
        if($("rbacDraftMarkets"))$("rbacDraftMarkets").onclick=async()=>{try{await api("/v29/predict/admin/agent/run",{method:"POST",body:"{}"});toast("Draft generation completed");window.loadQAdmin()}catch(e){toast(e.message,true)}};
        qsa("[data-rbac-publish]").forEach(b=>b.onclick=async()=>{try{await api(`/v29/predict/admin/markets/${b.dataset.rbacPublish}/publish`,{method:"POST",body:"{}"});toast("Market published");window.loadQAdmin()}catch(e){toast(e.message,true)}});
      }catch(e){host.innerHTML+=card("Q Predict","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("MARKETPLACE")){
      try{
        const rows=await v28("/admin/market/orders"), disputes=rows.filter(x=>x.status==="DISPUTED");
        host.innerHTML+=card("Q Marketplace",access.permissions.MARKETPLACE,
          `<div class="rbac-list">${disputes.slice(0,20).map(x=>`<div class="rbac-row"><div><strong>${esc(x.order_code)} · ${fmt(x.total_q)} Q</strong><small>${esc(x.dispute_note||"Open dispute")}</small></div>${can("MARKETPLACE","FULL")?`<div class="q28-actions"><button class="ghost" data-rbac-resolve="${x.id}" data-outcome="BUYER">Refund buyer</button><button class="primary" data-rbac-resolve="${x.id}" data-outcome="SELLER">Pay seller</button></div>`:""}</div>`).join("")||'<p class="micro">No open disputes.</p>'}</div>`);
        qsa("[data-rbac-resolve]").forEach(b=>b.onclick=async()=>{const note=prompt("Admin resolution note")||"Admin resolution";try{await v28(`/admin/market/orders/${b.dataset.rbacResolve}/resolve`,{method:"POST",body:JSON.stringify({outcome:b.dataset.outcome,note})});toast("Dispute resolved");window.loadQAdmin()}catch(e){toast(e.message,true)}});
      }catch(e){host.innerHTML+=card("Q Marketplace","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("Q_ECONOMY")){
      try{
        const rows=await v28("/admin/ledger?limit=30");
        host.innerHTML+=card("Q Economy & Treasury",access.permissions.Q_ECONOMY,
          `<div class="rbac-list">${rows.slice(0,20).map(x=>`<div class="rbac-row"><div><strong>${esc(x.kind)} · ${fmt(x.amount_q)} Q</strong><small>${esc(x.note||"")} · ${new Date(x.created_at).toLocaleString()}</small></div></div>`).join("")}</div>${can("Q_ECONOMY","FULL")?'<p class="micro">Treasury transfer is permitted by the backend at FULL access. This first stability patch keeps the delegated screen read-focused; Master Admin retains the existing treasury transfer UI.</p>':""}`);
      }catch(e){host.innerHTML+=card("Q Economy & Treasury","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("PACKAGES_REFERRALS")){
      try{
        const rules=await v28("/admin/package-rules");
        host.innerHTML+=card("Packages & Referrals",access.permissions.PACKAGES_REFERRALS,
          `<div class="rbac-list">${rules.map(x=>`<div class="rbac-row"><div><strong>${esc(x.name)}</strong><small>${x.daily_rate_percent}% daily · ${x.cap_percent}% max</small></div></div>`).join("")}</div>`);
      }catch(e){host.innerHTML+=card("Packages & Referrals","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("Q_FEATURE_PRICING")){
      try{
        const d=await api("/v2105/admin/q-features");
        host.innerHTML+=card("Q Feature Pricing",access.permissions.Q_FEATURE_PRICING,
          `<p class="micro">Charging enabled: ${d.charging_enabled?"YES":"NO"} · ${(d.rules||[]).length} tier rules</p>`);
      }catch(e){host.innerHTML+=card("Q Feature Pricing","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("AUDIT_LOGS")){
      try{
        const rows=await v28("/admin/audit?limit=40");
        host.innerHTML+=card("Audit Logs","READ only",
          `<div class="rbac-list">${rows.slice(0,30).map(x=>`<div class="rbac-row"><div><strong>${esc(x.action)}</strong><small>${new Date(x.created_at).toLocaleString()} · ${esc(x.reason||"")}</small></div></div>`).join("")}</div>`);
      }catch(e){host.innerHTML+=card("Audit Logs","",`<p class="micro">${esc(e.message)}</p>`)}
    }

    if(can("SYSTEM_SETTINGS")){
      try{
        const c=await v28("/config");
        host.innerHTML+=card("System / Q Settings",access.permissions.SYSTEM_SETTINGS,
          `<div class="q28-admin-stats"><div class="q28-stat"><small>Q reference</small><strong>${Number(c.q_reference_usd||0).toFixed(4)}</strong></div><div class="q28-stat"><small>Marketplace fee</small><strong>${Number(c.marketplace_fee_percent||0)}%</strong></div></div>`);
      }catch(e){host.innerHTML+=card("System / Q Settings","",`<p class="micro">${esc(e.message)}</p>`)}
    }
  }

  function permissionEditor(){
    return `<div class="section-head"><div><h3>Admin Team & Section Access</h3><p class="micro">Search a LEMMIQ user by @username, then grant NONE / READ / WRITE / FULL per section. MASTER_ADMIN is never assignable here.</p></div></div>
      <div class="rbac-find"><input id="rbacUser" placeholder="@username"><button id="rbacFind" class="ghost">Find user</button></div>
      <div id="rbacIdentity" class="micro"></div>
      <div id="rbacGrid"></div>
      <div id="rbacActions" class="rbac-actions hidden"><select id="rbacRole"><option>SUPPORT_ADMIN</option><option>FINANCE_ADMIN</option><option>MARKETPLACE_ADMIN</option><option>RISK_ADMIN</option><option>READ_ONLY</option></select><button id="rbacSave" class="primary">Save section access</button><button id="rbacDisable" class="danger">Disable admin access</button></div>
      <h4>Current admin team</h4><div id="rbacList" class="rbac-list"></div>`;
  }

  function showSelected(d){
    selected=d;
    $("rbacIdentity").innerHTML=`<strong>${esc(d.user.display_name)}</strong> · @${esc(d.user.username)} · ${esc(d.role||"Not an admin yet")}`;
    $("rbacRole").value=(d.role&&d.role!=="MASTER_ADMIN")?d.role:"SUPPORT_ADMIN";
    $("rbacActions").classList.remove("hidden");
    $("rbacGrid").innerHTML=`<div class="rbac-grid">${Object.entries(d.sections||access.sections||{}).map(([k,label])=>{
      if(k==="ADMIN_TEAM")return `<div class="rbac-grid-row"><span>${esc(label)}</span><select disabled><option>MASTER ONLY</option></select></div>`;
      const cur=d.permissions?.[k]||"NONE";
      return `<div class="rbac-grid-row"><span>${esc(label)}</span><select data-rbac-sec="${k}">${["NONE","READ","WRITE","FULL"].map(v=>`<option ${v===cur?"selected":""}>${v}</option>`).join("")}</select></div>`;
    }).join("")}</div>`;
  }

  async function findUser(){
    const q=$("rbacUser").value.trim();if(!q)return;
    try{showSelected(await v28(`/admin/access/user?username=${encodeURIComponent(q)}`))}catch(e){toast(e.message,true)}
  }

  async function saveUser(activeFlag){
    if(!selected)return toast("Find a user first",true);
    const permissions=[...document.querySelectorAll("[data-rbac-sec]")].map(x=>({section_key:x.dataset.rbacSec,access_level:x.value}));
    if(activeFlag){
      const elevated=permissions.filter(x=>x.access_level==="WRITE"||x.access_level==="FULL").length;
      if(elevated&&!confirm(`Grant ${elevated} WRITE/FULL section permission(s) to @${selected.user.username}?`))return;
    }else if(!confirm(`Disable admin access for @${selected.user.username}?`))return;
    try{
      await v28("/admin/access/user",{method:"PUT",body:JSON.stringify({username:selected.user.username,role:$("rbacRole").value,active:activeFlag,permissions})});
      toast(activeFlag?"Admin access saved":"Admin access disabled");selected=null;$("rbacUser").value="";$("rbacIdentity").textContent="";$("rbacGrid").innerHTML="";$("rbacActions").classList.add("hidden");await loadTeam();
    }catch(e){toast(e.message,true)}
  }

  async function loadTeam(){
    try{
      const d=await v28("/admin/access/list");
      $("rbacList").innerHTML=(d.items||[]).map(x=>`<div class="rbac-row"><div><strong>@${esc(x.user.username)} · ${esc(x.user.display_name)}</strong><small>${esc(x.role)} · ${x.active?"Active":"Disabled"} · ${Object.values(x.permissions||{}).filter(v=>v!=="NONE").length} section(s)</small></div>${x.role!=="MASTER_ADMIN"?`<button class="ghost" data-rbac-manage="${esc(x.user.username)}">Manage</button>`:"<span>Master</span>"}</div>`).join("");
      qsa("[data-rbac-manage]").forEach(b=>b.onclick=async()=>{try{$("rbacUser").value=b.dataset.rbacManage;showSelected(await v28(`/admin/access/user?username=${encodeURIComponent(b.dataset.rbacManage)}`))}catch(e){toast(e.message,true)}});
    }catch(e){$("rbacList").innerHTML=`<p class="micro">${esc(e.message)}</p>`}
  }

  async function installMaster(){
    restoreLegacy();
    await legacyLoadQAdmin();
    const box=$("q28AdminTeamCard");if(!box)return;
    box.classList.remove("hidden");box.innerHTML=permissionEditor();
    $("rbacFind").onclick=findUser;$("rbacUser").onkeydown=e=>{if(e.key==="Enter")findUser()};
    $("rbacSave").onclick=()=>saveUser(true);$("rbacDisable").onclick=()=>saveUser(false);
    await loadTeam();
  }

  window.loadQAdmin=async()=>{
    try{
      access=await v28("/admin/access/me");
      if(access.role==="MASTER_ADMIN")await installMaster();else await loadDelegated();
    }catch(e){toast(e.message||String(e),true);setView("more")}
  };

  if(location.hash==="#q-admin"&&state?.token)setTimeout(()=>window.loadQAdmin(),0);
})();