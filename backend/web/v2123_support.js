/* LEMMIQ V2.12.3 - secure official support chat shortcut. */
(() => {
  'use strict';
  async function openSupport() {
    try {
      const contact = await api('/v2123/support');
      if (!contact?.id) throw new Error('Official Support is not configured');
      const chat = await api('/chats/direct', {
        method: 'POST', body: JSON.stringify({ user_id: contact.id })
      });
      setView('chats');
      await loadChats();
      await openChat(chat.id);
    } catch (err) {
      toast(err.message || 'Unable to open official support', true);
    }
  }
  function setup() {
    for (const id of ['v2123SupportMe', 'v2123SupportMore']) {
      const button = document.getElementById(id);
      if (button) button.addEventListener('click', openSupport);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup, { once: true });
  } else setup();
})();
