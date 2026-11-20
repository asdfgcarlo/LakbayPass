document.querySelectorAll('.redeem-form').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button');
    button.disabled = true;
    button.textContent = 'Redeeming…';
    form.setAttribute('aria-busy', 'true');
  });
});
