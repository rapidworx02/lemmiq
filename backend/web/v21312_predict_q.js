/* LEMMIQ v2.13.12: safe order-specific Q Predict QR, approved-account notice. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const api = (url, options = {}) => window.api(url, options);
  const safe = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const NETWORKS = ['TRC20', 'BEP20'];
  let access = null;
  let loadingAccess = false;
  let queued = false;
  let activeModal = null;
  const toast = (m, err = false) => window.toast ? window.toast(m, err) : alert(m);

  const approvedHtml = () => `<div class="pq12-access" role="status"><strong>✓ Verified User Access — Q Predict</strong><p>Your account is approved for Q Predict testing. Q Predict and Q Economy wallets remain separate. Buying, predictions and withdrawals are available only when the corresponding service is enabled and applicable verification and authorisation requirements are met.</p></div>`;

  async function fetchAccess() {
    if (loadingAccess) return;
    loadingAccess = true;
    try {
      access = await api('/v21311/redeem/status');
      schedule();
    } catch (_error) {
      access = null; // Never assume approval after an API failure.
    } finally {
      loadingAccess = false;
    }
  }

  function renderAccess() {
    const root = $('v21310PredictRoot');
    if (!root || !access) return;
    const isApproved = access.eligible === true;
    const note = root.querySelector('.pq-actions + .pq-note');
    if (note && isApproved && !note.classList.contains('pq12-access')) {
      note.outerHTML = approvedHtml();
    }
    const buyForm = $('pqDetail')?.querySelector('.pq-panel');
    if (!buyForm) return;
    // v2.13.11 injects a generic 'Verification Required' box when checkout
    // is switched off. Remove it for allowlisted users, but do not turn ON
    // any payment button or bypass an API permission check.
    if (isApproved && $('pqQuote')) {
      buyForm.querySelectorAll('.pq-verification').forEach(el => el.remove());
      if (!buyForm.querySelector('.pq12-access')) {
        const n = document.createElement('div');
        n.innerHTML = approvedHtml();
        buyForm.insertBefore(n.firstElementChild, buyForm.firstElementChild?.nextSibling || null);
      }
    }
  }

  function showZoom(data) {
    if (activeModal) activeModal.remove();
    const modal = document.createElement('div');
    modal.className = 'pq12-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Enlarged Q Predict receiving QR');
    modal.innerHTML = `<div class="pq12-modal-inner"><h3>${safe(data.network)} — USDT receiving QR</h3><img alt="Enlarged QR for receiving address" src="data:image/png;base64,${data.qr_png_b64}"><code>${safe(data.receiving_address)}</code><p class="micro">Scan using the selected network only. Confirm that your wallet shows this exact receiving address.</p><button type="button" class="ghost" data-pq12-close>Close</button></div>`;
    document.body.appendChild(modal);
    activeModal = modal;
    const close = () => { if (activeModal === modal) activeModal = null; modal.remove(); document.removeEventListener('keydown', escClose); };
    const escClose = e => { if (e.key === 'Escape') close(); };
    modal.addEventListener('click', e => { if (e.target === modal || e.target.closest('[data-pq12-close]')) close(); });
    document.addEventListener('keydown', escClose);
    modal.querySelector('button')?.focus();
  }

  async function renderOrderQR() {
    const panel = $('pqDetail')?.querySelector('[data-pq-order-id]');
    if (!panel || panel.querySelector('.pq12-qr-panel') || panel.dataset.pq12Loading || panel.dataset.pq12Error) return;
    const id = Number(panel.dataset.pqOrderId);
    if (!Number.isSafeInteger(id) || id <= 0 || !panel.querySelector('#pqCopyAddress')) return;
    panel.dataset.pq12Loading = '1';
    try {
      const data = await api(`/v21312/predict/qr/order/${id}`);
      if (!panel.isConnected || panel.querySelector('.pq12-qr-panel')) return;
      const rawAddress = panel.querySelector('.pq-data code')?.textContent?.trim();
      if (!data.qr_png_b64 || !data.receiving_address || rawAddress !== data.receiving_address) {
        throw new Error('Receiving address mismatch — use Copy Address and contact support');
      }
      const box = document.createElement('div');
      box.className = 'pq12-qr-panel';
      box.innerHTML = `<strong>Scan to pay with ${safe(data.network)} USDT</strong><img class="pq12-qr-image" alt="QR encoding receiving address" role="button" tabindex="0" src="data:image/png;base64,${data.qr_png_b64}"><button class="ghost" type="button">Enlarge QR code</button><small>QR is generated from this exact order receiving address. Check the network and destination in your wallet before transferring.</small>`;
      panel.querySelector('#pqCopyAddress').before(box);
      box.querySelector('button').onclick = () => showZoom(data);
      const pic = box.querySelector('img');
      pic.onclick = () => showZoom(data);
      pic.onkeydown = e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault();showZoom(data);} };
    } catch (e) {
      panel.dataset.pq12Error = '1'; // Avoid retry loops if QR access is unavailable.
      if (panel.isConnected && !panel.querySelector('.pq12-qr-panel')) {
        const n = document.createElement('p');
        n.className = 'pq-note';
        n.textContent = 'QR unavailable: ' + e.message + '. Copy the receiving address instead.';
        panel.querySelector('#pqCopyAddress')?.before(n);
      }
    } finally {
      delete panel.dataset.pq12Loading;
    }
  }

  async function loadAdminQR(network, holder) {
    try {
      const result = await api(`/v21312/predict/qr/admin/${network}`);
      if (!holder.isConnected) return;
      holder.querySelector('.pq12-admin-preview').innerHTML = `<img alt="Address-based checkout QR" src="data:image/png;base64,${result.checkout_qr_png_b64}"><p class="micro">Checkout QR generated from ${safe(result.receiving_address)}.</p>${result.custom_reference_png_b64 ? `<details><summary>Uploaded admin QR reference</summary><img alt="Custom admin reference image" src="data:image/png;base64,${result.custom_reference_png_b64}"></details>` : ''}`;
    } catch (e) {
      if (holder.isConnected) holder.querySelector('.pq12-admin-preview').textContent = 'Save the receiving address first to display the QR.';
    }
  }

  function renderAdminQR() {
    for (const network of NETWORKS) {
      const input = $('pqAdminAddress' + network);
      if (!input || input.parentElement?.querySelector('.pq12-admin-qr')) continue;
      const holder = document.createElement('div');
      holder.className = 'pq12-admin-qr';
      holder.innerHTML = `<strong>${network} payment QR</strong><p class="micro">Checkout QR is generated from the treasury address. Optional uploaded images are admin references only and are NOT used for payments.</p><div class="pq12-admin-preview"></div><input type="file" accept="image/png,image/jpeg,image/webp" hidden><button class="ghost" type="button">Add / replace QR reference</button><button class="ghost" type="button">Remove reference</button>`;
      input.parentElement.appendChild(holder);
      const file = holder.querySelector('input[type=file]');
      const buttons = holder.querySelectorAll('button');
      buttons[0].addEventListener('click', () => file.click());
      file.addEventListener('change', async () => {
        if (!file.files?.[0]) return;
        const form = new FormData();
        form.append('file', file.files[0]);
        try {
          await api(`/v21312/predict/qr/admin/${network}`, {method: 'POST', body: form});
          toast(`${network} admin reference saved`);
          await loadAdminQR(network, holder);
        } catch (e) {toast(e.message, true);} finally {file.value = '';}
      });
      buttons[1].addEventListener('click', async () => {
        if (!confirm(`Remove the stored ${network} admin reference? Checkout QR remains available.`)) return;
        try { await api(`/v21312/predict/qr/admin/${network}`, {method:'DELETE'}); await loadAdminQR(network, holder); toast('QR reference removed'); }
        catch (e) {toast(e.message, true);}
      });
      loadAdminQR(network, holder);
    }
  }

  function render() { queued = false; renderAccess(); renderOrderQR(); renderAdminQR(); }
  function schedule() { if (queued) return; queued = true; setTimeout(render, 60); }
  document.addEventListener('DOMContentLoaded', () => {
    fetchAccess();
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, {childList: true, subtree: true});
    document.addEventListener('click', e => {
      if (e.target.closest('[data-view="q-predict"], [data-more-view="q-admin"], #pqBuy, #pqQuote, #pqCreateOrder, [data-pq-mode]')) {
        setTimeout(fetchAccess, 140);
        schedule();
      }
    });
    schedule();
  });
})();
