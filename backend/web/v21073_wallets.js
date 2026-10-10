/* LEMMIQ V2.10.7.3 — two shared USDT wallets + QR */
(()=>{
  const LEVEL={NONE:0,READ:1,WRITE:2,FULL:3};
  const previousLoadQAdmin=window.loadQAdmin;
  let accessState=null;

  const e=x=>escapeHtml(String(x??""));

  async function getAccess(){
    if(accessState)return accessState;
    accessState=await api("/v28/admin/access/me");
    return accessState;
  }

  async function loadSharedWallets(){
    const host=document.getElementById("q28WalletMatrix");
    if(!host)return;

    let access;
    try{ access=await getAccess(); }
    catch(err){ host.innerHTML=`<p class="micro">${e(err.message||err)}</p>`; return; }

    if(LEVEL[access.permissions?.PAYMENTS||"NONE"]<LEVEL.READ){
      const article=host.closest("article");
      if(article)article.style.display="none";
      return;
    }

    const canFull=LEVEL[access.permissions?.PAYMENTS||"NONE"]>=LEVEL.FULL;
    const article=host.closest("article");
    if(article){
      const title=article.querySelector("h3");
      const note=article.querySelector("p.micro");
      if(title)title.textContent="Shared USDT receiving wallets";
      if(note)note.textContent="One TRC20 wallet and one BEP20 wallet are used across Q Starter, Q Plus, Q Pro, Q Premium and Q Elite.";
    }

    host.innerHTML='<p class="micro">Loading shared wallets…</p>';

    try{
      const rows=await api("/v28/admin/global-payment-wallets");
      host.classList.add("q21073-shared-wallets");
      host.innerHTML=rows.map(row=>walletCard(row,canFull)).join("");
      wireWalletActions(canFull);
    }catch(err){
      host.innerHTML=`<p class="micro">${e(err.message||err)}</p>`;
    }
  }

  function walletCard(row,canFull){
    const w=row.wallet;
    const fallback=row.legacy_fallback;
    const current=w||fallback;
    const inherited=!w&&!!fallback;
    const address=current?.address||"";
    const label=w?.label||`Shared USDT ${row.network} — All Q Packs`;
    const packs=(row.used_by_packages||[]).join(" · ");

    return `<div class="q21073-wallet-card" data-network="${e(row.network)}">
      <div class="section-head">
        <div>
          <span class="eyebrow">${e(row.network)}</span>
          <h4>USDT ${e(row.network)}</h4>
          <p class="micro">Used by every Q subscription pack</p>
        </div>
        <span class="q21073-status ${w?"active":(fallback?"legacy":"empty")}">${w?"Active · shared":(fallback?"Legacy wallet found":"Not set")}</span>
      </div>

      ${inherited?`<div class="q21073-notice">A previous package wallet was found. Save it below to make this address the shared ${e(row.network)} wallet for every pack.</div>`:""}

      <label>Wallet label
        <input data-wallet-label value="${e(label)}" ${canFull?"":"disabled"}>
      </label>
      <label>Public ${e(row.network)} address
        <input data-wallet-address value="${e(address)}" placeholder="Public USDT ${e(row.network)} address" ${canFull?"":"disabled"}>
      </label>

      <div class="q21073-wallet-actions">
        ${canFull?`<button class="primary" data-wallet-save>${w?"Replace / Save":"Use for all packs"}</button>`:""}
        ${current?`<button class="ghost" data-wallet-qr data-wallet-id="${current.id}">QR</button>
          <button class="ghost" data-wallet-copy data-address="${e(current.address)}">Copy</button>`:""}
        ${canFull&&w?`<label class="ghost q21073-upload">Upload QR<input type="file" accept="image/*" data-wallet-upload data-wallet-id="${w.id}" hidden></label>`:""}
      </div>

      <p class="micro q21073-packs">${e(packs)}</p>
      ${w?`<p class="micro">${w.custom_qr?"Custom QR uploaded":"QR is generated automatically from the wallet address."}</p>`:""}
    </div>`;
  }

  function wireWalletActions(canFull){
    document.querySelectorAll("#q28WalletMatrix [data-wallet-save]").forEach(btn=>{
      btn.onclick=async()=>{
        const card=btn.closest("[data-network]");
        const network=card.dataset.network;
        const address=card.querySelector("[data-wallet-address]").value.trim();
        const label=card.querySelector("[data-wallet-label]").value.trim();
        if(!address)return toast("Enter the wallet address",true);
        btn.disabled=true;btn.textContent="Saving…";
        try{
          await api(`/v28/admin/global-payment-wallets/${network}`,{
            method:"PUT",
            body:JSON.stringify({label,address,active:true})
          });
          accessState=null;
          toast(`${network} wallet now used across all packs`);
          await loadSharedWallets();
        }catch(err){
          toast(err.message||String(err),true);
          btn.disabled=false;btn.textContent="Save";
        }
      };
    });

    document.querySelectorAll("#q28WalletMatrix [data-wallet-copy]").forEach(btn=>{
      btn.onclick=async()=>{
        try{
          await navigator.clipboard.writeText(btn.dataset.address||"");
          toast("Wallet address copied");
        }catch{
          toast("Unable to copy address",true);
        }
      };
    });

    document.querySelectorAll("#q28WalletMatrix [data-wallet-qr]").forEach(btn=>{
      btn.onclick=()=>{
        const card=btn.closest("[data-network]");
        const network=card.dataset.network;
        const address=card.querySelector("[data-wallet-address]").value.trim();
        const walletId=btn.dataset.walletId;
        openModal(`<span class="eyebrow">${e(network)}</span>
          <h2>USDT ${e(network)} QR</h2>
          <p class="micro">Same receiving wallet for every LEMMIQ Q subscription pack.</p>
          <div class="q21073-qr-wrap">
            <img src="/v28/payment-wallets/${e(walletId)}/qr?t=${Date.now()}" alt="${e(network)} wallet QR">
          </div>
          <div class="q21073-address">${e(address)}</div>
          <button id="q21073QrCopy" class="primary full">Copy address</button>
          <button id="q21073QrClose" class="ghost full">Close</button>`);
        document.getElementById("q21073QrCopy").onclick=async()=>{
          await navigator.clipboard.writeText(address);toast("Wallet address copied");
        };
        document.getElementById("q21073QrClose").onclick=closeModal;
      };
    });

    document.querySelectorAll("#q28WalletMatrix [data-wallet-upload]").forEach(inp=>{
      inp.onchange=async()=>{
        const file=inp.files?.[0];if(!file)return;
        const fd=new FormData();fd.append("file",file);
        try{
          await api(`/v28/admin/payment-wallets/${inp.dataset.walletId}/qr`,{method:"POST",body:fd});
          toast("Custom QR uploaded");
          await loadSharedWallets();
        }catch(err){toast(err.message||String(err),true)}
      };
    });
  }

  window.loadQAdmin=async function(){
    await previousLoadQAdmin();
    if(document.querySelector("#view-q-admin.active")){
      accessState=null;
      await loadSharedWallets();
    }
  };

  if(location.hash==="#q-admin"&&state?.token)setTimeout(loadSharedWallets,200);
})();