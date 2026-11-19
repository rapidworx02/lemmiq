/* LEM-012 - bottom More tab always returns from Notification Management to More home. */
(()=>{'use strict';document.addEventListener('DOMContentLoaded',()=>{
 const moreButton=document.querySelector('#nav button[data-view="more"]');
 if(moreButton)moreButton.addEventListener('click',()=>{
   const list=document.querySelector('#view-more .more-grid');const detail=document.getElementById('v2138NotificationDetail');
   if(list)list.hidden=false;if(detail)detail.hidden=true;
 },true);
 document.body.addEventListener('click',e=>{
   if(e.target.closest('#v2138NotifOpen'))return;
   const view=e.target.closest('[data-more-view]');
   if(view){const list=document.querySelector('#view-more .more-grid'),detail=document.getElementById('v2138NotificationDetail');
     if(list)list.hidden=false;if(detail)detail.hidden=true;}
 },true)
})})();
