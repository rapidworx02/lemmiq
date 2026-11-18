/* V21362_REFERRAL_LINKS — referral invitations for LEMMIQ, no Q accounting changes. */
(()=>{
  'use strict';
  const BASE='https://app.lemmiq.com/web/';
  const $=id=>document.getElementById(id);
  const normalize=x=>String(x??'').trim().toUpperCase();
  const valid=code=>/^Q[1-9]\d*-[A-F0-9]{6}$/.test(code);
  const makeLink=code=>BASE+'?ref='+encodeURIComponent(code);
  let latest='';
  const note=(msg,error=false)=>{const el=$('q28ReferralLinkStatus');if(el){el.textContent=msg;el.style.color=error?'#fca5a5':''}};

  function refresh(code){
    const normalized=normalize(code);
    latest=valid(normalized)?normalized:'';
    const url=latest?makeLink(latest):'';
    const input=$('q28ReferralLink');if(input)input.value=url;
    for(const id of ['q28CopyReferralLink','q28ShareReferralLink']){
      const button=$(id);if(button)button.disabled=!latest;
    }
  }
  async function copy(){
    const link=latest?makeLink(latest):'';
    if(!link){note('Referral link unavailable. Reload Q Wallet and try again.',true);return}
    try{
      if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(link);
      else {
        const field=$('q28ReferralLink');if(!field)throw Error('Copy not supported');
        field.focus();field.select();
        if(!document.execCommand('copy'))throw Error('Copy not supported');
        field.setSelectionRange(0,0);
      }
      note('Referral link copied. Share it with new LEMMIQ users.');
    }catch(e){note('Unable to copy automatically. Select the link and copy it manually.',true)}
  }
  async function share(){
    if(!latest)return;
    const url=makeLink(latest);
    if(!navigator.share){await copy();return}
    try{await navigator.share({title:'Join LEMMIQ',text:'Join me on LEMMIQ using my referral invitation.',url})}
    catch(e){if(e?.name!=='AbortError')note('Could not open sharing. Use Copy Link instead.',true)}
  }
  function applyIncoming(){
    const params=new URLSearchParams(location.search);
    const raw=params.get('ref')||params.get('referral');
    if(!raw || localStorage.getItem('lemmiq_token'))return;
    const tab=$('registerTab'),field=$('regReferral');
    if(!tab||!field)return;
    tab.click();
    const code=normalize(raw);
    let status=$('v21362SignupReferralStatus');
    if(!status){status=document.createElement('small');status.id='v21362SignupReferralStatus';status.className='v21362-signup-note';field.parentElement.appendChild(status)}
    if(valid(code)){
      field.value=code;
      status.textContent='Invitation applied. The referral is verified when your account is created.';
    }else{
      field.value='';
      status.textContent='This referral link is invalid. Ask the sender for a new invitation.';
      status.style.color='#fca5a5';
    }
  }
  function start(){
    $('q28CopyReferralLink')?.addEventListener('click',copy);
    $('q28ShareReferralLink')?.addEventListener('click',share);
    applyIncoming();
    refresh($('q28ReferralCode')?.textContent||'');
  }
  window.LEMMIQReferralLinksV21362={refresh};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
