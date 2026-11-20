for (const duration of document.querySelectorAll("[data-leave-duration]")) {
  const fields = duration.form.elements;
  const start = fields.start_date, end = fields.end_date;
  const first = fields.start_session, last = fields.end_session;
  duration.value = end.value !== start.value ? "range" : first.value === last.value ? first.value : "full";
  function synchronize() {
    const range = duration.value === "range";
    for (const input of [end, first, last]) input.closest("label").hidden = !range;
    if (!range) {
      end.value = start.value;
      first.value = duration.value === "pm" ? "pm" : "am";
      last.value = duration.value === "am" ? "am" : "pm";
    }
  }
  duration.addEventListener("change", () => {
    synchronize();
    end.dispatchEvent(new Event("change", {bubbles: true}));
  });
  start.addEventListener("change", synchronize);
  synchronize();
}

for (const select of document.querySelectorAll("[data-leave-type]")) {
  const form = select.closest("form");
  const rule = form?.querySelector("[data-leave-rule]");
  if (!rule) continue;
  const rules = {
    annual: select.dataset.ruleAnnual || "",
    sick: select.dataset.ruleSick || "",
    unpaid: select.dataset.ruleUnpaid || "",
  };
  const syncRule = () => {
    if (rules[select.value]) rule.textContent = rules[select.value];
  };
  select.addEventListener("change", syncRule);
  syncRule();
}

for (const rates of document.querySelectorAll("[data-injury-rates]")) {
  const fields = rates.closest("form").elements;
  const hint = rates.parentElement.querySelector("[data-injury-rate]");
  const rows = Array.from(rates.children).map(node => node.dataset);
  function updateReference() {
    const day = fields.accident_date.value;
    const rate = day
      ? rows.find(row => row.from <= day && (!row.to || row.to >= day))
      : rows[0];
    if (day) {
      fields.confirmed_monthly_earnings.value = rate?.basis === "monthly" ? rate.amount : "";
    }
    if (rate) {
      const label = rate.basis === "monthly" ? rates.dataset.monthly : rates.dataset.daily;
      hint.textContent = `${label} · ${rate.currency} ${rate.amount}${day ? "" : "（填寫意外日期後按該日薪酬更新）"}`;
      if (day) fields.currency.value = rate.currency;
    } else {
      hint.textContent = "";
    }
  }
  fields.accident_date.addEventListener("change", updateReference);
  updateReference();
}
