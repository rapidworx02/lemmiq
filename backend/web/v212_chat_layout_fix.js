/* LEMMIQ V2.12.1 PWA chat layout. No chat/backend logic changes. */
(() => {
  "use strict";
  const mobile = window.matchMedia("(max-width: 900px)");
  let frame = 0;
  const layout = document.querySelector("#view-chats .chat-layout");
  const nav = document.querySelector(".sidebar");
  if (!layout || !nav) return;

  function sync() {
    frame = 0;
    if (!mobile.matches || !layout.classList.contains("open-chat")) {
      layout.style.removeProperty("height");
      return;
    }
    const vv = window.visualViewport;
    const viewportBottom = vv ? vv.offsetTop + vv.height : window.innerHeight;
    const navTop = nav.getBoundingClientRect().top;
    const layoutTop = layout.getBoundingClientRect().top;
    if (!Number.isFinite(navTop) || !Number.isFinite(layoutTop)) return;
    // Reserve a gap above the six-tab navigation and do not cover the keyboard.
    const bottom = Math.min(navTop, viewportBottom);
    const available = Math.round(bottom - layoutTop - 9);
    if (available > 120) {
      layout.style.setProperty("height", `${available}px`, "important");
    } else {
      // Very short visual viewport: allow a smaller chat instead of hiding the input.
      layout.style.setProperty("height", `${Math.max(86, available)}px`, "important");
    }
  }
  function schedule() {
    if (!frame) frame = window.requestAnimationFrame(sync);
  }
  const observer = new MutationObserver(schedule);
  observer.observe(layout, {attributes: true, attributeFilter: ["class"]});
  window.addEventListener("resize", schedule, {passive: true});
  window.addEventListener("orientationchange", schedule, {passive: true});
  window.addEventListener("scroll", schedule, {passive: true});
  document.addEventListener("focusin", schedule);
  document.addEventListener("focusout", schedule);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", schedule, {passive: true});
    window.visualViewport.addEventListener("scroll", schedule, {passive: true});
  }
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(schedule);
    const header = document.querySelector(".topbar");
    if (header) ro.observe(header);
    ro.observe(nav);
  }
  schedule();
})();
