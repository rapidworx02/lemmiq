(()=>{
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]));
const sections=["OVERVIEW","USERS","Q_ECONOMY","Q_USAGE","Q_FEATURE_PRICING","Q_PREDICT","MARKETPLACE","PAYMENTS","PACKAGES_REFERRALS","NOTIFICATIONS_SUPPORT","TRUST_BUSINESS","CALLS_MEETINGS","SYSTEM_SETTINGS","AUDIT_LOGS","ADMIN_TEAM"];
let selected=null;

async function japi(path,opts={}){return await api(path,opts)}
function renderPermEditor(data){
  selected=data.user;
  $("q2108AdminIdentity").innerHTML=`<strong>${esc(data.user.display_name)}</strong> · @${esc(data.user.username)} · ${esc(data.role||"No admin role")}`;
  $("q2108BaseRole").value=(data.role&&data.role!=="MASTER_ADMIN")?data.role:"SUPPORT_ADMIN";
  $("q2108PermissionEditor").innerHTML=`<div class="q2108-perm-grid">${sections.filter(s=>s!=="ADMIN_TEAM").map(sec=>`<div class="q2108-perm-row"><label>${esc(sec.replaceAll("_"," "))}</label><select data-sec="${sec}">${["NONE","READ","WRITE","FULL"].map(x=>`<option ${data.permissions?.[sec]===x?"selected":""}>${x}</option>`).join("")}</select></div>`).join("")}<div class="q2108-perm-row"><label>ADMIN TEAM</label><select disabled><option>MASTER ADMIN ONLY</option></select></div></div>`;
}
async function findUser(){
  const q=$("q2108AdminUser")?.value.trim();if(!q)return;
  try{renderPermEditor(await japi(`/v2108/admin/access/search?username=${encodeURIComponent(q)}`))}
  catch(e){toast(e.message,true)}
}
async function saveAccess(){
  if(!selected)return toast("Find a user first",true);
  const permissions=[...document.querySelectorAll("#q2108PermissionEditor [data-sec]")].map(x=>({section_key:x.dataset.sec,access_level:x.value}));
  permissions.push({section_key:"ADMIN_TEAM",access_level:"NONE"});
  const risky=permissions.filter(x=>["WRITE","FULL"].includes(x.access_level)).length;
  if(risky&&!confirm(`Grant ${risky} Write/Full section permission(s) to @${selected.username}?`))return;
  try{
    await japi("/v2108/admin/access",{method:"PUT",body:JSON.stringify({username:selected.username,base_role:$("q2108BaseRole").value,active:true,permissions})});
    toast("Admin access updated");await loadAccessList();
  }catch(e){toast(e.message,true)}
}
async function loadAccessList(){
  if(!$("q2108AccessList"))return;
  try{
    const d=await japi("/v2108/admin/access");
    $("q2108AccessList").innerHTML=d.items.map(x=>`<div class="q28-row"><strong>${esc(x.display_name)} · @${esc(x.username)}</strong><small>${esc(x.role)} · ${Object.entries(x.permissions).filter(([k,v])=>v!=="NONE").map(([k,v])=>`${k}:${v}`).join(" · ")||"No section access"}</small></div>`).join("")||`<p class="micro">No support admins configured.</p>`;
  }catch(e){$("q2108AccessList").innerHTML=`<p class="micro">${esc(e.message)}</p>`}
}
async function loadUsage(){
  if(!$("q2108UsageUsers"))return;
  const p=$("q2108UsagePeriod").value,u=$("q2108UsageUser").value.trim(),f=$("q2108UsageFeature").value.trim();
  try{
    const d=await japi(`/v2108/admin/q-usage?period=${encodeURIComponent(p)}&username=${encodeURIComponent(u)}&feature=${encodeURIComponent(f)}`);
    const s=d.summary;
    $("q2108UsageSummary").innerHTML=[["Active users",s.active_users],["AI/Q actions",s.total_actions],["Average/user",s.avg_actions_per_user],["Median",s.median_actions],["P90",s.p90],["P95",s.p95],["Provider cost",`US$${Number(s.provider_cost_usd).toFixed(4)}`],["Simulated Q",`${s.simulated_q} Q`]].map(([a,b])=>`<div><small>${a}</small><strong>${b}</strong></div>`).join("");
    $("q2108FeatureTotals").innerHTML=`<h4>Feature usage</h4>`+Object.entries(s.feature_totals||{}).map(([k,v])=>`<span class="q2108-feature-chip">${esc(k)} · ${v}</span>`).join("");
    $("q2108UsageUsers").innerHTML=d.users.map(x=>`<div class="q2108-user-usage"><strong>${esc(x.display_name)} · @${esc(x.username)}</strong><div class="meta"><span>${esc(x.tier)}</span><span>${x.actions} actions</span><span>${x.avg_actions_per_day}/day</span><span>Sim ${x.simulated_q} Q</span><span>Cost US$${Number(x.provider_cost_usd).toFixed(4)}</span><span>${x.failed} failed</span></div><div>${Object.entries(x.features||{}).map(([k,v])=>`<span class="q2108-feature-chip">${esc(k)} ${v}</span>`).join("")}</div></div>`).join("")||`<p class="micro">No usage in this period.</p>`;
  }catch(e){$("q2108UsageUsers").innerHTML=`<p class="micro">${esc(e.message)}</p>`}
}
function usageCsv(){
  const p=$("q2108UsagePeriod").value;
  fetch(`/v2108/admin/q-usage/export.csv?period=${encodeURIComponent(p)}`,{headers:authHeaders()}).then(r=>{if(!r.ok)throw new Error("Export failed");return r.blob()}).then(b=>{const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download=`lemmiq-q-usage-${p}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}).catch(e=>toast(e.message,true));
}

async function renderWalletMatrix2108(){
  const host=$("q28WalletMatrix");if(!host)return;
  try{
    const items=await japi("/v28/admin/payment-wallet-matrix");
    host.innerHTML=items.map(x=>{const w=x.wallet||{};return `<div class="q28-wallet-slot" data-slot="${esc(x.slot_key)}"><div class="section-head"><strong>${esc(x.package_name)} · ${esc(x.network)}</strong><span>${w.active?"Active":"Not set"}</span></div><input data-label value="${esc(w.label||`${x.package_name} ${x.network}`)}"><input data-address placeholder="Public USDT ${esc(x.network)} address" value="${esc(w.address||"")}"><div class="q2108-qr-actions"><button class="primary" data-save>Save / Replace</button>${w.id?`<button class="ghost" data-qr="${w.id}">QR</button><label class="ghost">Upload QR<input type="file" accept="image/*" data-upload="${w.id}" hidden></label><button class="ghost" data-copy="${esc(w.address||"")}">Copy</button>`:`<button class="ghost" disabled>QR after address</button>`}</div></div>`}).join("");
    host.querySelectorAll("[data-save]").forEach(b=>b.onclick=async()=>{const c=b.closest("[data-slot]"),[code,network]=c.dataset.slot.split(":"),address=c.querySelector("[data-address]").value.trim(),label=c.querySelector("[data-label]").value.trim();try{await japi(`/v28/admin/payment-wallet-matrix/${code}/${network}`,{method:"PUT",body:JSON.stringify({label,address,active:true})});toast("Wallet saved");renderWalletMatrix2108()}catch(e){toast(e.message,true)}});
    host.querySelectorAll("[data-qr]").forEach(b=>b.onclick=()=>window.open(`/v28/payment-wallets/${b.dataset.qr}/qr`,"_blank"));
    host.querySelectorAll("[data-copy]").forEach(b=>b.onclick=()=>navigator.clipboard.writeText(b.dataset.copy).then(()=>toast("Address copied")));
    host.querySelectorAll("[data-upload]").forEach(inp=>inp.onchange=async()=>{const f=inp.files?.[0];if(!f)return;const fd=new FormData();fd.append("file",f);try{await japi(`/v28/admin/payment-wallets/${inp.dataset.upload}/qr`,{method:"POST",body:fd});toast("QR uploaded");renderWalletMatrix2108()}catch(e){toast(e.message,true)}});
  }catch(e){}
}

let adminLoadPromise=null;
async function loadV2108Admin(force=false){
  if(!document.querySelector("#view-q-admin.active") && !force) return;
  if(adminLoadPromise) return adminLoadPromise;

  adminLoadPromise=(async()=>{
    // Load each panel independently: one denied section must not collapse Q Admin.
    await Promise.allSettled([
      loadAccessList(),
      renderWalletMatrix2108(),
      loadUsage()
    ]);
  })();

  try{ await adminLoadPromise; }
  finally{ adminLoadPromise=null; }
}
window.loadV2108Admin=loadV2108Admin;

document.addEventListener("DOMContentLoaded",()=>{
  $("q2108FindAdminUser")?.addEventListener("click",findUser);
  $("q2108SaveAccess")?.addEventListener("click",saveAccess);
  $("q2108UsageLoad")?.addEventListener("click",loadUsage);
  $("q2108UsageCsv")?.addEventListener("click",usageCsv);

  // Do not observe every class change. V2.10.8 previously caused repeated
  // Q Admin reloads while legacy admin renderers toggled classes.
  if(document.querySelector("#view-q-admin.active")) loadV2108Admin(true);
});
})();