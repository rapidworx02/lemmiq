/* LEMMIQ 2.13.13 — client-side hash validation and admin unpaid-order cancellation.
   All server-side restrictions remain authoritative. */
(() => {
  'use strict';
  const api = (path, options) => window.api(path, options);
  const $ = id => document.getElementById(id);
  const alertUser = (text, bad = false) => {
    if (typeof window.toast === 'function') window.toast(text, bad);
    else window.alert(text);
  };
  function isValidHash(network, value) {
    const hash = String(value || '').trim();
    return network === 'TRC20' ? /^[a-fA-F0-9]{64}$/.test(hash)
      : network === 'BEP20' ? /^0x[a-fA-F0-9]{64}$/.test(hash) : false;
  }
  function networkOfOrder(panel) {
    const values = panel?.querySelectorAll('.pq-data b');
    return values?.[0]?.textContent?.trim()?.toUpperCase() || '';
  }
  let queued = false;
  function enhanceHashForm() {
    const panel = $('pqDetail')?.querySelector('[data-pq-order-id]');
    const field = panel?.querySelector('#pqHash');
    const submit = panel?.querySelector('#pqSubmitHash');
    if (!panel || !field || !submit) return;
    if (field.dataset.pq13Ready === '1') return;
    field.dataset.pq13Ready = '1';
    field.autocomplete = 'off';
    field.spellcheck = false;
    const help = document.createElement('p');
    help.className = 'pq13-hash-help';
    help.setAttribute('role', 'status');
    field.insertAdjacentElement('afterend', help);
    const update = () => {
      const chain = networkOfOrder(panel);
      const raw = field.value.trim();
      const valid = isValidHash(chain, raw);
      submit.disabled = !valid;
      if (!raw) {
        help.textContent = 'Enter the actual blockchain transaction ID after paying. Payment submission is disabled until a valid hash is supplied.';
      } else {
        help.textContent = valid ? 'Hash format accepted. The backend will still verify the actual USDT transfer.' :
          (chain === 'BEP20' ? 'Invalid BEP20 hash: enter 0x followed by 64 hexadecimal characters.' :
            'Invalid TRC20 hash: enter exactly 64 hexadecimal characters (0–9, a–f).');
      }
      help.classList.toggle('is-error', !!raw && !valid);
    };
    field.addEventListener('input', update);
    update();
  }
  // Also guard clicks in the capture phase if another script re-creates the button.
  document.addEventListener('click', event => {
    const button = event.target.closest?.('#pqSubmitHash');
    if (!button) return;
    const panel = button.closest('[data-pq-order-id]');
    const hash = panel?.querySelector('#pqHash')?.value;
    const network = networkOfOrder(panel);
    if (!isValidHash(network, hash)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      alertUser(network === 'BEP20' ? 'Enter a real BEP20 transaction hash (0x + 64 hex characters).' :
        'Enter a real TRC20 transaction ID (64 hex characters) before submitting.', true);
    }
  }, true);

  async function cancelOne(orderId, block, button) {
    const promptMsg = 'Cancel this unpaid Q Predict order?\n\nONLY cancel if no USDT transfer has been made. Once cancelled, any late transfer requires support/manual reconciliation.\n\nReason:';
    const reason = window.prompt(promptMsg, 'Unpaid order cancelled: no transaction hash supplied');
    if (reason == null) return;
    if (reason.trim().length < 8) { alertUser('Cancellation reason must be at least 8 characters.', true); return; }
    button.disabled = true;
    try {
      const result = await api(`/v21313/predict/admin/orders/${orderId}/cancel`, {method:'POST', body:JSON.stringify({reason:reason.trim()})});
      block.dataset.pqStatus = 'CANCELLED';
      block.querySelector('strong').textContent = result.order.code + ' · CANCELLED · ' + result.order.network;
      const small = block.querySelector('small');
      if (small) small.textContent = 'Cancelled by Master Admin — no submitted transaction hash';
      block.querySelector('.pq13-cancel-actions')?.remove();
      alertUser('Unpaid purchase order cancelled. Audit history retained.');
    } catch (error) {
      button.disabled = false;
      alertUser('Cancellation failed: ' + error.message, true);
    }
  }
  async function cancelExpired(button) {
    if (!window.confirm('Cancel only EXPIRED CREATED orders without a transaction hash? Orders with submitted payment proof or approved Q will NOT be touched. Check for any late transfers separately.')) return;
    button.disabled = true;
    try {
      const result = await api('/v21313/predict/admin/orders/cancel-expired', {
        method:'POST', body:JSON.stringify({reason:'Expired unpaid quote — no transaction hash submitted'})
      });
      alertUser(`${result.cancelled_count} expired unpaid orders cancelled. Refresh the Q Predict admin section to see the new statuses.`);
      // The current admin list is a snapshot; reload instead of showing stale state.
      if (result.cancelled_count > 0) window.location.reload();
    } catch(error) {
      alertUser('Could not cancel expired orders: ' + error.message, true);
    } finally {
      button.disabled = false;
    }
  }
  function enhanceAdmin() {
    const admin = $('pqAdmin');
    const list = admin?.querySelector('.pq-admin-list');
    if (!list) return;
    if (!list.querySelector('.pq13-bulk')) {
      const head = list.querySelector('h4');
      const block = document.createElement('div');
      block.className = 'pq13-bulk';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Cancel expired unpaid orders';
      btn.onclick = () => cancelExpired(btn);
      const note = document.createElement('p');
      note.textContent = 'Only expired CREATED orders with no transaction hash; no Q or USDT is moved.';
      block.append(btn, note);
      if (head) head.after(block); else list.prepend(block);
    }
    for (const block of list.querySelectorAll('.pq-admin-order[data-pq-order-id]')) {
      if (block.dataset.pqStatus !== 'CREATED' || block.dataset.pqHasHash === '1' || block.querySelector('.pq13-cancel-actions')) continue;
      const id = Number(block.dataset.pqOrderId);
      if (!Number.isSafeInteger(id) || id <= 0) continue;
      const actions = document.createElement('div');
      actions.className = 'pq13-cancel-actions';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = 'Cancel unpaid order';
      btn.addEventListener('click', () => cancelOne(id, block, btn));
      actions.appendChild(btn);
      block.appendChild(actions);
    }
  }
  function apply() { queued = false; enhanceHashForm(); enhanceAdmin(); }
  function schedule() { if (queued) return; queued = true; setTimeout(apply, 80); }
  document.addEventListener('DOMContentLoaded', () => {
    const obs = new MutationObserver(schedule);
    obs.observe(document.body, {subtree:true,childList:true});
    document.addEventListener('click', event => {
      if (event.target.closest?.('[data-view="q-predict"], [data-more-view="q-admin"], #pqBuy, #pqCreateOrder')) schedule();
    });
    schedule();
  });
  // Non-secret helper exposed for automated browser tests.
  window.LEMMIQ_PQ13_HASH_VALID = isValidHash;
})();
