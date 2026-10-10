/* LEMMIQ V2.10.4 additive browser/PWA Q Activity */
(()=>{
  const $=id=>document.getElementById(id);
  let filter="ALL", period="TODAY", ledger=[];
  const token=()=>localStorage.getItem("lemmiq_token")||"";
  async function getLedger(){
    const r=await fetch("/v28/wallet/ledger",{headers:token()?{"Authorization":`Bearer ${token()}`}:{}});
    if(!r.ok)throw new Error(`Q activity HTTP ${r.status}`);
    return await r.json();
  }
  const esc=s=>String(s??"").replace(/[&<>\"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'\"':"&quot;","'":"&#39;"}[c]));
  const num=v=>{const n=Number(v||0);return n.toLocaleString(undefined,{maximumFractionDigits:6})};
  function title(x){return String(x.feature_key||x.kind||"Q activity").replaceAll("_"," ")}
  function inPeriod(x){
    if(period==="ALL")return true;
    const d=new Date(x.created_at||0);if(Number.isNaN(d.getTime()))return false;
    const now=new Date(),start=new Date(now);
    if(period==="TODAY")start.setHours(0,0,0,0);
    else if(period==="WEEK"){start.setDate(now.getDate()-7);start.setHours(0,0,0,0)}
    else if(period==="MONTH"){start.setMonth(now.getMonth()-1);start.setHours(0,0,0,0)}
    else if(period==="YEAR"){start.setFullYear(now.getFullYear()-1);start.setHours(0,0,0,0)}
    return d>=start && d<=now;
  }
  function render(){
    const list=$("q2104ActivityList"),summary=$("q2104ActivitySummary"); if(!list||!summary)return;
    const scoped=ledger.filter(inPeriod);
    const incoming=scoped.filter(x=>String(x.direction).toUpperCase()==="IN").reduce((a,x)=>a+Number(x.amount_q||0),0);
    const outgoing=scoped.filter(x=>String(x.direction).toUpperCase()==="OUT").reduce((a,x)=>a+Number(x.amount_q||0),0);
    const feature=scoped.filter(x=>x.feature_key||String(x.kind||"").includes("FEATURE")).length;
    summary.innerHTML=`<div class="stat"><strong>+${num(incoming)} Q</strong><span>Incoming</span></div><div class="stat"><strong>−${num(outgoing)} Q</strong><span>Outgoing</span></div><div class="stat"><strong>${feature}</strong><span>Feature uses</span></div>`;
    const rows=scoped.filter(x=>filter==="ALL"||String(x.direction).toUpperCase()===filter);
    list.innerHTML=rows.length?rows.map(x=>{
      const dir=String(x.direction||"").toUpperCase(), amount=Number(x.amount_q||0);
      const cls=amount===0?"q2104-q-zero":dir==="IN"?"q2104-q-in":"q2104-q-out";
      const label=amount===0?"0 Q":`${dir==="IN"?"+":"−"}${num(amount)} Q`;
      return `<div class="q2104-activity-row"><div class="body"><strong>${esc(title(x))}</strong><small>${esc(x.note||x.reference||"")}</small><small>${esc(String(x.created_at||"").replace("T"," ").slice(0,19))}</small></div><span class="${cls}">${label}</span></div>`
    }).join(""):`<p class="micro">No Q activity in this view yet.</p>`;
  }
  async function load(){try{ledger=await getLedger();render()}catch(e){const el=$("q2104ActivityList");if(el)el.innerHTML=`<p class="micro">${esc(e.message)}</p>`}}
  function bind(){
    document.querySelectorAll("[data-q2104-filter]").forEach(b=>b.addEventListener("click",()=>{filter=b.dataset.q2104Filter;document.querySelectorAll("[data-q2104-filter]").forEach(x=>x.classList.toggle("active",x===b));render()}));
    document.querySelectorAll("[data-q2106-period]").forEach(b=>b.addEventListener("click",()=>{period=b.dataset.q2106Period;document.querySelectorAll("[data-q2106-period]").forEach(x=>x.classList.toggle("active",x===b));render()}));
    $("q2104RefreshActivity")?.addEventListener("click",load);
    document.querySelector('[data-q28-tab="activity"]')?.addEventListener("click",load);
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",bind);else bind();
})();
