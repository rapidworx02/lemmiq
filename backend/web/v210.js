/* LEMMIQ V2.10 additive UX patch.
   Load AFTER app.js. This file intentionally avoids replacing V2.9 logic. */
(() => {
  'use strict';

  const VERSION = '2.10.0';
  const state = {
    observer: null,
    taggedImages: new WeakSet(),
    qAnalyseBusy: false,
    media: { scale: 1, x: 0, y: 0, pointers: new Map(), lastTap: 0 }
  };

  const txt = (el) => (el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim();
  const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const all = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function visible(el) {
    if (!el || !(el instanceof Element)) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  }

  function clickByText(labels, root = document) {
    const wants = labels.map(norm);
    const candidates = all('button, a, [role="button"], [data-route], [tabindex]', root).filter(visible);
    for (const el of candidates) {
      const t = norm(txt(el));
      if (wants.some(w => t === w || t.includes(w))) {
        el.click();
        return true;
      }
    }
    return false;
  }

  function findCommonParent(elements) {
    if (!elements.length) return null;
    let p = elements[0].parentElement;
    while (p && p !== document.body) {
      if (elements.every(el => p.contains(el))) return p;
      p = p.parentElement;
    }
    return null;
  }

  function findElementsByExactText(labels, root = document) {
    const wants = labels.map(norm);
    return all('button, a, [role="button"], span, div', root).filter(el => {
      const t = norm(txt(el));
      return wants.includes(t);
    });
  }

  function ensureBottomSafeArea() {
    document.body.classList.add('v210-mobile-nav-safe');

    const navCandidates = all('nav, [class*="bottom"], [class*="nav"], [role="navigation"]')
      .filter(visible)
      .filter(el => {
        const t = norm(txt(el));
        return t.includes('chats') && t.includes('updates') && t.includes('q economy') && t.includes('q predict') && t.includes('calls');
      });

    const nav = navCandidates.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top)[0];
    if (!nav) return;

    nav.classList.add('v210-bottom-nav');

    if (!norm(txt(nav)).includes('more')) {
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'v210-more-tab';
      more.setAttribute('aria-label', 'More');
      more.innerHTML = '<span class="v210-more-icon">•••</span><span class="v210-more-label">More</span>';
      more.addEventListener('click', openMoreSheet);
      nav.appendChild(more);
    }
  }

  function ensureMoreSheet() {
    if (document.getElementById('v210-more-backdrop')) return;
    const bd = document.createElement('div');
    bd.id = 'v210-more-backdrop';
    bd.setAttribute('aria-hidden', 'true');
    bd.innerHTML = `
      <section id="v210-more-sheet" role="dialog" aria-modal="true" aria-label="More">
        <div class="v210-sheet-handle"></div>
        <div class="v210-sheet-title">More</div>
        <div class="v210-more-grid">
          <button class="v210-more-action" data-v210-dest="profile">👤 Profile</button>
          <button class="v210-more-action" data-v210-dest="trust">🛡️ Trust / Fact Check</button>
          <button class="v210-more-action" data-v210-dest="business">💼 Business Agent</button>
          <button class="v210-more-action" data-v210-dest="activity">📊 Activity</button>
          <button class="v210-more-action" data-v210-dest="money">💳 Money</button>
          <button class="v210-more-action" data-v210-dest="settings">⚙️ Settings</button>
          <button class="v210-more-action" data-v210-dest="privacy">🔒 Privacy & Security</button>
          <button class="v210-more-action" data-v210-dest="download">📱 Get LEMMIQ for Android</button>
        </div>
      </section>`;

    bd.addEventListener('click', (e) => {
      if (e.target === bd) closeMoreSheet();
      const btn = e.target.closest('[data-v210-dest]');
      if (btn) navigateMore(btn.dataset.v210Dest);
    });
    document.body.appendChild(bd);
  }

  function openMoreSheet() {
    ensureMoreSheet();
    const bd = document.getElementById('v210-more-backdrop');
    bd?.classList.add('v210-open');
    bd?.setAttribute('aria-hidden', 'false');
  }

  function closeMoreSheet() {
    const bd = document.getElementById('v210-more-backdrop');
    bd?.classList.remove('v210-open');
    bd?.setAttribute('aria-hidden', 'true');
  }

  const moreDestinations = {
    profile: { labels: ['Profile', 'Me'], hashes: ['#profile', '#me'] },
    trust: { labels: ['Trust', 'Fact Check', 'Trust / Fact Check'], hashes: ['#trust', '#fact-check'] },
    business: { labels: ['Business Agent', 'Business'], hashes: ['#business', '#business-agent'] },
    activity: { labels: ['Activity'], hashes: ['#activity'] },
    money: { labels: ['Money'], hashes: ['#money'] },
    settings: { labels: ['Settings'], hashes: ['#settings'] },
    privacy: { labels: ['Privacy & Security', 'Privacy', 'Security'], hashes: ['#privacy', '#security'] },
    download: { labels: ['Get LEMMIQ for Android', 'Download Android', 'Android app'], hashes: ['#download', '#android'] }
  };

  function navigateMore(dest) {
    closeMoreSheet();
    const cfg = moreDestinations[dest];
    if (!cfg) return;

    // Reuse an existing V2.9 menu/route when one exists; this keeps current routing authoritative.
    const existing = all('button, a, [role="button"], [data-route]').filter(el => !el.closest('#v210-more-backdrop'));
    const wants = cfg.labels.map(norm);
    const match = existing.find(el => {
      const t = norm(txt(el));
      return wants.some(w => t === w || t.includes(w));
    });
    if (match) {
      match.click();
      return;
    }

    // Hash fallback for installations where these screens are router-backed but hidden from navigation.
    if (cfg.hashes?.[0]) location.hash = cfg.hashes[0];
  }

  function removeHiddenQFooterLink() {
    all('a, button, [role="button"], div, span').forEach(el => {
      if (norm(txt(el)) === 'profile, trust, business & settings') {
        const actionable = el.closest('a,button,[role="button"]') || el;
        actionable.style.display = 'none';
        actionable.setAttribute('aria-hidden', 'true');
      }
    });
  }

  function tagQFab() {
    all('button, [role="button"], a').filter(visible).forEach(el => {
      if (norm(txt(el)) !== 'q') return;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const isRoundish = Math.abs(r.width - r.height) < 18 && r.width >= 44 && r.width <= 100;
      const isFloating = cs.position === 'fixed' || cs.position === 'absolute' || r.right > innerWidth - 120;
      if (isRoundish && isFloating) {
        el.classList.add('v210-q-fab');
        if (cs.position === 'fixed') el.classList.add('v210-q-fab-fixed');
      }
    });
  }

  function tagResponsivePages() {
    const bodyText = norm(txt(document.body));

    if (bodyText.includes('predict what happens next') || bodyText.includes('lemmiq q predict')) {
      const marker = all('h1,h2,h3,div,span').find(el => /predict what happens next/i.test(txt(el)));
      const page = marker?.closest('main, section, [class*="page"], [class*="screen"], [role="main"]') || marker?.parentElement?.parentElement || document.body;
      page.classList.add('v210-qpredict-page');

      // Category chip rail.
      const labels = ['Trending', 'CRYPTO', 'ECONOMY', 'Tech & AI', 'SPORTS'];
      const chipEls = [];
      labels.forEach(label => {
        const el = findElementsByExactText([label], page).find(visible);
        if (el) chipEls.push(el.closest('button,a,[role="button"]') || el);
      });
      const chipRail = findCommonParent(chipEls.slice(0, 3));
      if (chipRail) chipRail.classList.add('v210-chip-rail');

      // Market cards and their nearest grid.
      const cardCandidates = all('article, [class*="card"], [class*="market"], section, div', page)
        .filter(el => {
          const t = norm(txt(el));
          if (t.length < 25 || t.length > 1200) return false;
          return (t.includes('predictors') || t.includes('predictor')) && (t.includes('closes') || t.includes('% yes') || t.includes('% no'));
        })
        .filter(el => !el.querySelector('.v210-qpredict-card'));

      // Choose the smallest matching wrappers to avoid tagging the whole page.
      const cards = cardCandidates.filter(el => !cardCandidates.some(other => other !== el && el.contains(other)));
      cards.forEach(c => c.classList.add('v210-qpredict-card'));
      const grid = findCommonParent(cards.slice(0, Math.min(cards.length, 4)));
      if (grid && grid !== page) grid.classList.add('v210-qpredict-market-grid');

      // Top toolbar with title/download/menu/refresh.
      const titleNode = all('button,a,div,span').find(el => norm(txt(el)) === 'q predict');
      if (titleNode) {
        const toolbar = titleNode.closest('header,nav,[class*="toolbar"],[class*="header"]') || titleNode.parentElement;
        toolbar?.classList.add('v210-responsive-toolbar');
      }
    }

    if (bodyText.includes('q economy')) {
      const marker = all('h1,h2,h3,div,span').find(el => norm(txt(el)) === 'q economy');
      const page = marker?.closest('main, section, [class*="page"], [class*="screen"], [role="main"]') || marker?.parentElement?.parentElement;
      page?.classList.add('v210-qeconomy-page');

      const labels = ['Wallet', 'Packages', 'Market', 'Refer', 'Refer & Earn'];
      const tabs = [];
      labels.forEach(label => {
        const el = findElementsByExactText([label], page || document).find(visible);
        if (el) tabs.push(el.closest('button,a,[role="button"]') || el);
      });
      const rail = findCommonParent(tabs.slice(0, 3));
      rail?.classList.add('v210-scroll-tabs');
    }
  }

  function isLikelyChatPhoto(img) {
    if (!img || !visible(img)) return false;
    const src = img.currentSrc || img.src || '';
    if (!src) return false;
    const r = img.getBoundingClientRect();
    if (r.width < 110 || r.height < 90) return false;

    const near = img.closest('[class*="message"], [class*="bubble"], article, li, [data-message-id], [role="listitem"]');
    const nearText = norm(txt(near || img.parentElement));
    if (nearText.includes('ask q vision')) return true;
    if (near) return true;

    // Exclude obvious avatars/logos.
    const alt = norm(img.alt);
    if (alt.includes('avatar') || alt.includes('profile') || alt.includes('logo')) return false;
    return img.naturalWidth >= 300 && img.naturalHeight >= 200;
  }

  function tagChatPhotos() {
    all('img').forEach(img => {
      if (state.taggedImages.has(img) || !isLikelyChatPhoto(img)) return;
      state.taggedImages.add(img);
      img.classList.add('v210-chat-image');
      const wrap = img.closest('[class*="bubble"], [class*="message"], article, li') || img.parentElement;
      wrap?.classList.add('v210-chat-image-wrap');
      img.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openMediaViewer(img.currentSrc || img.src, img.alt || 'Chat photo');
      });
    });
  }

  function ensureMediaViewer() {
    if (document.getElementById('v210-media-viewer')) return;
    const v = document.createElement('div');
    v.id = 'v210-media-viewer';
    v.setAttribute('aria-hidden', 'true');
    v.innerHTML = `
      <button id="v210-media-close" type="button" aria-label="Close">×</button>
      <div id="v210-media-stage">
        <img id="v210-media-img" alt="Chat photo" draggable="false" />
      </div>`;
    document.body.appendChild(v);

    document.getElementById('v210-media-close')?.addEventListener('click', closeMediaViewer);
    const stage = document.getElementById('v210-media-stage');
    const image = document.getElementById('v210-media-img');

    stage.addEventListener('dblclick', (e) => {
      e.preventDefault();
      state.media.scale = state.media.scale > 1.1 ? 1 : 2.4;
      if (state.media.scale === 1) { state.media.x = 0; state.media.y = 0; }
      applyMediaTransform();
    });

    stage.addEventListener('wheel', (e) => {
      e.preventDefault();
      const next = Math.max(1, Math.min(5, state.media.scale + (e.deltaY < 0 ? 0.25 : -0.25)));
      state.media.scale = next;
      if (next === 1) { state.media.x = 0; state.media.y = 0; }
      applyMediaTransform();
    }, { passive: false });

    stage.addEventListener('pointerdown', (e) => {
      stage.setPointerCapture?.(e.pointerId);
      state.media.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, px: e.clientX, py: e.clientY });
    });

    stage.addEventListener('pointermove', (e) => {
      const p = state.media.pointers.get(e.pointerId);
      if (!p) return;
      const pointers = Array.from(state.media.pointers.values());
      if (pointers.length === 1 && state.media.scale > 1) {
        state.media.x += e.clientX - p.x;
        state.media.y += e.clientY - p.y;
        p.x = e.clientX; p.y = e.clientY;
        applyMediaTransform();
      } else if (pointers.length === 2) {
        const ids = Array.from(state.media.pointers.keys());
        const a = state.media.pointers.get(ids[0]);
        const b = state.media.pointers.get(ids[1]);
        if (!a || !b) return;
        const oldDist = Math.hypot(a.x - b.x, a.y - b.y) || 1;
        p.x = e.clientX; p.y = e.clientY;
        const newDist = Math.hypot(a.x - b.x, a.y - b.y) || 1;
        state.media.scale = Math.max(1, Math.min(5, state.media.scale * (newDist / oldDist)));
        applyMediaTransform();
      }
    });

    const end = (e) => state.media.pointers.delete(e.pointerId);
    stage.addEventListener('pointerup', end);
    stage.addEventListener('pointercancel', end);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && v.classList.contains('v210-open')) closeMediaViewer();
    });
  }

  function applyMediaTransform() {
    const image = document.getElementById('v210-media-img');
    if (!image) return;
    image.style.transform = `translate(${state.media.x}px, ${state.media.y}px) scale(${state.media.scale})`;
  }

  function openMediaViewer(src, alt) {
    ensureMediaViewer();
    state.media.scale = 1; state.media.x = 0; state.media.y = 0; state.media.pointers.clear();
    const v = document.getElementById('v210-media-viewer');
    const image = document.getElementById('v210-media-img');
    if (!v || !image) return;
    image.src = src;
    image.alt = alt || 'Chat photo';
    applyMediaTransform();
    v.classList.add('v210-open');
    v.setAttribute('aria-hidden', 'false');
  }

  function closeMediaViewer() {
    const v = document.getElementById('v210-media-viewer');
    v?.classList.remove('v210-open');
    v?.setAttribute('aria-hidden', 'true');
  }

  function ensureQAnalyseSheet() {
    if (document.getElementById('v210-qanalyse-backdrop')) return;
    const bd = document.createElement('div');
    bd.id = 'v210-qanalyse-backdrop';
    bd.setAttribute('aria-hidden', 'true');
    bd.innerHTML = `
      <section id="v210-qanalyse-sheet" role="dialog" aria-modal="true" aria-label="Q market analysis">
        <div class="v210-sheet-handle"></div>
        <div class="v210-sheet-title">Q · Analyse this market</div>
        <div id="v210-qanalyse-status" class="v210-qanalyse-status">Ready</div>
        <div id="v210-qanalyse-body" class="v210-qanalyse-body"></div>
        <div id="v210-qanalyse-sources" class="v210-qanalyse-sources"></div>
        <div id="v210-qanalyse-disclaimer" class="v210-qanalyse-disclaimer" style="display:none"></div>
      </section>`;
    bd.addEventListener('click', e => { if (e.target === bd) closeQAnalyseSheet(); });
    document.body.appendChild(bd);
  }

  function openQAnalyseSheet() {
    ensureQAnalyseSheet();
    const bd = document.getElementById('v210-qanalyse-backdrop');
    bd?.classList.add('v210-open');
    bd?.setAttribute('aria-hidden', 'false');
  }

  function closeQAnalyseSheet() {
    const bd = document.getElementById('v210-qanalyse-backdrop');
    bd?.classList.remove('v210-open');
    bd?.setAttribute('aria-hidden', 'true');
  }

  function findMarketContainer(button) {
    return button.closest('[role="dialog"], dialog, [class*="modal"], [class*="sheet"], [class*="market"], article, section') || button.parentElement?.parentElement || document.body;
  }

  function extractMarketContext(button) {
    const root = findMarketContainer(button);
    const raw = txt(root);
    const lines = (root.innerText || '').split(/\n+/).map(s => s.trim()).filter(Boolean);

    const question = lines.find(l => /\?$/.test(l) && l.length > 12) ||
      lines.find(l => /\bwill\b/i.test(l) && l.length > 12) || '';

    const yesMatch = raw.match(/YES\s*(\d+(?:\.\d+)?)%/i) || raw.match(/(\d+(?:\.\d+)?)%\s*YES/i);
    const noMatch = raw.match(/NO\s*(\d+(?:\.\d+)?)%/i) || raw.match(/(\d+(?:\.\d+)?)%\s*NO/i);
    const predictorsMatch = raw.match(/([\d,]+)\s*predictors?/i);
    const sourceMatch = raw.match(/Source\s*:\s*([^\n]+)/i);
    const closesMatch = raw.match(/Closes?\s*([^\n]+)/i);

    let resolutionRule = '';
    const rIdx = lines.findIndex(l => /^resolution$/i.test(l));
    if (rIdx >= 0) resolutionRule = lines.slice(rIdx + 1, rIdx + 4).join(' ');

    return {
      question: question || raw.slice(0, 500),
      yes_percent: yesMatch ? Number(yesMatch[1]) : null,
      no_percent: noMatch ? Number(noMatch[1]) : null,
      predictor_count: predictorsMatch ? Number(predictorsMatch[1].replace(/,/g, '')) : null,
      close_time: closesMatch ? closesMatch[1].trim() : null,
      resolution_rule: resolutionRule || null,
      resolution_source: sourceMatch ? sourceMatch[1].trim() : null,
      user_position: null,
      visible_context: raw.slice(0, 3200)
    };
  }

  function getAuthHeader() {
    const keys = ['access_token', 'token', 'authToken', 'jwt', 'lemmiq_token'];
    for (const key of keys) {
      const value = localStorage.getItem(key) || sessionStorage.getItem(key);
      if (value && value.length > 20) return { Authorization: value.startsWith('Bearer ') ? value : `Bearer ${value}` };
    }
    return {};
  }

  async function analyseMarket(button) {
    if (state.qAnalyseBusy) return;
    state.qAnalyseBusy = true;
    openQAnalyseSheet();

    const status = document.getElementById('v210-qanalyse-status');
    const bodyEl = document.getElementById('v210-qanalyse-body');
    const sourcesEl = document.getElementById('v210-qanalyse-sources');
    const disclaimerEl = document.getElementById('v210-qanalyse-disclaimer');
    if (status) status.textContent = 'Q is analysing the market…';
    if (bodyEl) bodyEl.textContent = '';
    if (sourcesEl) sourcesEl.innerHTML = '';
    if (disclaimerEl) disclaimerEl.style.display = 'none';

    try {
      const context = extractMarketContext(button);
      const resp = await fetch('/v210/q-predict/analyse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify(context)
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || `Q analysis failed (${resp.status})`);

      if (status) status.textContent = data.used_live_context ? 'Analysis includes current web context' : 'Analysis based on market context';
      if (bodyEl) bodyEl.textContent = data.analysis || 'No analysis returned.';

      if (sourcesEl && Array.isArray(data.live_sources) && data.live_sources.length) {
        sourcesEl.innerHTML = '<strong>Current sources</strong>';
        const list = document.createElement('div');
        data.live_sources.forEach(s => {
          if (!s.url) return;
          const p = document.createElement('div');
          const a = document.createElement('a');
          a.href = s.url;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          a.textContent = s.title || s.url;
          p.appendChild(a);
          list.appendChild(p);
        });
        sourcesEl.appendChild(list);
      }

      if (disclaimerEl && data.disclaimer) {
        disclaimerEl.textContent = data.disclaimer;
        disclaimerEl.style.display = 'block';
      }
    } catch (err) {
      if (status) status.textContent = 'Could not analyse this market';
      if (bodyEl) bodyEl.textContent = `${err?.message || err}\n\nTap “Q · Analyse this market” again to retry.`;
    } finally {
      state.qAnalyseBusy = false;
    }
  }

  function attachAnalyseHandler() {
    if (document.documentElement.dataset.v210AnalyseAttached === '1') return;
    document.documentElement.dataset.v210AnalyseAttached = '1';
    document.addEventListener('click', e => {
      const button = e.target.closest('button, a, [role="button"]');
      if (!button) return;
      const t = norm(txt(button));
      if (t.includes('analyse this market') || t.includes('analyze this market')) {
        e.preventDefault();
        e.stopPropagation();
        analyseMarket(button);
      }
    }, true);
  }

  function applyAll() {
    ensureMoreSheet();
    ensureMediaViewer();
    ensureQAnalyseSheet();
    ensureBottomSafeArea();
    removeHiddenQFooterLink();
    tagQFab();
    tagResponsivePages();
    tagChatPhotos();
    attachAnalyseHandler();
  }

  function start() {
    applyAll();
    let queued = false;
    state.observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        applyAll();
      });
    });
    state.observer.observe(document.documentElement, { childList: true, subtree: true, attributes: false });
    window.addEventListener('resize', applyAll, { passive: true });

    window.LEMMIQ_V210 = {
      version: VERSION,
      refresh: applyAll,
      openMore: openMoreSheet,
      openMedia: openMediaViewer
    };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
