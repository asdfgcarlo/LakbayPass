(() => {
  'use strict';
  const section = document.querySelector('[data-memories]');
  if (!section) return;
  const byId = (id) => document.getElementById(id);
  const form = byId('memories-form');
  const fields = byId('memories-fields');
  const picker = byId('memory-files');
  const previews = byId('memory-previews');
  const gallery = byId('memories-gallery');
  const addButton = byId('add-memories');
  const saveButton = byId('save-memories');
  const error = byId('memories-error');
  const status = byId('memories-status');
  const viewer = byId('memory-viewer');
  const viewerActions = byId('memory-viewer-actions');
  const editForm = byId('memory-edit-form');
  const editCaption = byId('memory-edit-caption');
  const deleteConfirm = byId('memory-delete-confirm');
  const viewerError = byId('memory-viewer-error');
  const viewerStatus = byId('memory-viewer-status');
  let selected = [];
  let nextId = 0;
  let activeCard = null;
  let viewerBusy = false;

  async function api(url, options = {}) {
    let response;
    try {
      response = await fetch(url, {
        ...options,
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': section.dataset.csrf, ...options.headers },
      });
    } catch {
      throw new Error('Could not connect. Check your connection and try again.');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || 'Your memories could not be saved. Please try again.');
    return data;
  }

  function updateCount() {
    byId('memories-count').textContent = `${selected.length} of 3 photos selected · at least 1 required`;
  }

  function closeForm() {
    selected.forEach((photo) => URL.revokeObjectURL(photo.url));
    selected = [];
    nextId = 0;
    previews.replaceChildren();
    picker.value = '';
    error.textContent = '';
    updateCount();
    form.hidden = true;
    addButton.hidden = false;
    addButton.setAttribute('aria-expanded', 'false');
    addButton.focus({ preventScroll: true });
  }

  addButton.addEventListener('click', () => {
    status.textContent = '';
    form.hidden = false;
    addButton.setAttribute('aria-expanded', 'true');
    addButton.hidden = true;
    picker.focus();
  });
  byId('cancel-memories').addEventListener('click', closeForm);

  function preview(photo) {
    const item = document.createElement('li');
    item.className = 'memory-preview';
    const image = document.createElement('img');
    image.src = photo.url;
    image.alt = `Selected photo: ${photo.file.name}`;
    image.width = 320;
    image.height = 240;
    const label = document.createElement('label');
    label.htmlFor = `memory-caption-${photo.key}`;
    label.textContent = `Description for photo ${photo.key + 1} (optional)`;
    const caption = document.createElement('textarea');
    caption.id = label.htmlFor;
    caption.maxLength = 300;
    caption.rows = 2;
    caption.placeholder = 'What would you like to remember?';
    const count = document.createElement('p');
    count.className = 'memory-help memory-character-count';
    count.id = `memory-caption-count-${photo.key}`;
    count.textContent = '0 / 300 characters';
    caption.setAttribute('aria-describedby', count.id);
    caption.addEventListener('input', () => {
      photo.caption = caption.value;
      count.textContent = `${caption.value.length} / 300 characters`;
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'memory-button memory-remove';
    remove.textContent = 'Remove photo';
    remove.setAttribute('aria-label', `Remove photo ${photo.key + 1}: ${photo.file.name}`);
    remove.addEventListener('click', () => {
      const nextFocus = item.nextElementSibling?.querySelector('button') || item.previousElementSibling?.querySelector('button') || picker;
      selected = selected.filter((entry) => entry !== photo);
      URL.revokeObjectURL(photo.url);
      item.remove();
      updateCount();
      error.textContent = '';
      nextFocus.focus({ preventScroll: true });
    });
    item.append(image, label, caption, count, remove);
    return item;
  }

  picker.addEventListener('change', () => {
    const problems = [];
    for (const file of picker.files) {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        problems.push(`${file.name}: choose a JPG, PNG or WebP photo.`);
      } else if (file.size > 10 * 1024 * 1024) {
        problems.push(`${file.name}: choose a photo no larger than 10 MB.`);
      } else if (selected.length >= 3) {
        problems.push('You can save up to 3 photos at a time.');
        break;
      } else {
        const photo = { key: nextId++, file, caption: '', url: URL.createObjectURL(file) };
        selected.push(photo);
        previews.append(preview(photo));
      }
    }
    picker.value = '';
    error.textContent = problems.join(' ');
    updateCount();
  });

  function updateCard(card, memory) {
    card.dataset.caption = memory.caption;
    const link = card.querySelector('.memory-open');
    const image = link.querySelector('img');
    const caption = card.querySelector('.memory-caption');
    link.href = memory.image_url;
    link.setAttribute('aria-label', `Open memory: ${memory.caption || 'Photo without a description'}`);
    image.src = memory.image_url;
    image.alt = memory.caption || 'Travel memory';
    caption.textContent = memory.caption || 'No description yet.';
    caption.classList.toggle('memory-help', !memory.caption);
  }

  function createCard(memory) {
    const card = document.createElement('li');
    card.className = 'memory-card';
    card.dataset.memoryId = memory.id;
    const link = document.createElement('a');
    link.className = 'memory-open';
    const image = document.createElement('img');
    image.width = 640;
    image.height = 480;
    image.loading = 'lazy';
    image.decoding = 'async';
    link.append(image);
    const caption = document.createElement('p');
    caption.className = 'memory-caption';
    card.append(link, caption);
    updateCard(card, memory);
    return card;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (fields.disabled) return;
    if (selected.length < 1) {
      error.textContent = 'Please add at least 1 image to save your memories.';
      return;
    }
    error.textContent = '';
    const data = new FormData();
    selected.forEach((photo) => {
      data.append('images', photo.file);
      data.append('captions', photo.caption);
    });
    fields.disabled = true;
    form.setAttribute('aria-busy', 'true');
    saveButton.textContent = 'Saving memories…';
    status.textContent = 'Saving your photos…';
    try {
      const result = await api(section.dataset.endpoint, { method: 'POST', body: data });
      gallery.prepend(...result.memories.map(createCard));
      byId('memories-empty').hidden = true;
      closeForm();
      status.textContent = result.message;
    } catch (problem) {
      error.textContent = problem.message;
      status.textContent = '';
    } finally {
      fields.disabled = false;
      form.removeAttribute('aria-busy');
      saveButton.textContent = 'Save Memories';
    }
  });

  function resetViewer() {
    editForm.hidden = true;
    deleteConfirm.hidden = true;
    viewerActions.hidden = false;
    viewerError.textContent = '';
    viewerStatus.textContent = '';
  }

  gallery.addEventListener('click', (event) => {
    const link = event.target.closest('.memory-open');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (typeof viewer.showModal !== 'function') return;
    event.preventDefault();
    activeCard = link.closest('.memory-card');
    resetViewer();
    byId('memory-large-image').src = link.href;
    byId('memory-large-image').alt = activeCard.dataset.caption || 'Travel memory';
    byId('memory-viewer-caption').textContent = activeCard.dataset.caption || 'No description yet.';
    viewer.showModal();
    document.documentElement.classList.add('memory-viewing');
  });

  byId('close-memory').addEventListener('click', () => viewer.close());
  viewer.addEventListener('cancel', (event) => { if (viewerBusy) event.preventDefault(); });
  viewer.addEventListener('close', () => {
    document.documentElement.classList.remove('memory-viewing');
    byId('memory-large-image').removeAttribute('src');
    const focus = activeCard?.isConnected ? activeCard.querySelector('.memory-open') : (form.hidden ? addButton : picker);
    focus.focus({ preventScroll: true });
  });
  function countEdit() { byId('memory-edit-count').textContent = `${editCaption.value.length} / 300 characters`; }
  editCaption.addEventListener('input', countEdit);
  byId('edit-memory').addEventListener('click', () => {
    resetViewer();
    viewerActions.hidden = true;
    editForm.hidden = false;
    editCaption.value = activeCard.dataset.caption;
    countEdit();
    editCaption.focus();
  });
  byId('cancel-memory-edit').addEventListener('click', () => { resetViewer(); byId('edit-memory').focus(); });
  byId('delete-memory').addEventListener('click', () => {
    resetViewer();
    viewerActions.hidden = true;
    deleteConfirm.hidden = false;
    byId('cancel-memory-delete').focus();
  });
  byId('cancel-memory-delete').addEventListener('click', () => { resetViewer(); byId('delete-memory').focus(); });

  function setViewerBusy(busy, message = '') {
    viewerBusy = busy;
    viewer.querySelectorAll('button, textarea').forEach((control) => { control.disabled = busy; });
    viewer.setAttribute('aria-busy', String(busy));
    viewerStatus.textContent = message;
  }
  editForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (viewerBusy) return;
    viewerError.textContent = '';
    setViewerBusy(true, 'Saving description…');
    try {
      const result = await api(`${section.dataset.endpoint}/${activeCard.dataset.memoryId}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ caption: editCaption.value }),
      });
      updateCard(activeCard, result.memory);
      byId('memory-viewer-caption').textContent = result.memory.caption || 'No description yet.';
      byId('memory-large-image').alt = result.memory.caption || 'Travel memory';
      resetViewer();
      setViewerBusy(false, result.message);
      byId('edit-memory').focus();
    } catch (problem) {
      setViewerBusy(false);
      viewerError.textContent = problem.message;
    }
  });
  byId('confirm-memory-delete').addEventListener('click', async () => {
    if (viewerBusy) return;
    viewerError.textContent = '';
    setViewerBusy(true, 'Deleting memory…');
    try {
      const result = await api(`${section.dataset.endpoint}/${activeCard.dataset.memoryId}`, { method: 'DELETE' });
      activeCard.remove();
      byId('memories-empty').hidden = gallery.children.length > 0;
      setViewerBusy(false);
      viewer.close();
      status.textContent = result.message;
    } catch (problem) {
      setViewerBusy(false);
      viewerError.textContent = problem.message;
    }
  });
  window.addEventListener('beforeunload', (event) => {
    if (selected.length || viewerBusy) { event.preventDefault(); event.returnValue = ''; }
  });
})();
