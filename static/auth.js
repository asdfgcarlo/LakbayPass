(() => {
  const form = document.querySelector('.auth-form');
  if (!form) return;
  const fields = [...form.querySelectorAll('input')];
  const submit = form.querySelector('[type="submit"]');
  const label = submit.querySelector('.button-label');
  const status = form.querySelector('.submission-status');
  const idleLabel = label.textContent;
  const toggle = form.querySelector('.password-toggle');
  const password = form.elements.password;
  const touched = new Set();

  // Keep native validation available when JavaScript is unavailable.
  form.noValidate = true;
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const showing = password.type === 'password';
    password.type = showing ? 'text' : 'password';
    toggle.textContent = showing ? 'Hide' : 'Show';
    toggle.setAttribute('aria-label', showing ? 'Hide password' : 'Show password');
    toggle.setAttribute('aria-pressed', String(showing));
  });

  function messageFor(input) {
    const value = input.name === 'password' ? input.value : input.value.trim();
    if (!value) {
      return { username: 'Enter your username.', email: 'Enter your email address.', password: 'Enter your password.' }[input.name];
    }
    if (input.name === 'email' && input.validity.typeMismatch) return 'Enter an email address like name@example.com.';
    if (input.maxLength > 0 && value.length > input.maxLength) {
      return `Use ${input.maxLength} characters or fewer for your ${input.name === 'email' ? 'email address' : 'username'}.`;
    }
    return '';
  }
  function validate(input) {
    const message = messageFor(input);
    const error = document.getElementById(`${input.id}-error`);
    input.setAttribute('aria-invalid', String(Boolean(message)));
    error.textContent = message;
    error.hidden = !message;
    return !message;
  }
  fields.forEach(input => {
    input.addEventListener('blur', () => {
      touched.add(input);
      if (!input.dataset.serverError) validate(input);
    });
    input.addEventListener('input', () => {
      delete input.dataset.serverError;
      if (touched.has(input) || input.getAttribute('aria-invalid') === 'true') validate(input);
      if (!form.querySelector('[aria-invalid="true"]')) status.textContent = '';
    });
  });
  form.addEventListener('submit', event => {
    if (submit.disabled) {
      event.preventDefault();
      return;
    }
    fields.filter(input => input.name !== 'password').forEach(input => { input.value = input.value.trim(); });
    const invalid = fields.filter(input => {
      touched.add(input);
      return !validate(input);
    });
    if (invalid.length) {
      event.preventDefault();
      status.textContent = 'Check the highlighted fields and try again.';
      invalid[0].focus();
      return;
    }
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    label.textContent = form.dataset.pendingLabel;
    status.textContent = form.dataset.pendingLabel;
  });
  window.addEventListener('pageshow', () => {
    submit.disabled = false;
    form.removeAttribute('aria-busy');
    label.textContent = idleLabel;
    status.textContent = '';
    password.type = 'password';
    toggle.textContent = 'Show';
    toggle.setAttribute('aria-label', 'Show password');
    toggle.setAttribute('aria-pressed', 'false');
  });
  const firstError = fields.find(input => input.getAttribute('aria-invalid') === 'true');
  if (firstError) firstError.focus();
})();
