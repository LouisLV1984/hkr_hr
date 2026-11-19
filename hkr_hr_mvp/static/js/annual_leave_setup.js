/* Read-only previews; native form POST is the only write. */
document.querySelectorAll('[data-hire-date-policy]').forEach(panel => {
  const form = panel.closest('form');
  const start = form.querySelector('[name=start_date]');
  const action = panel.querySelector('[name=date_change_action]');
  let pending = false;
  form.addEventListener('input', event => {
    if (['start_date', 'initial_days'].includes(event.target.name)) action.value = '';
  });
  // Capture before the profile workspace's asynchronous submit handler.
  document.addEventListener('submit', async event => {
    if (event.target !== form || !start.value || start.value === panel.dataset.original || action.value) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (pending || form.querySelector('[data-setup-save]:disabled')) return;
    pending = true;
    const selectedDate = start.value;
    const initial = form.querySelector('[name=initial_days]')?.value || panel.dataset.initial;
    try {
      const query = new URLSearchParams({start_date:selectedDate, initial_days:initial, preserve:'0'});
      const response = await fetch(`${panel.dataset.url}?${query}`, {credentials:'same-origin'});
      if (!response.ok) throw new Error('invalid');
      const data = await response.json();
      const modal = document.createElement('dialog');
      modal.className = 'app-dialog record-editor-dialog';
      const body = document.createElement('div'); body.className = 'dialog-panel';
      const heading = document.createElement('h2'); heading.textContent = panel.dataset.title;
      const text = document.createElement('p');
      text.textContent = panel.dataset.label.replace('{year}', data.year).replace('{old}', data.old).replace('{new}', data.calculated);
      const buttons = document.createElement('div'); buttons.className = 'dialog-actions';
      const close = () => { pending = false; modal.close(); modal.remove(); };
      for (const [value, label] of [['recalculate', panel.dataset.recalculate], ['keep_current', panel.dataset.keep], ['', panel.dataset.cancel]]) {
        const button = document.createElement('button'); button.type = 'button';
        button.className = value === 'recalculate' ? 'primary-btn' : 'ghost-btn';
        button.textContent = label;
        button.addEventListener('click', () => {
          close();
          if (value && start.value === selectedDate && (form.querySelector('[name=initial_days]')?.value || panel.dataset.initial) === initial) {
            action.value = value; form.requestSubmit();
          }
        });
        buttons.append(button);
      }
      modal.addEventListener('cancel', event => {event.preventDefault(); close();});
      body.append(heading, text, buttons); modal.append(body); document.body.append(modal); modal.showModal();
    } catch (_) {
      pending = false;
      let error = panel.querySelector('[role=alert]');
      if (!error) {error = document.createElement('p'); error.setAttribute('role','alert'); panel.append(error);}
      error.textContent = panel.dataset.error;
    }
  }, true);
});
document.querySelectorAll('[data-annual-setup]').forEach(form => {
  let revision = 0;
  const result = form.querySelector('[data-setup-result]');
  const save = form.querySelector('[data-setup-save]');
  const preview = async () => {
    const version = ++revision;
    save.disabled = true;
    result.textContent = form.dataset.errorLabel;
    if (!form.checkValidity()) return;
    const query = new URLSearchParams(new FormData(form));
    query.delete('setup_token'); query.delete('csrf_token'); query.delete('_csrf_token');
    try {
      const response = await fetch(`${form.dataset.previewUrl}?${query}`, {credentials:'same-origin'});
      const data = await response.json();
      if (version !== revision || !response.ok) return;
      result.textContent = form.dataset.previewLabel.replace('{year}', data.year).replace('{old}', data.old).replace('{new}', data.calculated).replace('{used}', data.used).replace('{remaining}', data.remaining);
      save.disabled = false;
    } catch (_) { /* Keep save disabled until the preview succeeds. */ }
  };
  form.addEventListener('input', preview);
  form.addEventListener('submit', event => { if (save.disabled) event.preventDefault(); });
  preview();
});
document.querySelectorAll('[data-termination-leave]').forEach(panel => {
  const form = panel.closest('form');
  const input = form.querySelector('[name=end_date]');
  let revision = 0;
  input.addEventListener('change', async () => {
    const version = ++revision;
    panel.textContent = '';
    try {
      const response = await fetch(`${panel.dataset.url}?end_date=${encodeURIComponent(input.value)}`, {credentials:'same-origin'});
      const data = await response.json();
      if (!response.ok || version !== revision) return;
      panel.textContent = panel.dataset.label.replace('{entitled}', Number(data.entitled).toFixed(4)).replace('{used}', data.used).replace('{offset}', Number(data.offset).toFixed(4)).replace('{overused}', Number(data.overused).toFixed(4)).replace('{amount}', data.deduction === null ? panel.dataset.missing : data.deduction);
      if (data.pending) panel.textContent += ' ' + panel.dataset.pending;
      // The preview is inline within the existing departure dialog.
      panel.setAttribute('role', 'alert');
    } catch (_) { panel.textContent = panel.dataset.missing; }
  });
});
