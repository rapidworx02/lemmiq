/* LEMMIQ V2.13.2 — call recovery UI + prominent Q Creators shortcut.
 * Only the logged-in account may reset its own active calls. Reset requires
 * explicit confirmation and is processed by the authenticated backend.
 */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let busy = false;
  let last = null;

  function mount() {
    const calls = $('view-calls');
    if (calls && !$('v2132CallRecovery')) {
      const card = document.createElement('article');
      card.id = 'v2132CallRecovery';
      card.className = 'card glass v2132-call-recovery';
      card.innerHTML = `
        <div class="section-head"><div><span class="eyebrow">CALL DIAGNOSTICS</span><h3>Call Recovery</h3>
          <p class="micro">Seeing “user already on call” when neither person is calling? Check and clear an abandoned session.</p></div></div>
        <div id="v2132CallStatus" class="v2132-call-status" role="status">Check your call status.</div>
        <div class="v2132-call-actions">
          <button id="v2132CallCheck" type="button" class="ghost">↻ Check active calls</button>
          <button id="v2132CallReset" type="button" class="danger">End my active calls / Reset</button>
        </div>
        <p class="micro">Reset ends every active LEMMIQ call on your account, including other devices. The other party may be disconnected.</p>`;
      const list = $('callsList');
      const parent = list?.closest('article');
      if (parent) parent.before(card);
      else calls.append(card);
      $('v2132CallCheck').addEventListener('click', () => check());
      $('v2132CallReset').addEventListener('click', reset);
    }
    // The PWA already includes Q Creators inside Q Economy. Make it a prominent CTA.
    const economy = $('view-q-economy');
    if (economy && !$('v2132QCreatorShortcut')) {
      const heading = economy.querySelector('.q28-hero');
      if (heading) {
        const shortcut = document.createElement('button');
        shortcut.id = 'v2132QCreatorShortcut';
        shortcut.type = 'button';
        shortcut.className = 'v2132-creators-shortcut';
        shortcut.textContent = '✨ Q Creators · Discover & Exclusive Gallery';
        shortcut.addEventListener('click', () => {
          if (typeof setView === 'function') setView('q-creators');
        });
        heading.after(shortcut);
      }
    }
  }

  function updateStatus(info, msg) {
    const area = $('v2132CallStatus');
    if (!area) return;
    if (msg) { area.textContent = msg; return; }
    const count = info?.active_count ?? 0;
    area.innerHTML = `<strong>${count ? `${count} active call(s) in server records` : 'No active calls in server records'}</strong>`
      + (info?.active || []).map(c => `<p class="micro">${escape(c.call_type)} · ${escape(c.peer_display_name)} · ${escape(c.status)}</p>`).join('');
    if (info?.resolved_count) area.innerHTML += `<p class="micro">Automatically cleared ${info.resolved_count} abandoned call(s).</p>`;
  }
  function buttons(disabled) {
    ['v2132CallCheck','v2132CallReset'].forEach(id => { if ($(id)) $(id).disabled = disabled; });
  }
  async function check() {
    if (busy || !$('v2132CallRecovery')) return;
    busy = true;
    buttons(true);
    updateStatus(null, 'Checking call status…');
    try {
      // Reconcile only calls actually stale by server age / confirmed LiveKit absence.
      last = await api('/v2132/calls/reconcile', {method: 'POST', body: '{}'});
      updateStatus(last);
    } catch (e) {
      updateStatus(null, `Call recovery unavailable: ${e.message || e}. Make sure the V2.13.2 backend is deployed.`);
    } finally { busy = false; buttons(false); }
  }
  async function reset() {
    if (busy) return;
    const agree = window.confirm('End ALL active LEMMIQ calls on your account? This can disconnect another device or participant. Use only if your call status is stuck.');
    if (!agree) return;
    busy = true;
    buttons(true);
    updateStatus(null, 'Ending your active call sessions…');
    try {
      const result = await api('/v2132/calls/reset', {
        method: 'POST', body: JSON.stringify({confirm: true})
      });
      // Clear any local PWA call overlay after the backend has accepted the reset.
      if (typeof endVoiceCall === 'function') await endVoiceCall(false);
      if (typeof loadCalls === 'function') loadCalls().catch(() => {});
      last = await api('/v2132/calls/active');
      updateStatus(last);
      const line = document.createElement('p');
      line.className = 'micro v2132-reset-result';
      line.textContent = `Reset complete: ${result.ended_count} server call(s) ended.` +
        (result.livekit_teardown_failed ? ' LiveKit disconnect could not be confirmed for every room.' : '');
      $('v2132CallStatus')?.append(line);
    } catch (e) {
      updateStatus(null, `Unable to reset: ${e.message || e}`);
    } finally { busy = false; buttons(false); }
  }

  document.addEventListener('DOMContentLoaded', () => {
    mount();
    const previous = window.loadCalls;
    if (typeof previous === 'function') {
      window.loadCalls = async function (...args) {
        const data = await previous.apply(this, args);
        if ($('view-calls')?.classList.contains('active')) await check();
        return data;
      };
    }
  });
})();
