/* LEMMIQ V2.10.10 — Browser app-style theme */
(()=>{
  const root=document.documentElement;
  function current(){return root.dataset.theme==="dark"?"dark":"light"}
  function apply(theme,persist=true){
    const value=theme==="dark"?"dark":"light";
    root.dataset.theme=value;
    if(persist)localStorage.setItem("lemmiq_theme",value);
    const card=document.getElementById("themeToggleCard");
    const icon=document.getElementById("themeToggleIcon");
    const title=document.getElementById("themeToggleTitle");
    if(icon)icon.textContent=value==="dark"?"☀️":"🌙";
    if(title)title.textContent=value==="dark"?"Light mode":"Dark mode";
    if(card)card.title=value==="dark"?"Switch to light mode":"Switch to dark mode";
    const meta=document.querySelector('meta[name="theme-color"]');
    if(meta)meta.setAttribute("content",value==="dark"?"#0b0e1b":"#f7f7fb");
  }
  function install(){
    apply(current(),false);
    const card=document.getElementById("themeToggleCard");
    if(card&&!card.dataset.bound){card.dataset.bound="1";card.onclick=()=>apply(current()==="dark"?"light":"dark")}
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",install);else install();
})();
