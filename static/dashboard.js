(() => {
  'use strict';
  const viewport = document.querySelector('#photo-canvas');
  const container = document.querySelector('#canvas-tiles');
  if (!viewport || !container) return;
  const originals = [...container.querySelectorAll('.photo-tile')].slice(0, 6);
  if (originals.length !== 6) return;
  const templates = originals.map(tile => tile.cloneNode(true));
  const toggle = document.querySelector('[data-canvas-toggle]');
  const directions = [...document.querySelectorAll('[data-direction]')];
  const status = document.querySelector('#canvas-status');
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const modulo = (value, divisor) => ((value % divisor) + divisor) % divisor;
  const roundUp = (value, multiple) => Math.ceil(value / multiple) * multiple;

  let autoplay = !motionPreference.matches;
  let activePointer = null;
  let lastPointerX = 0;
  let lastPointerY = 0;
  let dragging = false;
  let pointerStartX = 0;
  let pointerStartY = 0;
  let didDrag = false;
  let pressedLink = null;
  let focusedTile = null;
  let inView = true;
  let ready = false;
  let needsRender = false;
  let frameId = 0;
  let resizeFrameId = 0;
  let lastTimestamp = null;
  let offsetX = 0;
  let offsetY = 0;
  let geometry = null;
  let tiles = [];

  // Measure actual CSS lengths, including future clamp(), rem, or vw values.
  const measurement = document.createElement('div');
  measurement.setAttribute('aria-hidden', 'true');
  Object.assign(measurement.style, {
    position: 'absolute', visibility: 'hidden', pointerEvents: 'none',
    boxSizing: 'content-box', display: 'block', left: '0', top: '0',
    width: 'var(--tile-width)', height: 'var(--tile-height)',
    paddingLeft: 'var(--column-gap)', paddingTop: 'var(--row-gap)',
    marginTop: 'var(--caption-height)', border: '0',
  });
  viewport.appendChild(measurement);

  function announce(message) { if (status) status.textContent = message; }

  function prepareTile(tile) {
    // Only one representative per destination joins the keyboard tab order.
    tile.setAttribute('aria-hidden', 'true');
    tile.tabIndex = -1;
    tile.removeAttribute('id');
    tile.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
    tile.querySelectorAll('img').forEach(image => {
      image.draggable = false;
      function showFallback() {
        const media = image.closest('.photo-media');
        if (media) {
          media.classList.add('is-placeholder');
          const label = media.querySelector('.placeholder-label');
          if (label) label.hidden = false;
        }
        if (image.dataset.fallback && !image.dataset.canvasFallbackApplied) {
          image.dataset.canvasFallbackApplied = 'true';
          image.src = image.dataset.fallback;
        } else {
          image.style.visibility = 'hidden';
        }
      }
      image.addEventListener('error', showFallback);
      if (image.complete && image.naturalWidth === 0) showFallback();
    });
  }

  function canRender() {
    return ready && !document.hidden && inView && geometry && geometry.width > 0 && geometry.height > 0;
  }

  function updateControls() {
    toggle.hidden = false;
    toggle.setAttribute('aria-pressed', String(autoplay));
    toggle.setAttribute('aria-label', autoplay ? 'Pause automatic canvas movement' : 'Play automatic canvas movement');
    toggle.querySelector('[data-play-label]').textContent = autoplay ? 'Pause' : 'Play';
    toggle.querySelector('[data-play-icon]').toggleAttribute('hidden', autoplay);
    toggle.querySelector('[data-pause-icon]').toggleAttribute('hidden', !autoplay);
    directions.forEach(button => { button.hidden = false; });
    viewport.dataset.autoplay = String(autoplay);
  }

  function normalizeOffsets() {
    if (!geometry) return;
    offsetX = modulo(offsetX, geometry.periodX);
    offsetY = modulo(offsetY, geometry.periodY);
  }

  function renderTiles() {
    if (!geometry) return;
    const { strideX, strideY, periodX, periodY } = geometry;
    tiles.forEach(({ node, column, row }) => {
      // Recycle outside the viewport, preserving every visible neighbor.
      const x = modulo(column * strideX + offsetX + strideX, periodX) - strideX;
      const y = modulo(row * strideY + offsetY + strideY, periodY) - strideY;
      node.style.transform = `translate3d(${x.toFixed(3)}px, ${y.toFixed(3)}px, 0)`;
    });
    needsRender = false;
  }

  function requestFrame() {
    if (frameId || !canRender() || (!needsRender && !(autoplay && !dragging && !focusedTile))) return;
    frameId = window.requestAnimationFrame(animate);
  }

  function animate(timestamp) {
    frameId = 0;
    if (!canRender()) { lastTimestamp = null; return; }
    const moving = autoplay && !dragging && !focusedTile;
    if (moving && lastTimestamp !== null) {
      // A suspended tab or stalled frame must never jump on return.
      const elapsed = Math.min(Math.max((timestamp - lastTimestamp) / 1000, 0), 0.05);
      offsetX -= 15 * elapsed;
      offsetY -= 5 * elapsed;
      normalizeOffsets();
      needsRender = true;
    }
    if (needsRender) renderTiles();
    lastTimestamp = moving ? timestamp : null;
    requestFrame();
  }

  function rebuildPool(columns, rows) {
    const available = Array.from({ length: 6 }, () => []);
    if (tiles.length) {
      tiles.forEach(tile => available[tile.source].push(tile.node));
    } else {
      originals.forEach((node, source) => { prepareTile(node); available[source].push(node); });
    }
    const nextTiles = [];
    const represented = new Set();
    const fragment = document.createDocumentFragment();
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        const source = (row % 2) * 3 + (column % 3);
        let node = available[source].shift();
        if (!node) { node = templates[source].cloneNode(true); prepareTile(node); }
        const representative = !represented.has(source);
        represented.add(source);
        node.tabIndex = representative ? 0 : -1;
        node.setAttribute('aria-hidden', String(!representative));
        nextTiles.push({ node, source, row, column });
        fragment.appendChild(node);
      }
    }
    container.replaceChildren(fragment);
    tiles = nextTiles;
  }

  function resizeCanvas() {
    const bounds = viewport.getBoundingClientRect();
    if (bounds.width <= 0 || bounds.height <= 0) return;
    const computed = window.getComputedStyle(measurement);
    const tileWidth = parseFloat(computed.width);
    const tileHeight = parseFloat(computed.height);
    const columnGap = parseFloat(computed.paddingLeft);
    const rowGap = parseFloat(computed.paddingTop);
    const captionHeight = parseFloat(computed.marginTop);
    if (![tileWidth, tileHeight, columnGap, rowGap, captionHeight].every(Number.isFinite) || tileWidth <= 0 || tileHeight <= 0) return;
    const strideX = tileWidth + columnGap;
    const strideY = tileHeight + captionHeight + rowGap;
    // Whole pattern multiples make both axes repeat seamlessly.
    const columns = roundUp(Math.ceil(bounds.width / strideX) + 2, 3);
    const rows = roundUp(Math.ceil(bounds.height / strideY) + 2, 2);
    if (geometry) {
      offsetX = (offsetX / geometry.strideX) * strideX;
      offsetY = (offsetY / geometry.strideY) * strideY;
    } else {
      offsetX = bounds.width <= 600 ? (bounds.width - tileWidth) / 2 : -tileWidth * 0.45;
      offsetY = bounds.width <= 600 ? 88 : 96;
    }
    const poolChanged = !geometry || geometry.columns !== columns || geometry.rows !== rows;
    geometry = { width: bounds.width, height: bounds.height, strideX, strideY, columns, rows, periodX: columns * strideX, periodY: rows * strideY };
    if (poolChanged) rebuildPool(columns, rows);
    normalizeOffsets();
    ready = true;
    viewport.classList.add('canvas-ready');
    updateControls();
    lastTimestamp = null;
    needsRender = true;
    renderTiles();
    requestFrame();
  }

  function scheduleResize() {
    if (resizeFrameId) return;
    resizeFrameId = window.requestAnimationFrame(() => { resizeFrameId = 0; resizeCanvas(); });
  }

  function stopDragging(event) {
    if (activePointer === null || (event && typeof event.pointerId === 'number' && event.pointerId !== activePointer)) return;
    const pointerId = activePointer;
    const link = pressedLink;
    const rect = link?.getBoundingClientRect();
    const activate = event?.type === 'pointerup' && !didDrag && link &&
      event.clientX >= rect.left && event.clientX <= rect.right &&
      event.clientY >= rect.top && event.clientY <= rect.bottom;
    activePointer = null;
    dragging = false;
    pressedLink = null;
    viewport.classList.remove('is-dragging');
    lastTimestamp = null;
    if (viewport.hasPointerCapture(pointerId)) viewport.releasePointerCapture(pointerId);
    requestFrame();
    // Pointer capture retargets the browser click to the viewport, so a tap
    // explicitly follows its original link. Keyboard clicks remain native.
    if (activate) window.location.assign(link.href);
  }

  viewport.addEventListener('pointerdown', event => {
    if (!ready || activePointer !== null || event.isPrimary === false || (event.pointerType === 'mouse' && event.button !== 0)) return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.target instanceof Element && event.target.closest('button, input, select, textarea')) return;
    activePointer = event.pointerId;
    dragging = true;
    didDrag = false;
    pressedLink = event.target instanceof Element ? event.target.closest('a.photo-tile') : null;
    pointerStartX = event.clientX;
    pointerStartY = event.clientY;
    lastPointerX = event.clientX;
    lastPointerY = event.clientY;
    lastTimestamp = null;
    viewport.focus({ preventScroll: true });
    try { viewport.setPointerCapture(event.pointerId); } catch (_) { /* Window events still clean up. */ }
    event.preventDefault();
  });
  viewport.addEventListener('pointermove', event => {
    if (event.pointerId !== activePointer) return;
    if (!didDrag && Math.hypot(event.clientX - pointerStartX, event.clientY - pointerStartY) <= 6) return;
    didDrag = true;
    viewport.classList.add('is-dragging');
    offsetX += event.clientX - lastPointerX;
    offsetY += event.clientY - lastPointerY;
    lastPointerX = event.clientX;
    lastPointerY = event.clientY;
    normalizeOffsets();
    needsRender = true;
    requestFrame();
    event.preventDefault();
  }, { passive: false });
  window.addEventListener('pointerup', stopDragging);
  window.addEventListener('pointercancel', stopDragging);
  viewport.addEventListener('lostpointercapture', stopDragging);
  window.addEventListener('blur', () => stopDragging());
  viewport.addEventListener('dragstart', event => { if (ready) event.preventDefault(); });
  viewport.addEventListener('click', event => {
    // A swipe may still produce a compatibility click; never follow it.
    // detail=0 is native Enter activation (or a programmatic link click).
    if (event.detail > 0 && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey) event.preventDefault();
  }, true);

  container.addEventListener('focusin', event => {
    const link = event.target.closest?.('a.photo-tile');
    if (!link || !geometry) return;
    focusedTile = link;
    lastTimestamp = null;
    const rect = link.getBoundingClientRect();
    if (rect.left < 12 || rect.right > geometry.width - 12 || rect.top < 96 || rect.bottom > geometry.height - 128) {
      offsetX += (geometry.width - rect.width) / 2 - rect.left;
      offsetY += (geometry.height - rect.height) / 2 - rect.top;
      normalizeOffsets();
      needsRender = true;
      renderTiles();
    }
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  });
  container.addEventListener('focusout', () => {
    focusedTile = null;
    lastTimestamp = null;
    requestFrame();
  });

  function setAutoplay(enabled, userInitiated = false) {
    autoplay = enabled;
    lastTimestamp = null;
    updateControls();
    if (userInitiated) announce(enabled ? 'Automatic canvas movement playing.' : 'Automatic canvas movement paused.');
    requestFrame();
  }

  function moveCanvas(direction) {
    if (!geometry) return;
    const horizontalStep = Math.min(240, Math.max(80, geometry.strideX * 0.45));
    const verticalStep = Math.min(200, Math.max(80, geometry.strideY * 0.45));
    if (direction === 'left') offsetX -= horizontalStep;
    else if (direction === 'right') offsetX += horizontalStep;
    else if (direction === 'up') offsetY -= verticalStep;
    else if (direction === 'down') offsetY += verticalStep;
    else return;
    normalizeOffsets();
    needsRender = true;
    announce(`Moved canvas ${direction}.`);
    requestFrame();
  }
  toggle.addEventListener('click', () => setAutoplay(!autoplay, true));
  directions.forEach(button => button.addEventListener('click', () => moveCanvas(button.dataset.direction)));
  const arrowDirections = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' };
  viewport.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const direction = arrowDirections[event.key];
    if (direction) { event.preventDefault(); moveCanvas(direction); }
    else if (event.code === 'Space' || event.key === ' ') {
      event.preventDefault();
      if (!event.repeat) setAutoplay(!autoplay, true);
    }
  });

  function motionPreferenceChanged() {
    setAutoplay(false);
    announce('Automatic canvas movement paused after your motion preference changed.');
  }
  if (motionPreference.addEventListener) motionPreference.addEventListener('change', motionPreferenceChanged);
  else motionPreference.addListener(motionPreferenceChanged);
  document.addEventListener('visibilitychange', () => {
    lastTimestamp = null;
    if (document.hidden) {
      stopDragging();
      if (frameId) { window.cancelAnimationFrame(frameId); frameId = 0; }
    } else { needsRender = true; requestFrame(); }
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      inView = entries[0].isIntersecting;
      lastTimestamp = null;
      if (!inView && frameId) { window.cancelAnimationFrame(frameId); frameId = 0; }
      else if (inView) { needsRender = true; requestFrame(); }
    }).observe(viewport);
  }
  if ('ResizeObserver' in window) new ResizeObserver(scheduleResize).observe(viewport);
  window.addEventListener('resize', scheduleResize);
  resizeCanvas();
})();
