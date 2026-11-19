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

for (const rates of document.querySelectorAll("[data-injury-rates]")) {
  const fields = rates.closest("form").elements;
  const hint = rates.parentElement.querySelector("[data-injury-rate]");
  function updateReference() {
    const day = fields.accident_date.value;
    const rate = Array.from(rates.children).map(node => node.dataset)
      .find(row => row.from <= day && (!row.to || row.to >= day));
    fields.confirmed_monthly_earnings.value = rate?.basis === "monthly" ? rate.amount : "";
    hint.textContent = rate ? (rate.basis === "monthly" ? rates.dataset.monthly : rates.dataset.daily) +
      " · " + rate.currency + " " + rate.amount : "";
    if (rate) fields.currency.value = rate.currency;
  }
  fields.accident_date.addEventListener("change", updateReference);
  updateReference();
}
