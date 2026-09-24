(() => {
  const form = document.getElementById('salary-record-editor');
  if (!form) return;
  const labels = JSON.parse(document.getElementById('salary-record-labels').textContent);
  const message = document.getElementById('salary-record-message');
  let dirty = false, leaving = false, busy = false;
  const number = input => input.value.trim() === '' ? null : Number(input.value.replaceAll(',', ''));
  const displayMoney = value => value.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  function formatInput(input) {
    const raw = input.value.replaceAll(',', '').trim();
    // Leave invalid or over-precision values intact for server validation; never silently round them.
    if (/^[+-]?\d+(?:\.\d{0,2})?$/.test(raw) && Number.isFinite(Number(raw))) input.value = displayMoney(Number(raw));
  }
  const csrf = () => document.querySelector('meta[name="csrf-token"]').content;
  function refresh(row, autofill = false) {
    const fields = Object.fromEntries([...row.querySelectorAll('[data-money]')].map(input => [input.dataset.money, input]));
    const gross = number(fields.gross_amount), mpf = number(fields.employee_mpf);
    if (autofill && row.dataset.netManual !== '1' && gross !== null && mpf !== null && Number.isFinite(gross) && Number.isFinite(mpf)) fields.net_amount.value = displayMoney(gross-mpf);
    const net = number(fields.net_amount), note = row.querySelector('.salary-record-difference');
    const values = [gross,mpf,net];
    note.textContent = values.every(n => n !== null && Number.isFinite(n)) && Math.abs(gross-mpf-net) > 0.005 ? labels.difference : '';
    if (values.some(n => n !== null && n < 0)) note.textContent += ' ' + labels.negative;
  }
  form.querySelectorAll('[data-salary-row]').forEach(row => refresh(row));
  form.addEventListener('focusout', event => {
    if (event.target.matches('[data-money]')) formatInput(event.target);
  });
  form.addEventListener('input', event => {
    dirty = true;
    const row = event.target.closest('[data-salary-row]');
    if (!row) return;
    if (event.target.dataset.money === 'net_amount') row.dataset.netManual = event.target.value.trim() ? '1' : '0';
    refresh(row, event.target.dataset.money === 'gross_amount' || event.target.dataset.money === 'employee_mpf');
  });
  form.addEventListener('change', () => { dirty = true; });
  window.addEventListener('beforeunload', event => { if (dirty && !leaving) { event.preventDefault(); event.returnValue = ''; } });
  async function post(url, body) {
    if (busy) return;
    busy = true;
    const buttons = [...form.querySelectorAll('button')];
    buttons.forEach(b => b.disabled = true);
    try {
      const response = await fetch(url, {method:'POST', body, headers:{'X-CSRF-Token':csrf()}});
      const result = await response.json().catch(() => { throw new Error(labels.failed); });
      if (!response.ok || !result.redirect) throw new Error(result.error || labels.failed);
      leaving = true; window.location.assign(result.redirect);
    } catch(error) { message.textContent = error.message || labels.failed; message.classList.add('danger-text'); }
    finally { busy = false; buttons.forEach(b => b.disabled = false); }
  }
  form.addEventListener('submit', event => { event.preventDefault(); post(form.action, new FormData(form)); });
  form.addEventListener('click', async event => {
    const prefill = event.target.closest('[data-prefill]'), withdraw = event.target.closest('[data-withdraw]');
    if (prefill) {
      if (!window.confirm(labels.prefill_confirm)) return;
      prefill.disabled = true;
      try {
        const response = await fetch(prefill.dataset.prefill), data = await response.json().catch(() => { throw new Error(labels.failed); });
        if (!response.ok) throw new Error(data.error || labels.failed);
        const row = prefill.closest('[data-salary-row]');
        const currency = row.querySelector('select[name$=".currency"]');
        if (![...currency.options].some(option => option.value === data.values.currency)) throw new Error(labels.invalid_currency);
        Object.entries(data.values).forEach(([key,value]) => {
          const input = row.querySelector(`[name="${row.dataset.employeeId}.${key}"]`);
          input.value=value;
          if (input.matches('[data-money]')) formatInput(input);
        });
        row.dataset.netManual='1'; dirty=true; refresh(row); message.textContent=data.message;
      } catch(error) { message.textContent=error.message || labels.failed; }
      finally { prefill.disabled=false; }
    }
    if (withdraw) {
      if (dirty && !window.confirm(labels.discard)) return;
      const reason = window.prompt(labels.withdraw_reason);
      if (!reason?.trim()) return;
      const body = new FormData(); body.set('_csrf_token',csrf()); body.set('reason',reason); body.set('revision',withdraw.dataset.revision);
      post(withdraw.dataset.withdraw,body);
    }
  });
})();
