/* LEMMIQ V2.8 Q Economy */
(()=>{
  const v28={wallet:null,ledger:[],referrals:null,payments:[],listings:[],orders:[],admin:null,adminWallets:[],adminPayments:[],adminLedger:[],adminMarket:[],adminRoles:{roles:[],items:[]}};
  const fmtQ=n=>new Intl.NumberFormat(undefined,{maximumFractionDigits:6}).format(Number(n||0));
  const fmtUsd=n=>new Intl.NumberFormat(undefined,{style:"currency",currency:"USD",maximumFractionDigits:4}).format(Number(n||0));
  const dt=x=>{try{return new Date(x).toLocaleString()}catch{return x||""}};
  const status=x=>`<span class="q28-status ${escapeHtml(x||"")}">${escapeHtml(x||"")}</span>`;

  async function qApi(path,opts={}){ return api("/v28"+path,opts); }

  function qRow(title,sub,right="",actions=""){
    return `<div class="q28-row"><div class="q28-main"><strong>${title}</strong><small>${sub||""}</small></div><div><div>${right||""}</div><div class="q28-actions">${actions||""}</div></div></div>`;
  }

  function renderWallet(){
    const w=v28.wallet;if(!w)return;
    $("q28Balance").textContent=`${fmtQ(w.balance_q)} Q`;
    $("q28Usd").textContent=`≈ ${fmtUsd(w.balance_usd_reference)} reference`;
    $("q28DailyInfo").textContent=w.basic_claimed_today
      ?`Today's basic Q has been claimed. Daily allowance: ${fmtQ(w.basic_daily_q)} Q.`
      :`Basic daily allowance: ${fmtQ(w.basic_daily_q)} Q. Cash-out is disabled in V2.8.`;
    $("q28ClaimDaily").disabled=!!w.basic_claimed_today;
    $("q28ReferralCode").textContent=w.referral_code||"—";
    $("q28ReferralInfo").textContent=`Referral reward: ${fmtQ(w.referral_reward_q)} Q · Signup bonus: ${fmtQ(w.signup_bonus_q)} Q.`;
    $("q28Subscriptions").innerHTML=(w.packages||[]).length?(w.packages||[]).map(p=>{
      const pct=p.cap_usd?Math.min(100,(Number(p.accrued_usd_reference||0)/Number(p.cap_usd))*100):0;
      return qRow(
        `${escapeHtml(p.package_name)} · ${status(p.status)}`,
        `${escapeHtml(p.package_code)} · ${p.daily_rate_percent}% daily · expires ${dt(p.expires_at)}<br>Accrued ${fmtQ(p.accrued_q)} Q · ${fmtUsd(p.accrued_usd_reference)} / ${fmtUsd(p.cap_usd)} cap · ${pct.toFixed(1)}%`,
        `${fmtUsd(p.remaining_cap_usd)} remaining`
      )
    }).join(""):`<div class="empty-state"><p>No paid Q packages yet.</p></div>`;

    $("q28Plans").innerHTML=(w.plans||[]).map(p=>`<div class="q28-plan ${p.code==="PREMIUM_500"?"featured":""}">
      <small>${p.daily_rate_percent}% daily package accrual</small>
      <h4>${escapeHtml(p.name)}</h4><div class="price">US$${p.price_usd}</div>
      <ul><li>≈ ${fmtQ(p.daily_q_at_current_reference)} Q/day at current reference</li><li>Up to ${fmtUsd(p.cap_usd)} package ceiling</li><li>365-day validity</li><li>Manual USDT verification</li></ul>
      <button class="primary" data-q28-buy="${p.code}">Buy with USDT</button>
    </div>`).join("");
    qsa("[data-q28-buy]").forEach(b=>b.onclick=()=>openPayment(b.dataset.q28Buy));
  }

  function renderLedger(){
    $("q28Ledger").innerHTML=v28.ledger.length?v28.ledger.map(x=>qRow(
      `${x.direction==="IN"?"+":"−"}${fmtQ(x.amount_q)} Q · ${escapeHtml(x.kind)}`,
      `${dt(x.created_at)}${x.note?` · ${escapeHtml(x.note)}`:""}`,
      x.direction==="IN"?'<span class="q28-positive">IN</span>':'<span class="q28-negative">OUT</span>'
    )).join(""):`<div class="empty-state"><p>No Q transactions yet.</p></div>`;
  }

  function renderReferrals(){
    const r=v28.referrals||{items:[],count:0,earned_q:0};
    $("q28ReferralList").innerHTML=qRow("Referral summary",`${r.count||0} successful referral(s)`,`${fmtQ(r.earned_q)} Q earned`)+
      ((r.items||[]).map(x=>qRow(`User #${x.user_id}`,dt(x.created_at),`+${fmtQ(x.reward_q)} Q`)).join(""));
  }

  function renderPayments(){
    $("q28PaymentOrders").innerHTML=v28.payments.length?v28.payments.map(x=>qRow(
      `${escapeHtml(x.package_name)} · ${status(x.status)}`,
      `${x.order_code} · ${x.network} · ${fmtQ(x.expected_usdt)} USDT${x.tx_hash?`<br>TX: ${escapeHtml(x.tx_hash)}`:""}`,
      x.explorer_url?`<a class="ghost" target="_blank" rel="noopener" href="${escapeHtml(x.explorer_url)}">Explorer ↗</a>`:""
    )).join(""):`<div class="empty-state"><p>No USDT payment orders yet.</p></div>`;
  }

  function renderMarket(){
    $("q28MarketListings").innerHTML=v28.listings.length?v28.listings.map(x=>`<article class="q28-listing">
      <small>${escapeHtml(x.category)} · ${escapeHtml(x.condition)}</small>
      <h4>${escapeHtml(x.title)}</h4><p>${escapeHtml(x.description||"")}</p>
      <div class="seller">@${escapeHtml(x.seller?.username||"seller")} · ${x.inventory} available</div>
      <div class="q-price">${fmtQ(x.price_q)} Q</div><div class="q-usd">≈ ${fmtUsd(x.price_usd_reference)} reference</div>
      ${x.seller?.id===state.user?.id?'<button class="ghost" disabled>Your listing</button>':`<button class="primary" data-q28-market-buy="${x.id}">Buy with Q</button>`}
    </article>`).join(""):`<article class="card glass"><p>No active listings found.</p></article>`;
    qsa("[data-q28-market-buy]").forEach(b=>b.onclick=()=>buyMarket(Number(b.dataset.q28MarketBuy)));
    $("q28MarketOrders").innerHTML=v28.orders.length?v28.orders.map(o=>{
      const mineSeller=o.seller_id===state.user?.id,mineBuyer=o.buyer_id===state.user?.id;
      let acts="";
      if(mineSeller&&o.status==="PAID")acts+=`<button class="ghost" data-q28-order-action="accept" data-id="${o.id}">Accept</button>`;
      if(mineSeller&&["PAID","ACCEPTED"].includes(o.status))acts+=`<button class="ghost" data-q28-order-action="delivered" data-id="${o.id}">Delivered</button>`;
      if(mineBuyer&&["ACCEPTED","DELIVERED"].includes(o.status))acts+=`<button class="primary" data-q28-order-action="complete" data-id="${o.id}">Confirm complete</button>`;
      if(mineBuyer&&o.status==="PAID")acts+=`<button class="ghost" data-q28-order-action="cancel" data-id="${o.id}">Cancel</button>`;
      if(["PAID","ACCEPTED","DELIVERED"].includes(o.status))acts+=`<button class="danger" data-q28-order-action="dispute" data-id="${o.id}">Dispute</button>`;
      return qRow(`${escapeHtml(o.order_code)} · ${status(o.status)}`,`${escapeHtml(o.listing?.title||"Listing")} · ${o.quantity} × · ${mineSeller?"Selling":"Buying"}`,`${fmtQ(o.total_q)} Q`,acts);
    }).join(""):`<div class="empty-state"><p>No marketplace orders yet.</p></div>`;
    qsa("[data-q28-order-action]").forEach(b=>b.onclick=()=>marketOrderAction(Number(b.dataset.id),b.dataset.q28OrderAction));
  }

  async function loadQEconomy(){
    try{
      const [wallet,ledger,refs,payments,listings,orders]=await Promise.all([
        qApi("/wallet"),qApi("/wallet/ledger"),qApi("/referrals"),qApi("/payments/orders"),
        qApi(`/market/listings?q=${encodeURIComponent($("q28MarketSearch")?.value||"")}`),qApi("/market/orders")
      ]);
      Object.assign(v28,{wallet,ledger,referrals:refs,payments,listings,orders});
      renderWallet();renderLedger();renderReferrals();renderPayments();renderMarket();
    }catch(e){toast(e.message,true)}
  }
  window.loadQEconomy=loadQEconomy;

  async function refreshV28Access(){
    if(!state?.token)return;
    try{
      const w=await qApi("/wallet");v28.wallet=w;
      if($("qAdminMoreCard"))$("qAdminMoreCard").classList.toggle("hidden",!w.admin_role);
    }catch{}
  }
  window.refreshV28Access=refreshV28Access;

  async function openPayment(code){
    try{
      const p=(v28.wallet?.plans||[]).find(x=>x.code===code);if(!p)return;
      $("modalContent").innerHTML=`<span class="eyebrow">Q SUBSCRIPTION</span><h2>${escapeHtml(p.name)}</h2><p>Pay <strong>${p.price_usd} USDT</strong>. Choose the exact network you will use.</p>
      <div class="q28-inline"><button class="primary" data-pay-net="TRC20">USDT TRC20</button><button class="primary" data-pay-net="BEP20">USDT BEP20</button></div>
      <p class="micro">Never send using a different network. V2.8 uses manual admin verification.</p>`;
      $("modal").showModal();
      qsa("[data-pay-net]").forEach(b=>b.onclick=()=>createPayment(code,b.dataset.payNet));
    }catch(e){toast(e.message,true)}
  }

  async function createPayment(code,network){
    try{
      const o=await qApi("/payments/orders",{method:"POST",body:JSON.stringify({package_code:code,network})});
      $("modalContent").innerHTML=`<div class="q28-payment-box"><span class="eyebrow">PAYMENT ORDER</span><h2>${escapeHtml(o.package_name)}</h2>
        <p>Send exactly <strong>${fmtQ(o.expected_usdt)} USDT</strong> using <strong>${o.network}</strong>.</p>
        <img class="q28-qr" src="${escapeHtml(o.wallet.qr_url)}" alt="Payment QR">
        <p class="q28-address">${escapeHtml(o.wallet.address)}</p><p><small>Order ${escapeHtml(o.order_code)}</small></p>
        <input id="q28TxHash" placeholder="Paste transaction hash after payment">
        <textarea id="q28PaymentNote" placeholder="Optional note"></textarea>
        <button id="q28SubmitPayment" class="primary full">I have paid — submit for verification</button>
        <p class="micro">Admin will verify the network, destination, amount and transaction hash before activation.</p></div>`;
      $("q28SubmitPayment").onclick=async()=>{
        const tx=$("q28TxHash").value.trim();if(tx.length<20){toast("Enter the transaction hash",true);return}
        try{
          await qApi(`/payments/orders/${o.id}/submit`,{method:"POST",body:JSON.stringify({tx_hash:tx,note:$("q28PaymentNote").value})});
          $("modal").close();toast("Payment submitted for admin verification");await loadQEconomy();
        }catch(e){toast(e.message,true)}
      };
    }catch(e){toast(e.message,true)}
  }

  async function buyMarket(id){
    if(!confirm("Buy this item/service using Q? Your Q will be held in escrow."))return;
    try{await qApi(`/market/listings/${id}/buy`,{method:"POST",body:JSON.stringify({quantity:1})});toast("Q moved to escrow");await loadQEconomy()}catch(e){toast(e.message,true)}
  }

  async function marketOrderAction(id,action){
    try{
      if(action==="dispute"){
        const note=prompt("Describe the dispute");if(!note)return;
        await qApi(`/market/orders/${id}/dispute`,{method:"POST",body:JSON.stringify({note})});
      }else{
        if(action==="complete"&&!confirm("Confirm the product/service is complete? This releases Q from escrow to the seller."))return;
        await qApi(`/market/orders/${id}/${action}`,{method:"POST",body:"{}"});
      }
      toast("Marketplace order updated");await loadQEconomy();
    }catch(e){toast(e.message,true)}
  }

  function adminStats(a){
    return [
      ["Q reference",fmtUsd(a.q_reference_usd)],
      ["Circulating",`${fmtQ(a.circulating_q)} Q`],
      ["Active packages",a.subscriptions?.active||0],
      ["Pending USDT",a.subscriptions?.pending_payments||0],
      ["USDT approved",fmtUsd(a.subscriptions?.approved_usdt||0)],
      ["Package caps",fmtUsd(a.subscriptions?.maximum_package_caps_usd||0)],
      ["Accrued reference",fmtUsd(a.subscriptions?.accrued_usd_reference||0)],
      ["Market volume",`${fmtQ(a.market?.completed_volume_q||0)} Q`],
    ].map(x=>`<div class="q28-stat"><small>${x[0]}</small><strong>${x[1]}</strong></div>`).join("");
  }

  function renderAdmin(){
    const a=v28.admin;if(!a)return;
    $("q28AdminOverview").innerHTML=adminStats(a.economy);
    $("q28AdminRole").textContent=a.me.role;
    if($("q28AdminTeamCard"))$("q28AdminTeamCard").classList.toggle("hidden",a.me.role!=="MASTER_ADMIN");
    if($("q28AdminTeam")){
      $("q28AdminTeam").innerHTML=(v28.adminRoles.items||[]).map(r=>qRow(
        `@${escapeHtml(r.username)} · ${escapeHtml(r.display_name)}`,
        `${escapeHtml(r.role)} · ${r.active?"Active":"Disabled"}`,
        r.user_id===a.me.id?"Current admin":""
      )).join("")||`<div class="empty-state"><p>No admin roles configured.</p></div>`;
    }
    $("q28AdminWallets").innerHTML=v28.adminWallets.length?v28.adminWallets.map(w=>qRow(
      `${w.network} · ${escapeHtml(w.package_code||"ALL PACKAGES")}`,
      `${escapeHtml(w.label||"Wallet")}<br>${escapeHtml(w.address)}`,
      w.active?"Active":"Disabled",`<a target="_blank" class="ghost" href="${escapeHtml(w.qr_url)}">QR</a>`
    )).join(""):`<div class="empty-state"><p>No receiving wallets configured.</p></div>`;

    const pending=v28.adminPayments.filter(x=>x.status==="PENDING");
    $("q28AdminPayments").innerHTML=pending.length?pending.map(o=>qRow(
      `${escapeHtml(o.package_name)} · ${fmtQ(o.expected_usdt)} USDT · ${o.network}`,
      `${escapeHtml(o.order_code)} · @${escapeHtml(o.user?.username||"")}<br>TX: ${escapeHtml(o.tx_hash||"")}`,
      o.explorer_url?`<a target="_blank" rel="noopener" href="${escapeHtml(o.explorer_url)}">Explorer ↗</a>`:"",
      `<button class="primary" data-admin-pay="approve" data-id="${o.id}">Approve</button><button class="danger" data-admin-pay="reject" data-id="${o.id}">Reject</button>`
    )).join(""):`<div class="empty-state"><p>No pending USDT payments.</p></div>`;
    qsa("[data-admin-pay]").forEach(b=>b.onclick=()=>adminPaymentAction(Number(b.dataset.id),b.dataset.adminPay));

    $("q28AdminTreasury").innerHTML=(a.economy.system_wallets||[]).map(w=>qRow(escapeHtml(w.label),escapeHtml(w.key),`${fmtQ(w.balance_q)} Q`)).join("");
    const opts=(a.economy.system_wallets||[]).map(w=>`<option value="${escapeHtml(w.key)}">${escapeHtml(w.label)}</option>`).join("");
    $("q28TreasuryFrom").innerHTML=opts;$("q28TreasuryTo").innerHTML=opts;
    if($("q28TreasuryTo").options.length>1)$("q28TreasuryTo").selectedIndex=1;

    $("q28AdminLedger").innerHTML=v28.adminLedger.slice(0,100).map(x=>qRow(
      `${escapeHtml(x.kind)} · ${fmtQ(x.amount_q)} Q`,
      `${dt(x.created_at)} · ${escapeHtml(x.reference||"")}`,
      `${escapeHtml(x.from_system||x.from_user||"GENESIS")} → ${escapeHtml(x.to_system||x.to_user||"")}`
    )).join("");

    const disputes=v28.adminMarket.filter(x=>x.status==="DISPUTED");
    $("q28AdminMarketOrders").innerHTML=disputes.length?disputes.map(o=>qRow(
      `${escapeHtml(o.order_code)} · ${fmtQ(o.total_q)} Q`,
      escapeHtml(o.dispute_note||"No dispute note"),status(o.status),
      `<button class="ghost" data-dispute-outcome="BUYER" data-id="${o.id}">Refund buyer</button><button class="primary" data-dispute-outcome="SELLER" data-id="${o.id}">Pay seller</button>`
    )).join(""):`<div class="empty-state"><p>No open disputes.</p></div>`;
    qsa("[data-dispute-outcome]").forEach(b=>b.onclick=()=>resolveDispute(Number(b.dataset.id),b.dataset.disputeOutcome));

    const c=a.config;
    $("q28AdminPrice").value=c.q_reference_usd;
    $("q28AdminFee").value=c.marketplace_fee_percent;
    $("q28AdminBasic").value=v28.wallet?.basic_daily_q??2;
    $("q28AdminSignup").value=v28.wallet?.signup_bonus_q??100;
    $("q28AdminReferrer").value=v28.wallet?.referral_reward_q??25;
    $("q28AdminReferred").value=25;
  }

  async function loadQAdmin(){
    try{
      const [me,economy,wallets,payments,ledger,market,config,wallet,roles]=await Promise.all([
        qApi("/admin/me"),qApi("/admin/economy"),qApi("/admin/payment-wallets"),qApi("/admin/payment-orders"),
        qApi("/admin/ledger"),qApi("/admin/market/orders"),qApi("/config"),qApi("/wallet"),qApi("/admin/roles")
      ]);
      v28.admin={me,economy,config};v28.adminWallets=wallets;v28.adminPayments=payments;v28.adminLedger=ledger;v28.adminMarket=market;v28.wallet=wallet;v28.adminRoles=roles;
      renderAdmin();
    }catch(e){toast(e.message,true);setView("more")}
  }
  window.loadQAdmin=loadQAdmin;

  async function adminPaymentAction(id,action){
    try{
      if(action==="approve"){
        if(!confirm("Confirm you personally verified this USDT transaction on-chain?"))return;
        await qApi(`/admin/payment-orders/${id}/approve`,{method:"POST",body:"{}"});
      }else{
        const note=prompt("Reason for rejection");if(!note)return;
        await qApi(`/admin/payment-orders/${id}/reject`,{method:"POST",body:JSON.stringify({note})});
      }
      toast(`Payment ${action}d`);await loadQAdmin();
    }catch(e){toast(e.message,true)}
  }

  async function resolveDispute(id,outcome){
    const note=prompt(`Admin note for ${outcome==="BUYER"?"refund buyer":"pay seller"}`)||"Admin resolution";
    try{await qApi(`/admin/market/orders/${id}/resolve`,{method:"POST",body:JSON.stringify({outcome,note})});toast("Dispute resolved");await loadQAdmin()}catch(e){toast(e.message,true)}
  }

  function bind(){
    qsa("[data-q28-tab]").forEach(b=>b.onclick=()=>{
      qsa("[data-q28-tab]").forEach(x=>x.classList.toggle("active",x===b));
      qsa(".q28-tab").forEach(x=>x.classList.toggle("active",x.id===`q28Tab-${b.dataset.q28Tab}`));
    });
    $("q28ClaimDaily")?.addEventListener("click",async()=>{try{await qApi("/wallet/claim-daily",{method:"POST",body:"{}"});toast("Daily Q claimed");await loadQEconomy()}catch(e){toast(e.message,true)}});
    $("q28SendBtn")?.addEventListener("click",async()=>{
      const username=$("q28SendUser").value.trim().replace(/^@/,""),amount=Number($("q28SendAmount").value);
      if(!username||!(amount>0)){toast("Enter username and Q amount",true);return}
      if(!confirm(`Send ${amount} Q to @${username}?`))return;
      try{await qApi("/wallet/transfer",{method:"POST",body:JSON.stringify({username,amount_q:amount,note:"LEMMIQ Q transfer"})});$("q28SendAmount").value="";toast("Q sent");await loadQEconomy()}catch(e){toast(e.message,true)}
    });
    $("q28RefreshLedger")?.addEventListener("click",loadQEconomy);
    $("q28MarketSearchBtn")?.addEventListener("click",loadQEconomy);
    $("q28CreateListing")?.addEventListener("click",async()=>{
      const title=$("q28ListingTitle").value.trim(),description=$("q28ListingDescription").value.trim(),price=Number($("q28ListingPrice").value),inventory=Number($("q28ListingInventory").value||1);
      if(!title||!(price>0)){toast("Enter title and Q price",true);return}
      try{await qApi("/market/listings",{method:"POST",body:JSON.stringify({title,description,category:"OTHER",condition:"SERVICE",price_q:price,inventory})});toast("Q Market listing created");$("q28ListingTitle").value="";$("q28ListingDescription").value="";$("q28ListingPrice").value="";await loadQEconomy()}catch(e){toast(e.message,true)}
    });
    $("q28CopyReferral")?.addEventListener("click",async()=>{const code=v28.wallet?.referral_code||"";if(!code)return;await navigator.clipboard?.writeText(code);toast("Referral code copied")});
    $("q28ClaimReferralBtn")?.addEventListener("click",async()=>{const code=$("q28ClaimReferralCode").value.trim();if(!code)return;try{await qApi("/referrals/claim",{method:"POST",body:JSON.stringify({code})});toast("Referral reward claimed");await loadQEconomy()}catch(e){toast(e.message,true)}});

    $("q28AdminTeamSave")?.addEventListener("click",async()=>{
      const username=$("q28AdminTeamUser").value.trim().replace(/^@/,""),role=$("q28AdminTeamRole").value;
      if(!username){toast("Enter a LEMMIQ username",true);return}
      try{
        await qApi("/admin/roles",{method:"POST",body:JSON.stringify({username,role,active:true})});
        $("q28AdminTeamUser").value="";toast("Admin role updated");await loadQAdmin();
      }catch(e){toast(e.message,true)}
    });
    $("q28AdminAddWallet")?.addEventListener("click",async()=>{
      const body={network:$("q28AdminNetwork").value,package_code:$("q28AdminPackage").value||null,label:$("q28AdminWalletLabel").value,address:$("q28AdminWalletAddress").value.trim(),active:true};
      if(!body.address){toast("Enter a public USDT receiving address",true);return}
      try{await qApi("/admin/payment-wallets",{method:"POST",body:JSON.stringify(body)});toast("Payment wallet added");$("q28AdminWalletAddress").value="";await loadQAdmin()}catch(e){toast(e.message,true)}
    });
    $("q28AdminSaveConfig")?.addEventListener("click",async()=>{
      const body={q_price_usd:Number($("q28AdminPrice").value),marketplace_fee_percent:Number($("q28AdminFee").value),basic_daily_q:Number($("q28AdminBasic").value),signup_bonus_q:Number($("q28AdminSignup").value),referral_referrer_q:Number($("q28AdminReferrer").value),referral_referred_q:Number($("q28AdminReferred").value)};
      try{await qApi("/admin/config",{method:"PUT",body:JSON.stringify(body)});toast("Q settings saved");await loadQAdmin()}catch(e){toast(e.message,true)}
    });
    $("q28AdminRefreshPayments")?.addEventListener("click",loadQAdmin);
    $("q28TreasuryTransfer")?.addEventListener("click",async()=>{
      const body={from_wallet:$("q28TreasuryFrom").value,to_wallet:$("q28TreasuryTo").value,amount_q:Number($("q28TreasuryAmount").value),reason:$("q28TreasuryReason").value.trim()};
      if(!(body.amount_q>0)||body.reason.length<3){toast("Enter amount and reason",true);return}
      if(!confirm(`Transfer ${body.amount_q} Q between treasury wallets?`))return;
      try{await qApi("/admin/treasury/transfer",{method:"POST",body:JSON.stringify(body)});toast("Treasury transfer completed");await loadQAdmin()}catch(e){toast(e.message,true)}
    });
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",bind);else bind();
})();