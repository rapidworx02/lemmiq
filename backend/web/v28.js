/* LEMMIQ V2.8.3 Q Economy */
(()=>{
  const v28={wallet:null,ledger:[],referrals:null,payments:[],listings:[],myListings:[],orders:[],admin:null,adminWallets:[],adminWalletMatrix:[],adminPackageRules:[],adminUsers:[],adminAudit:[],adminPayments:[],adminLedger:[],adminMarket:[],adminRoles:{roles:[],items:[]},adminReferralRules:[],adminReferralOverview:null};
  const fmtQ=n=>new Intl.NumberFormat(undefined,{maximumFractionDigits:6}).format(Number(n||0));
  const fmtUsd=n=>new Intl.NumberFormat(undefined,{style:"currency",currency:"USD",maximumFractionDigits:4}).format(Number(n||0));
  const dt=x=>{try{return new Date(x).toLocaleString()}catch{return x||""}};
  const status=x=>`<span class="q28-status ${escapeHtml(x||"")}">${escapeHtml(x||"")}</span>`;

  async function qApi(path,opts={}){ return api("/v28"+path,opts); }

  function qRow(title,sub,right="",actions=""){
    return `<div class="q28-row"><div class="q28-main"><strong>${title}</strong><small>${sub||""}</small></div><div><div>${right||""}</div><div class="q28-actions">${actions||""}</div></div></div>`;
  }

  function marketMediaHtml(media=[]){
    if(!media?.length)return "";
    return `<div class="q28-media-strip">${media.map(m=>{
      const url=escapeHtml(m.media_url||"");
      if(m.kind==="PHOTO")return `<a href="${url}" target="_blank" rel="noopener"><img src="${url}" alt="${escapeHtml(m.name||"Listing photo")}"></a>`;
      if(m.kind==="VIDEO")return `<a class="q28-media-file" href="${url}" target="_blank" rel="noopener">🎥 ${escapeHtml(m.name||"Video")}</a>`;
      return `<a class="q28-media-file" href="${escapeHtml(m.download_url||url)}" target="_blank" rel="noopener">📎 ${escapeHtml(m.name||"File")}</a>`;
    }).join("")}</div>`;
  }

  function selectedMediaPreview(){
    const files=[...($(`q28ListingMedia`)?.files||[])].slice(0,10);
    if(!$(`q28ListingMediaPreview`))return;
    $(`q28ListingMediaPreview`).innerHTML=files.map(f=>`<span>${f.type.startsWith("image/")?"🖼️":f.type.startsWith("video/")?"🎥":"📎"} ${escapeHtml(f.name)} <small>${Math.max(1,Math.round(f.size/1024))} KB</small></span>`).join("");
  }

  async function uploadListingMedia(listingId,files){
    for(const file of files.slice(0,10)){
      const form=new FormData();form.append("file",file,file.name);
      await qApi(`/market/listings/${listingId}/media`,{method:"POST",body:form});
    }
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
    const r=v28.referrals||{items:[],count:0,paid_users:0,earned_q:0,pending_q:0};
    const summary=qRow(
      "Referral summary",
      `${r.count||0} referred · ${r.paid_users||0} paid subscriber(s)`,
      `${fmtQ(r.earned_q)} Q earned${Number(r.pending_q||0)>0?` · ${fmtQ(r.pending_q)} Q pending`:""}`
    );
    const rows=(r.items||[]).map(x=>{
      const events=(x.events||[]).map(e=>`<div class="q28-ref-event"><span>${escapeHtml(e.label||e.type)}</span><b>+${fmtQ(e.reward_q)} Q</b><em>${escapeHtml(e.status||"")}</em></div>`).join("");
      return `<details class="q28-referral-card"><summary><div><strong>${escapeHtml(x.display_name||x.username||("User #"+x.user_id))}</strong><small>@${escapeHtml(x.username||"")} · ${escapeHtml(x.current_tier||"Free")} · joined ${dt(x.created_at)}</small></div><div><b>${fmtQ(x.reward_q)} Q</b>${Number(x.pending_q||0)>0?`<small>${fmtQ(x.pending_q)} Q pending</small>`:""}</div></summary><div class="q28-ref-events">${events||"<span>No reward events yet.</span>"}</div></details>`;
    }).join("");
    $("q28ReferralList").innerHTML=summary+(rows||`<div class="empty-state"><p>No referrals yet.</p></div>`);
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
      <h4>${escapeHtml(x.title)}</h4>${marketMediaHtml(x.media)}<p>${escapeHtml(x.description||"")}</p>
      <div class="seller">@${escapeHtml(x.seller?.username||"seller")} · ${x.inventory} available · ${(x.media||[]).length} attachment(s)</div>
      <div class="q-price">${fmtQ(x.price_q)} Q</div><div class="q-usd">≈ ${fmtUsd(x.price_usd_reference)} reference</div>
      ${x.seller?.id===state.user?.id?'<button class="ghost" disabled>Your listing</button>':`<button class="primary" data-q28-market-buy="${x.id}">Buy with Q</button>`}
    </article>`).join(""):`<article class="card glass"><p>No active listings found.</p></article>`;
    qsa("[data-q28-market-buy]").forEach(b=>b.onclick=()=>buyMarket(Number(b.dataset.q28MarketBuy)));
    if($("q28MyListings")){
      $("q28MyListings").innerHTML=v28.myListings.length?v28.myListings.map(x=>qRow(
        `${escapeHtml(x.title)} · ${x.active?"Active":"Paused"}`,
        `${fmtQ(x.price_q)} Q · ${x.inventory} available · ${escapeHtml(x.category)} · ${(x.media||[]).length} attachment(s)`,
        `≈ ${fmtUsd(x.price_usd_reference)}`,
        `<button class="ghost" data-q28-edit-listing="${x.id}">Edit</button><button class="ghost" data-q28-media-listing="${x.id}">Media</button>`
      )).join(""):`<div class="empty-state"><p>No listings yet.</p></div>`;
      qsa("[data-q28-edit-listing]").forEach(b=>b.onclick=()=>editListing(Number(b.dataset.q28EditListing)));
      qsa("[data-q28-media-listing]").forEach(b=>b.onclick=()=>manageListingMedia(Number(b.dataset.q28MediaListing)));
    }
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
      const [wallet,ledger,refs,payments,listings,myListings,orders]=await Promise.all([
        qApi("/wallet"),qApi("/wallet/ledger"),qApi("/referrals"),qApi("/payments/orders"),
        qApi(`/market/listings?q=${encodeURIComponent($("q28MarketSearch")?.value||"")}`),qApi("/market/my-listings"),qApi("/market/orders")
      ]);
      Object.assign(v28,{wallet,ledger,referrals:refs,payments,listings,myListings,orders});
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
      $("modalContent").innerHTML=`<div class="q28-network-modal"><span class="eyebrow">Q SUBSCRIPTION</span><h2>${escapeHtml(p.name)}</h2><p>Pay <strong>${p.price_usd} USDT</strong>. Select the exact network you will use.</p><p class="micro">Package rate: ${p.daily_rate_percent}% daily · 200% package ceiling · 365-day validity</p><div class="q28-network-buttons"><button class="primary full" data-pay-net="TRC20">USDT TRC20</button><button class="ghost full" data-pay-net="BEP20">USDT BEP20</button></div><p class="micro q28-warning">⚠ Send only on the selected network. Sending on another network may result in loss of funds.</p><button id="q28CancelNetwork" class="ghost full">Cancel</button></div>`;
      $("modal").showModal();
      qsa("[data-pay-net]").forEach(b=>b.onclick=()=>createPayment(code,b.dataset.payNet));
      $("q28CancelNetwork").onclick=()=>$("modal").close();
    }catch(e){toast(e.message,true)}
  }

  async function createPayment(code,network){
    try{
      const o=await qApi("/payments/orders",{method:"POST",body:JSON.stringify({package_code:code,network})});
      $("modalContent").innerHTML=`<div class="q28-payment-box"><span class="eyebrow">PAYMENT ORDER</span><h2>Pay ${fmtQ(o.expected_usdt)} USDT</h2><div class="q28-payment-network">${escapeHtml(o.network)} · ${escapeHtml(o.order_code)}</div><img id="q28PaymentQr" class="q28-qr q28-qr-large" src="${escapeHtml(o.wallet.qr_url)}" alt="Payment QR"><small>Tap QR to enlarge</small><div class="q28-copy-card"><label>Wallet address</label><div class="q28-address">${escapeHtml(o.wallet.address)}</div><button id="q28CopyAddress" class="ghost full">📋 Copy address</button></div><div class="q28-copy-actions"><button id="q28CopyAmount" class="ghost">Copy ${fmtQ(o.expected_usdt)} USDT</button><button id="q28CopyOrder" class="ghost">Copy Order ID</button></div><p class="micro q28-warning">⚠ Send USDT using <strong>${escapeHtml(o.network)}</strong> only.</p><input id="q28TxHash" placeholder="Paste transaction hash"><textarea id="q28PaymentNote" placeholder="Optional note"></textarea><button id="q28SubmitPayment" class="primary full" disabled>Submit for verification</button><button id="q28CancelPayment" class="ghost full">Cancel</button><p class="micro">Admin manually verifies network, address and amount before activation.</p></div>`;
      const copy=async(text,msg)=>{try{await navigator.clipboard.writeText(String(text));toast(msg)}catch{toast("Copy failed — select and copy manually",true)}};
      $("q28CopyAddress").onclick=()=>copy(o.wallet.address,"Address copied ✓");
      $("q28CopyAmount").onclick=()=>copy(o.expected_usdt,"Amount copied ✓");
      $("q28CopyOrder").onclick=()=>copy(o.order_code,"Order ID copied ✓");
      $("q28CancelPayment").onclick=()=>$("modal").close();
      $("q28PaymentQr").onclick=()=>{const w=window.open("","_blank");if(w)w.document.write(`<body style="margin:0;background:#fff;display:grid;place-items:center;height:100vh"><img src="${escapeHtml(o.wallet.qr_url)}" style="width:min(90vw,720px);height:auto"></body>`)};
      $("q28TxHash").oninput=()=>{$("q28SubmitPayment").disabled=$("q28TxHash").value.trim().length<20};
      $("q28SubmitPayment").onclick=async()=>{
        const tx=$("q28TxHash").value.trim();if(tx.length<20){toast("Enter the transaction hash",true);return}
        try{await qApi(`/payments/orders/${o.id}/submit`,{method:"POST",body:JSON.stringify({tx_hash:tx,note:$("q28PaymentNote").value})});$("modal").close();toast("Payment submitted for admin verification");await loadQEconomy()}catch(e){toast(e.message,true)}
      };
    }catch(e){toast(e.message,true)}
  }

  async function manageListingMedia(id){
    const x=v28.myListings.find(y=>y.id===id);if(!x)return;
    const rows=(x.media||[]).map(m=>`<div class="q28-row"><div class="q28-main"><strong>${m.kind==="PHOTO"?"🖼️":m.kind==="VIDEO"?"🎥":"📎"} ${escapeHtml(m.name)}</strong><small>${Math.max(1,Math.round((m.size_bytes||0)/1024))} KB ${m.is_cover?"· Cover":""}</small></div><div class="q28-actions">${m.kind==="PHOTO"&&!m.is_cover?`<button class="ghost" data-set-cover="${m.id}">Set cover</button>`:""}<button class="danger" data-delete-media="${m.id}">Remove</button></div></div>`).join("");
    $("modalContent").innerHTML=`<span class="eyebrow">Q MARKET MEDIA</span><h2>${escapeHtml(x.title)}</h2><label class="q28-upload-box">Add more photos, videos or files<input id="q28MoreMedia" type="file" multiple accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime,application/pdf,text/plain,text/csv,.docx,.xlsx" hidden><span>+ Add media / files</span><small>Maximum 10 attachments total</small></label><div class="q28-list">${rows||"<p>No attachments yet.</p>"}</div><button id="q28CloseMedia" class="ghost full">Close</button>`;
    $("modal").showModal();
    $("q28CloseMedia").onclick=()=>$("modal").close();
    $("q28MoreMedia").onchange=async()=>{try{await uploadListingMedia(x.id,[...$("q28MoreMedia").files].slice(0,Math.max(0,10-(x.media||[]).length)));$("modal").close();toast("Media uploaded");await loadQEconomy()}catch(e){toast(e.message,true)}};
    qsa("[data-delete-media]").forEach(b=>b.onclick=async()=>{if(!confirm("Remove this marketplace attachment?"))return;try{await qApi(`/market/listings/${x.id}/media/${b.dataset.deleteMedia}`,{method:"DELETE"});$("modal").close();toast("Attachment removed");await loadQEconomy()}catch(e){toast(e.message,true)}});
    qsa("[data-set-cover]").forEach(b=>b.onclick=async()=>{try{await qApi(`/market/listings/${x.id}/media/${b.dataset.setCover}/cover`,{method:"POST",body:"{}"});$("modal").close();toast("Cover photo updated");await loadQEconomy()}catch(e){toast(e.message,true)}});
  }

  async function editListing(id){
    const x=v28.myListings.find(y=>y.id===id);if(!x)return;
    const title=prompt("Listing title",x.title);if(title===null||!title.trim())return;
    const description=prompt("Description",x.description||"");if(description===null)return;
    const priceRaw=prompt("Price in Q",String(x.price_q));if(priceRaw===null)return;
    const inventoryRaw=prompt("Available quantity",String(x.inventory));if(inventoryRaw===null)return;
    const price=Number(priceRaw),inventory=Number(inventoryRaw);
    if(!(price>0)||!(inventory>=1)){toast("Price and inventory must be valid",true);return}
    const active=confirm("Keep this listing ACTIVE?\nOK = Active\nCancel = Pause");
    try{
      await qApi(`/market/listings/${id}`,{method:"PUT",body:JSON.stringify({
        title:title.trim(),description,category:x.category||"OTHER",condition:x.condition||"SERVICE",
        price_q:price,inventory:Math.floor(inventory),active
      })});
      toast("Listing updated");await loadQEconomy();
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

  function adminParty(system,info,id){
    if(system)return escapeHtml(system);
    if(info)return `User #${info.id} · ${escapeHtml(info.display_name||"")} · @${escapeHtml(info.username||"")}`;
    if(id)return `User #${id}`;
    return "—";
  }

  function renderWalletMatrix(){
    const el=$("q28WalletMatrix");if(!el)return;
    const grouped={};
    (v28.adminWalletMatrix||[]).forEach(x=>{(grouped[x.package_code]??=[]).push(x)});
    el.innerHTML=Object.entries(grouped).map(([code,items])=>`<section class="q28-wallet-package"><div class="q28-wallet-package-head"><strong>${escapeHtml(items[0]?.package_name||code)}</strong><span>US$${items[0]?.price_usd||""}</span></div><div class="q28-wallet-network-grid">${items.map(slot=>{
      const w=slot.wallet||{};
      return `<div class="q28-wallet-slot"><div class="q28-wallet-slot-title"><b>${slot.network}</b>${w.active?'<span class="q28-status APPROVED">Active</span>':'<span class="q28-status">Not set</span>'}</div><input data-wallet-label="${slot.slot_key}" value="${escapeHtml(w.label||`${slot.package_name} ${slot.network}`)}" placeholder="Label"><input data-wallet-address="${slot.slot_key}" value="${escapeHtml(w.address||"")}" placeholder="Public USDT ${slot.network} address"><div class="q28-actions"><button class="primary" data-wallet-save="${slot.slot_key}">${w.id?'Replace / Save':'Add wallet'}</button>${w.id?`<a class="ghost" target="_blank" href="${escapeHtml(w.qr_url||'')}">QR</a><button class="ghost" data-q28-upload-qr="${w.id}">Upload QR</button>`:''}</div></div>`;
    }).join("")}</div></section>`).join("");
    qsa("[data-wallet-save]").forEach(b=>b.onclick=()=>saveWalletSlot(b.dataset.walletSave));
    qsa("[data-q28-upload-qr]").forEach(b=>b.onclick=()=>uploadWalletQr(Number(b.dataset.q28UploadQr)));
  }

  async function saveWalletSlot(slotKey){
    const [code,network]=slotKey.split(":");
    const address=document.querySelector(`[data-wallet-address="${slotKey}"]`)?.value.trim()||"";
    const label=document.querySelector(`[data-wallet-label="${slotKey}"]`)?.value.trim()||"";
    if(!address){toast("Enter the public USDT receiving address",true);return}
    if(!confirm(`Save ${network} wallet for ${code}? New payment orders will use this address.`))return;
    try{
      await qApi(`/admin/payment-wallet-matrix/${code}/${network}`,{method:"PUT",body:JSON.stringify({address,label,active:true})});
      toast("USDT wallet slot saved");await loadQAdmin();
    }catch(e){toast(e.message,true)}
  }

  function renderPackageMasterRules(){
    const el=$("q28PackageMasterRules");if(!el)return;
    el.innerHTML=(v28.adminPackageRules||[]).map(r=>`<div class="q28-master-rule"><div><strong>${escapeHtml(r.name)}</strong><small>US$${r.price_usd}</small></div><label>Daily return %<input data-rule-daily="${r.package_code}" type="number" min="0" max="10" step="0.01" value="${r.daily_rate_percent}"></label><label>Maximum return %<input data-rule-cap="${r.package_code}" type="number" min="0" max="1000" step="1" value="${r.cap_percent}"></label><label class="q28-check"><input data-rule-preserve="${r.package_code}" type="checkbox"> Preserve individual overrides</label><div class="q28-actions"><button class="primary" data-rule-apply="${r.package_code}">Apply to all current + future</button><button class="ghost" data-rule-future="${r.package_code}">Future packages only</button></div></div>`).join("");
    qsa("[data-rule-apply]").forEach(b=>b.onclick=()=>savePackageMasterRule(b.dataset.ruleApply,true));
    qsa("[data-rule-future]").forEach(b=>b.onclick=()=>savePackageMasterRule(b.dataset.ruleFuture,false));
  }

  async function savePackageMasterRule(code,applyExisting){
    const daily=Number(document.querySelector(`[data-rule-daily="${code}"]`)?.value);
    const cap=Number(document.querySelector(`[data-rule-cap="${code}"]`)?.value);
    const preserve=!!document.querySelector(`[data-rule-preserve="${code}"]`)?.checked;
    if(!Number.isFinite(daily)||!Number.isFinite(cap)){toast("Enter valid daily and maximum return percentages",true);return}
    const reason=prompt("Reason for this master package change",applyExisting?"Master package rate update":"Future package default update");if(reason===null)return;
    const warning=applyExisting?`Apply ${daily}% daily / ${cap}% max to existing ${code} packages as well? Past earnings will not be recalculated.`:`Save ${daily}% daily / ${cap}% max for future ${code} packages only?`;
    if(!confirm(warning))return;
    try{
      const r=await qApi(`/admin/package-rules/${code}`,{method:"PUT",body:JSON.stringify({daily_rate_percent:daily,cap_percent:cap,apply_to_existing:applyExisting,include_custom:applyExisting&&!preserve,reason:reason||"Package master update"})});
      toast(`Package rule saved · ${r.affected||0} existing package(s) updated`);await loadQAdmin();
    }catch(e){toast(e.message,true)}
  }

  function renderAdminUsers(){
    const el=$("q28AdminUsers");if(!el)return;
    el.innerHTML=(v28.adminUsers||[]).length?(v28.adminUsers||[]).map(x=>{
      const p=x.packages||[];
      const active=p.filter(a=>a.status==="ACTIVE").length;
      const summary=p.slice(0,3).map(a=>`${escapeHtml(a.package_name)} · ${a.daily_rate_percent}%/day · ${a.earned_percent}% earned of ${a.cap_percent}% max · ${escapeHtml(a.status)}`).join("<br>") || "No package";
      return qRow(`User #${x.user.id} · ${escapeHtml(x.user.display_name)} · @${escapeHtml(x.user.username)}`,`${fmtQ(x.wallet_q)} Q wallet · ${active} active package(s)<br>${summary}`,"",`<button class="primary" data-manage-user="${x.user.id}">Manage</button>`);
    }).join(""):`<div class="empty-state"><p>No users matched your search.</p></div>`;
    qsa("[data-manage-user]").forEach(b=>b.onclick=()=>openAdminUser(Number(b.dataset.manageUser)));
  }

  async function loadAdminUsers(){
    try{
      const q=$("q28AdminUserSearch")?.value.trim()||"";
      const pc=$("q28AdminUserPackage")?.value||"";
      const st=$("q28AdminUserStatus")?.value||"";
      v28.adminUsers=await qApi(`/admin/users?q=${encodeURIComponent(q)}&package_code=${encodeURIComponent(pc)}&status=${encodeURIComponent(st)}`);
      renderAdminUsers();
    }catch(e){toast(e.message,true)}
  }

  function packageCardHtml(p){
    return `<div class="q28-admin-package"><div class="q28-admin-package-head"><strong>${escapeHtml(p.package_name)} #${p.id}</strong>${status(p.status)}</div><div class="q28-package-metrics"><span>Daily <b>${p.daily_rate_percent}%</b>${p.daily_rate_override?' *':''}</span><span>Earned <b>${Number(p.earned_percent||0).toFixed(2)}%</b></span><span>Max <b>${Number(p.cap_percent||0).toFixed(2)}%</b>${p.cap_percent_override?' *':''}</span><span>Q earned <b>${fmtQ(p.accrued_q)}</b></span><span>Value <b>${fmtUsd(p.accrued_usd_reference)}</b></span><span>Remaining <b>${fmtUsd(p.remaining_cap_usd)}</b></span></div><small>* individual override</small><div class="q28-actions"><button class="primary" data-edit-user-package="${p.id}">Edit package</button></div></div>`;
  }

  async function openAdminUser(userId){
    try{
      const d=await qApi(`/admin/users/${userId}`);
      openModal(`<span class="eyebrow">Q USER CONTROL</span><h2>User #${d.user.id} · ${escapeHtml(d.user.display_name)}</h2><p>@${escapeHtml(d.user.username)}</p><div class="q28-user-wallet-control"><div><small>Q Wallet</small><strong>${fmtQ(d.wallet_q)} Q</strong><span>≈ ${fmtUsd(d.wallet_usd_reference)} reference</span></div><div><input id="q28AdjustAmount" type="number" step="0.01" placeholder="+/- Q correction"><input id="q28AdjustReason" placeholder="Reason for adjustment"><button id="q28AdjustWallet" class="primary">Apply wallet correction</button></div></div><h3>Packages</h3><div class="q28-list">${(d.packages||[]).map(packageCardHtml).join("")||"<p>No packages.</p>"}</div><button id="q28CloseUserControl" class="ghost full">Close</button>`);
      $("q28AdjustWallet").onclick=async()=>{
        const amount=Number($("q28AdjustAmount").value),reason=$("q28AdjustReason").value.trim();
        if(!amount||reason.length<3){toast("Enter a non-zero Q correction and reason",true);return}
        if(!confirm(`Apply ${amount>0?'+':''}${amount} Q adjustment to @${d.user.username}?`))return;
        try{await qApi(`/admin/users/${d.user.id}/wallet-adjust`,{method:"POST",body:JSON.stringify({amount_q:amount,reason})});toast("Wallet correction recorded");closeModal();await loadQAdmin();await openAdminUser(d.user.id)}catch(e){toast(e.message,true)}
      };
      qsa("[data-edit-user-package]").forEach(b=>b.onclick=()=>{const p=d.packages.find(x=>x.id===Number(b.dataset.editUserPackage));if(p)openAdminPackageEditor(d.user,p)});
      $("q28CloseUserControl").onclick=closeModal;
    }catch(e){toast(e.message,true)}
  }

  function openAdminPackageEditor(user,p){
    openModal(`<span class="eyebrow">PACKAGE CONTROL</span><h2>${escapeHtml(p.package_name)} #${p.id}</h2><p>User #${user.id} · ${escapeHtml(user.display_name)} · @${escapeHtml(user.username)}</p><div class="q28-package-metrics"><span>Earned <b>${Number(p.earned_percent||0).toFixed(2)}%</b></span><span>Current max <b>${Number(p.cap_percent||0).toFixed(2)}%</b></span><span>Accrued <b>${fmtUsd(p.accrued_usd_reference)}</b></span><span>Q <b>${fmtQ(p.accrued_q)}</b></span></div><label>Daily return %<input id="q28EditDaily" type="number" step="0.01" value="${p.daily_rate_percent}"></label><label>Maximum return %<input id="q28EditCap" type="number" step="1" value="${p.cap_percent}"></label><label>Status<select id="q28EditStatus"><option ${p.status==='ACTIVE'?'selected':''}>ACTIVE</option><option ${p.status==='PAUSED'?'selected':''}>PAUSED</option><option ${p.status==='STOPPED'?'selected':''}>STOPPED</option><option ${p.status==='ADMIN_CANCELLED'?'selected':''}>ADMIN_CANCELLED</option></select></label><label>Admin reason<input id="q28EditReason" placeholder="Required reason"></label><div class="q28-actions"><button id="q28SaveUserPackage" class="primary">Save custom settings</button><button id="q28ResetUserDaily" class="ghost">Reset daily to master</button><button id="q28ResetUserCap" class="ghost">Reset max to master</button></div><div class="q28-danger-zone"><button data-package-status="PAUSED" class="ghost">Pause</button><button data-package-status="ACTIVE" class="ghost">Resume</button><button data-package-status="STOPPED" class="danger">Stop</button><button data-package-status="ADMIN_CANCELLED" class="danger">Cancel / remove</button></div>`);
    const reason=()=>$("q28EditReason").value.trim();
    const send=async body=>{if((body.reason||"").length<3){toast("Enter an admin reason",true);return}try{await qApi(`/admin/subscriptions/${p.id}`,{method:"PUT",body:JSON.stringify(body)});toast("Package updated and audit logged");closeModal();await loadQAdmin();await openAdminUser(user.id)}catch(e){toast(e.message,true)}};
    $("q28SaveUserPackage").onclick=()=>send({daily_rate_percent:Number($("q28EditDaily").value),cap_percent:Number($("q28EditCap").value),status:$("q28EditStatus").value,reason:reason()});
    $("q28ResetUserDaily").onclick=()=>send({clear_daily_override:true,reason:reason()});
    $("q28ResetUserCap").onclick=()=>send({clear_cap_override:true,reason:reason()});
    qsa("[data-package-status]").forEach(b=>b.onclick=()=>{const st=b.dataset.packageStatus;if(!confirm(`${st} this package?`))return;send({status:st,reason:reason()})});
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
    renderWalletMatrix();
    renderPackageMasterRules();
    renderAdminUsers();

    const pending=v28.adminPayments.filter(x=>x.status==="PENDING");
    $("q28AdminPayments").innerHTML=pending.length?pending.map(o=>qRow(
      `${escapeHtml(o.package_name)} · ${fmtQ(o.expected_usdt)} USDT · ${o.network}`,
      `${escapeHtml(o.order_code)} · User #${o.user?.id||o.user_id} · ${escapeHtml(o.user?.display_name||"")} · @${escapeHtml(o.user?.username||"")}<br>TX: ${escapeHtml(o.tx_hash||"")}`,
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
      `${dt(x.created_at)}${x.note?` · ${escapeHtml(x.note)}`:""}`,
      `${adminParty(x.from_system,x.from_user_info,x.from_user)} → ${adminParty(x.to_system,x.to_user_info,x.to_user)}`
    )).join("");

    if($("q28AdminAudit"))$("q28AdminAudit").innerHTML=(v28.adminAudit||[]).slice(0,100).map(x=>qRow(
      escapeHtml(x.action),
      `${dt(x.created_at)} · ${escapeHtml(x.reason||"")}`,
      `${x.admin?`Admin #${x.admin.id} · @${escapeHtml(x.admin.username||"")}`:""}${x.target_user?`<br>Target User #${x.target_user.id} · ${escapeHtml(x.target_user.display_name||"")} · @${escapeHtml(x.target_user.username||"")}`:""}${x.subscription_lot_id?`<br>Package #${x.subscription_lot_id}`:""}`
    )).join("")||`<div class="empty-state"><p>No admin changes logged yet.</p></div>`;

    const disputes=v28.adminMarket.filter(x=>x.status==="DISPUTED");
    $("q28AdminMarketOrders").innerHTML=disputes.length?disputes.map(o=>qRow(
      `${escapeHtml(o.order_code)} · ${fmtQ(o.total_q)} Q`,
      escapeHtml(o.dispute_note||"No dispute note"),status(o.status),
      `<button class="ghost" data-dispute-outcome="BUYER" data-id="${o.id}">Refund buyer</button><button class="primary" data-dispute-outcome="SELLER" data-id="${o.id}">Pay seller</button>`
    )).join(""):`<div class="empty-state"><p>No open disputes.</p></div>`;
    qsa("[data-dispute-outcome]").forEach(b=>b.onclick=()=>resolveDispute(Number(b.dataset.id),b.dataset.disputeOutcome));

    const cfg=a.config;
    $("q28AdminPrice").value=cfg.q_reference_usd;
    $("q28AdminFee").value=cfg.marketplace_fee_percent;
    $("q28AdminBasic").value=v28.wallet?.basic_daily_q??2;
    $("q28AdminSignup").value=v28.wallet?.signup_bonus_q??100;
    $("q28AdminReferrer").value=v28.wallet?.referral_reward_q??25;
    $("q28AdminReferred").value=25;
    const rules=Object.fromEntries((v28.adminReferralRules||[]).map(x=>[x.package_code,x.reward_q]));
    $("q28RefStarter").value=rules.STARTER_10??10;
    $("q28RefPlus").value=rules.PLUS_50??25;
    $("q28RefPro").value=rules.PRO_100??50;
    $("q28RefPremium").value=rules.PREMIUM_500??200;
    $("q28RefElite").value=rules.ELITE_1000??400;
    const ro=v28.adminReferralOverview||{};
    if($("q28AdminReferralOverview"))$("q28AdminReferralOverview").innerHTML=`<span>${ro.total_referred_users||0} referred users</span><span>${fmtQ(ro.free_signup_q||0)} Q signup rewards</span><span>${fmtQ(ro.package_paid_q||0)} Q package rewards</span>${Number(ro.package_pending_q||0)>0?`<span>${fmtQ(ro.package_pending_q)} Q pending</span>`:""}`;
  }

  async function loadQAdmin(){
    try{
      const [me,economy,wallets,walletMatrix,packageRules,users,audit,payments,ledger,market,config,wallet,roles,referralRules,referralOverview]=await Promise.all([
        qApi("/admin/me"),qApi("/admin/economy"),qApi("/admin/payment-wallets"),qApi("/admin/payment-wallet-matrix"),qApi("/admin/package-rules"),qApi("/admin/users"),qApi("/admin/audit"),qApi("/admin/payment-orders"),
        qApi("/admin/ledger"),qApi("/admin/market/orders"),qApi("/config"),qApi("/wallet"),qApi("/admin/roles"),qApi("/admin/referral-rules"),qApi("/admin/referrals")
      ]);
      v28.admin={me,economy,config};v28.adminWallets=wallets;v28.adminWalletMatrix=walletMatrix;v28.adminPackageRules=packageRules;v28.adminUsers=users;v28.adminAudit=audit;v28.adminPayments=payments;v28.adminLedger=ledger;v28.adminMarket=market;v28.wallet=wallet;v28.adminRoles=roles;v28.adminReferralRules=referralRules;v28.adminReferralOverview=referralOverview;
      renderAdmin();
    }catch(e){toast(e.message,true);setView("more")}
  }
  window.loadQAdmin=loadQAdmin;

  async function uploadWalletQr(id){
    const input=document.createElement("input");input.type="file";input.accept="image/*";
    input.onchange=async()=>{
      const file=input.files?.[0];if(!file)return;
      if(file.size>600000){toast("QR image must be under 600 KB",true);return}
      const form=new FormData();form.append("file",file);
      try{await qApi(`/admin/payment-wallets/${id}/qr`,{method:"POST",body:form});toast("Custom QR uploaded");await loadQAdmin()}catch(e){toast(e.message,true)}
    };
    input.click();
  }

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
    $("q28ListingMedia")?.addEventListener("change",selectedMediaPreview);
    $("q28CreateListing")?.addEventListener("click",async()=>{
      const title=$("q28ListingTitle").value.trim(),description=$("q28ListingDescription").value.trim(),price=Number($("q28ListingPrice").value),inventory=Number($("q28ListingInventory").value||1),files=[...($("q28ListingMedia")?.files||[])].slice(0,10);
      if(!title||!(price>0)){toast("Enter title and Q price",true);return}
      try{
        $("q28CreateListing").disabled=true;$("q28CreateListing").textContent=files.length?"Uploading…":"Listing…";
        const listing=await qApi("/market/listings",{method:"POST",body:JSON.stringify({title,description,category:"OTHER",condition:"SERVICE",price_q:price,inventory})});
        if(files.length)await uploadListingMedia(listing.id,files);
        toast("Q Market listing created");$("q28ListingTitle").value="";$("q28ListingDescription").value="";$("q28ListingPrice").value="";if($("q28ListingMedia"))$("q28ListingMedia").value="";selectedMediaPreview();await loadQEconomy();
      }catch(e){toast(e.message,true)}finally{$("q28CreateListing").disabled=false;$("q28CreateListing").textContent="List"}
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
    $("q28AdminSaveConfig")?.addEventListener("click",async()=>{
      const body={q_price_usd:Number($("q28AdminPrice").value),marketplace_fee_percent:Number($("q28AdminFee").value),basic_daily_q:Number($("q28AdminBasic").value),signup_bonus_q:Number($("q28AdminSignup").value),referral_referrer_q:Number($("q28AdminReferrer").value),referral_referred_q:Number($("q28AdminReferred").value)};
      try{await qApi("/admin/config",{method:"PUT",body:JSON.stringify(body)});toast("Q settings saved");await loadQAdmin()}catch(e){toast(e.message,true)}
    });
    $("q28AdminSaveReferralRules")?.addEventListener("click",async()=>{
      const body={starter_10_q:Number($("q28RefStarter").value),plus_50_q:Number($("q28RefPlus").value),pro_100_q:Number($("q28RefPro").value),premium_500_q:Number($("q28RefPremium").value),elite_1000_q:Number($("q28RefElite").value)};
      try{await qApi("/admin/referral-rules",{method:"PUT",body:JSON.stringify(body)});toast("Package referral rewards saved");await loadQAdmin()}catch(e){toast(e.message,true)}
    });
    $("q28AdminRefreshPayments")?.addEventListener("click",loadQAdmin);
    $("q28AdminRefreshUsers")?.addEventListener("click",loadAdminUsers);
    $("q28AdminUserSearchBtn")?.addEventListener("click",loadAdminUsers);
    $("q28AdminUserSearch")?.addEventListener("keydown",e=>{if(e.key==="Enter")loadAdminUsers()});
    $("q28TreasuryTransfer")?.addEventListener("click",async()=>{
      const body={from_wallet:$("q28TreasuryFrom").value,to_wallet:$("q28TreasuryTo").value,amount_q:Number($("q28TreasuryAmount").value),reason:$("q28TreasuryReason").value.trim()};
      if(!(body.amount_q>0)||body.reason.length<3){toast("Enter amount and reason",true);return}
      if(!confirm(`Transfer ${body.amount_q} Q between treasury wallets?`))return;
      try{await qApi("/admin/treasury/transfer",{method:"POST",body:JSON.stringify(body)});toast("Treasury transfer completed");await loadQAdmin()}catch(e){toast(e.message,true)}
    });
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",bind);else bind();
})();