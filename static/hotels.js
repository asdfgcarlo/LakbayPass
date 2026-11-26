(() => {
  'use strict';
  function showFallback(image) {
    image.hidden = true;
    image.removeAttribute('srcset');
    const figure = image.closest('.hotel-figure');
    figure.querySelector('.hotel-photo-fallback').hidden = false;
    const credit = figure.querySelector('.hotel-photo-credit');
    if (credit) credit.hidden = true;
  }
  document.querySelectorAll('.hotel-image').forEach((image) => {
    image.addEventListener('error', () => showFallback(image), { once: true });
    // Handle a cached error that happened before this deferred script ran.
    if (image.complete && !image.naturalWidth) showFallback(image);
  });
})();
