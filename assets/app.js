/* TravelOS browser-only polish. No analytics, maps, providers, or external scripts. */
import { icon } from '/assets/icons.js';

(() => {
  const toastRegion = document.querySelector('.toast-region');
  const showToast = (message) => {
    if (!toastRegion || !message) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toastRegion.append(toast);
    window.setTimeout(() => {
      toast.classList.add('is-leaving');
      window.setTimeout(() => toast.remove(), 280);
    }, 3000);
  };

  /* ── Theme toggle ────────────────────────────────────────────────── */
  const themeToggle = document.querySelector('[data-theme-toggle]');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const body = document.body;
      const current = body.getAttribute('data-theme');
      const next = current === 'dark' ? 'bright' : 'dark';
      body.setAttribute('data-theme', next);
      try { localStorage.setItem('travelos-theme', next); } catch (_) { /* noop */ }
      const label = next === 'dark' ? 'coding' : 'bright';
      showToast(`Theme: ${label} 🎨`);
    });
  }

  /* Restore saved theme preference (public pages only — workspace always starts dark) */
  try {
    const saved = localStorage.getItem('travelos-theme');
    if (saved && !document.body.classList.contains('command-shell')) {
      document.body.setAttribute('data-theme', saved);
    }
  } catch (_) { /* noop */ }

  /* ── Click delegation ────────────────────────────────────────────── */
  document.addEventListener('click', (event) => {
    const toaster = event.target.closest('[data-toast]');
    if (toaster) showToast(toaster.dataset.toast);

    const menu = event.target.closest('[data-menu-toggle]');
    if (menu) {
      const header = document.querySelector('.site-header');
      header?.classList.toggle('is-menu-open');
      menu.setAttribute('aria-expanded', String(header?.classList.contains('is-menu-open')));
    }

    const sideToggle = event.target.closest('[data-sidebar-toggle]');
    if (sideToggle) {
      document.querySelector('.command-sidebar')?.classList.toggle('is-collapsed');
      showToast('Trip rail toggled — keyboard layout remains in place.');
    }

    const drawerToggle = event.target.closest('[data-drawer-toggle]');
    if (drawerToggle) {
      document.querySelector('.command-drawer')?.classList.toggle('is-expanded');
      showToast('Trip signals are already visible in this local demo.');
    }

    const dayButton = event.target.closest('[data-day]');
    if (dayButton) {
      document.querySelectorAll('[data-day]').forEach((button) => button.classList.remove('is-active'));
      dayButton.classList.add('is-active');
      showToast(`Day ${dayButton.dataset.day} is now the active planning context.`);
    }

    const paneTab = event.target.closest('[data-pane-tab]');
    if (paneTab) {
      paneTab.parentElement.querySelectorAll('button').forEach((button) => button.classList.remove('is-active'));
      paneTab.classList.add('is-active');
      showToast(`${paneTab.textContent.trim()} view is a local workspace surface.`);
    }

    const bookingTab = event.target.closest('[data-booking-tab]');
    if (bookingTab) {
      bookingTab.parentElement.querySelectorAll('button').forEach((button) => button.classList.remove('is-active'));
      bookingTab.classList.add('is-active');
      showToast(`${bookingTab.textContent.trim()} fixtures are now in focus.`);
    }

    const overview = event.target.closest('[data-overview]');
    if (overview) {
      document.querySelectorAll('[data-overview]').forEach((button) => button.classList.remove('is-active'));
      overview.classList.add('is-active');
      showToast(`${overview.textContent.trim()} is the active command-center lens.`);
    }

    if (event.target.closest('[data-command-palette]')) {
      document.querySelector('[data-command-dialog]')?.removeAttribute('hidden');
      document.querySelector('[data-command-dialog] input')?.focus();
    }
    if (event.target.closest('[data-command-close]')) {
      document.querySelector('[data-command-dialog]')?.setAttribute('hidden', '');
    }

    /* ── Copy share link ───────────────────────────────────────────── */
    const copyBtn = event.target.closest('[data-copy-link]');
    if (copyBtn) {
      const url = copyBtn.dataset.copyLink || window.location.href;
      navigator.clipboard.writeText(url).then(
        () => showToast('Link copied! Share it with your travel crew. 📋'),
        () => showToast('Could not copy — select and copy manually.')
      );
    }
  });

  /* ── Keyboard shortcuts ─────────────────────────────────────────── */
  document.addEventListener('keydown', (event) => {
    const dialog = document.querySelector('[data-command-dialog]');
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      dialog?.removeAttribute('hidden');
      dialog?.querySelector('input')?.focus();
    }
    if (event.key === 'Escape' && dialog && !dialog.hasAttribute('hidden')) {
      dialog.setAttribute('hidden', '');
    }
    /* Pane keys 1–6 — only active in workspace */
    if (['1', '2', '3', '4', '5', '6'].includes(event.key) && document.body.classList.contains('command-shell')) {
      const target = [...document.querySelectorAll('.pane-key')].find((key) => key.textContent.trim() === event.key)?.closest('.command-pane');
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.animate([{ outline: '2px solid #f2c85d' }, { outline: '0 solid transparent' }], { duration: 850 });
        showToast(`Pane ${event.key} focused.`);
      }
    }
    /* Quick theme toggle: Ctrl+Shift+T */
    if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 't') {
      event.preventDefault();
      themeToggle?.click();
    }
  });
})();
