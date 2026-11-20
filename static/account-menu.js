(() => {
  'use strict';
  const menu = document.querySelector('[data-account-menu]');
  if (!menu) return;
  const summary = menu.querySelector('summary');
  const desktop = window.matchMedia('(min-width: 768px)');
  const close = (restoreFocus = false) => {
    if (!menu.open) return;
    menu.open = false;
    if (restoreFocus) summary.focus({ preventScroll: true });
  };
  menu.addEventListener('toggle', () => {
    document.dispatchEvent(new CustomEvent('lakbay:account-menu', { detail: { open: menu.open } }));
  });
  document.addEventListener('pointerdown', event => {
    if (!menu.contains(event.target)) close();
  });
  document.addEventListener('focusin', event => {
    if (!menu.contains(event.target)) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu.open) {
      event.preventDefault();
      event.stopImmediatePropagation();
      close(true);
    }
  }, true);
  menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => close()));
  desktop.addEventListener('change', () => {
    if (!desktop.matches) return;
    const containedFocus = menu.contains(document.activeElement);
    close();
    if (containedFocus) document.querySelector('.welcome, .back-to-gallery')?.focus({ preventScroll: true });
  });
  window.addEventListener('pagehide', () => close());
})();
