(() => {
  'use strict';

  const root = document.querySelector('#scanner-root');
  if (!root) return;
  const openButton = document.querySelector('#open-scanner');
  const closeButton = document.querySelector('#close-scanner');
  const panel = document.querySelector('#mission-scanner');
  const retryButton = document.querySelector('#retry-scanner');
  const video = document.querySelector('#camera-preview');
  const cameraFrame = video.closest('.camera-frame');
  const cameraStatus = document.querySelector('#camera-status');
  const feedback = document.querySelector('#claim-feedback');
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d', { willReadFrequently: true });
  let stream = null;
  let scanTimer = null;
  let generation = 0;
  let claiming = false;

  function stopCamera() {
    generation += 1;
    clearTimeout(scanTimer);
    scanTimer = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    video.pause();
    video.srcObject = null;
    cameraFrame.hidden = true;
  }

  function closeScanner(restoreFocus = true) {
    stopCamera();
    panel.hidden = true;
    openButton.setAttribute('aria-expanded', 'false');
    if (restoreFocus && !openButton.disabled) openButton.focus({ preventScroll: true });
  }

  function announce(message, needsLogin = false) {
    feedback.textContent = message;
    if (needsLogin) {
      const link = document.createElement('a');
      link.href = root.dataset.loginUrl;
      link.textContent = 'Log in';
      feedback.append(document.createElement('br'), link);
    }
    feedback.hidden = false;
  }

  function applyProgress(progress) {
    if (Number.isSafeInteger(progress.total_points)) {
      document.querySelector('#player-total').textContent = String(progress.total_points);
    }
    if (!Array.isArray(progress.missions)) return;
    for (const mission of progress.missions) {
      // Compare existing data attributes instead of constructing selectors from data.
      const row = [...document.querySelectorAll('[data-mission-type]')]
        .find(node => node.dataset.missionType === mission.mission_type);
      if (!row) continue;
      row.classList.toggle('is-claimed', mission.claimed);
      row.querySelector('.mission-state').hidden = !mission.claimed;
      row.querySelector('.mission-score strong').textContent = String(
        mission.claimed ? mission.points_awarded : mission.points,
      );
    }
  }

  async function claim(qrText) {
    if (claiming) return;
    claiming = true;
    stopCamera();
    retryButton.hidden = true;
    openButton.disabled = true;
    root.setAttribute('aria-busy', 'true');
    cameraStatus.textContent = 'QR found. Checking your mission…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(root.dataset.claimUrl, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': root.dataset.csrf },
        body: JSON.stringify({ qr_code: qrText, destination_slug: root.dataset.destination }),
      });
      const result = await response.json();
      applyProgress(result);
      announce(result.message || 'Your claim could not be confirmed. Please scan again.', response.status === 401);
      cameraStatus.textContent = 'Camera stopped. You can scan another mission card.';
      root.dataset.claimStatus = result.status || 'unavailable';
    } catch {
      announce('We couldn’t confirm this scan. Try again; each mission can only be claimed once.');
      cameraStatus.textContent = 'Camera stopped. Scan again to check your claim.';
      root.dataset.claimStatus = 'unavailable';
    } finally {
      clearTimeout(timeout);
      claiming = false;
      openButton.disabled = false;
      root.removeAttribute('aria-busy');
      retryButton.textContent = 'Scan another QR';
      retryButton.hidden = false;
    }
  }

  function cameraFailure(error) {
    switch (error?.name) {
      case 'NotAllowedError':
      case 'SecurityError':
        return 'Camera access was blocked. Allow camera access in your browser settings, then try again.';
      case 'NotFoundError':
      case 'DevicesNotFoundError':
        return 'No camera was found. Connect a camera, then try again.';
      case 'NotReadableError':
      case 'TrackStartError':
        return 'Your camera could not start. Close other apps using the camera, then try again.';
      default:
        return 'Your camera could not start. Check your camera connection and browser permissions, then try again.';
    }
  }

  function failCamera(message) {
    stopCamera();
    cameraStatus.textContent = message;
    retryButton.textContent = 'Try camera again';
    retryButton.hidden = false;
  }

  function decodeFrame(token) {
    if (token !== generation || panel.hidden || claiming) return;
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0) {
      const scale = Math.min(1, 640 / video.videoWidth);
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      try {
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const frame = context.getImageData(0, 0, canvas.width, canvas.height);
        const code = window.jsQR(frame.data, frame.width, frame.height, { inversionAttempts: 'attemptBoth' });
        if (code && code.data) {
          void claim(code.data);
          return;
        }
      } catch {
        failCamera('The scanner could not read the camera. Try starting the camera again.');
        return;
      }
    }
    scanTimer = setTimeout(() => decodeFrame(token), 180);
  }

  async function startCamera() {
    if (claiming) return;
    stopCamera();
    const token = generation;
    retryButton.hidden = true;
    if (!window.isSecureContext) {
      failCamera('Camera scanning needs a secure connection. Open LakbayPass over HTTPS, then try again.');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      failCamera('This browser cannot access a camera. Try a browser with camera support.');
      return;
    }
    if (typeof window.jsQR !== 'function' || !context) {
      failCamera('The QR scanner could not load. Refresh this page, then try again.');
      return;
    }
    cameraStatus.textContent = 'Allow camera access to scan a QR code.';
    try {
      let acquired;
      try {
        acquired = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        });
      } catch (error) {
        if (error.name !== 'OverconstrainedError' || token !== generation) throw error;
        acquired = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
      }
      // Permission may resolve after Close, a new request, or leaving the page.
      if (token !== generation || panel.hidden) {
        acquired.getTracks().forEach(track => track.stop());
        return;
      }
      stream = acquired;
      for (const track of stream.getVideoTracks()) {
        track.addEventListener('ended', () => {
          if (token === generation && !panel.hidden) failCamera('The camera disconnected. Check the camera, then try again.');
        }, { once: true });
      }
      video.srcObject = acquired;
      await video.play();
      if (token !== generation || panel.hidden) return;
      cameraFrame.hidden = false;
      cameraStatus.textContent = 'Camera ready. Hold the QR code steady inside the preview.';
      decodeFrame(token);
    } catch (error) {
      if (token === generation && !panel.hidden) failCamera(cameraFailure(error));
    }
  }

  openButton.disabled = false;
  openButton.addEventListener('click', () => {
    if (!panel.hidden) return;
    panel.hidden = false;
    openButton.setAttribute('aria-expanded', 'true');
    closeButton.focus({ preventScroll: true });
    panel.scrollIntoView({ block: 'nearest' });
    void startCamera();
  });
  closeButton.addEventListener('click', () => closeScanner());
  retryButton.addEventListener('click', () => void startCamera());
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeScanner();
    }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) closeScanner(false);
  });
  window.addEventListener('pagehide', () => closeScanner(false));
  window.addEventListener('pageshow', async event => {
    if (!event.persisted) return;
    try {
      const response = await fetch(root.dataset.progressUrl, { credentials: 'same-origin', cache: 'no-store' });
      if (response.ok) applyProgress(await response.json());
    } catch { /* Initial saved state stays visible until the next successful scan. */ }
  });
})();
