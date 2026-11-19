(() => {
  const config = document.getElementById("attendance-rate-windows");
  if (!config) return;
  const windows = JSON.parse(config.textContent);
  const fields = ["working_days", "ot_hours", "sunday_holiday_days", "large_ecall_count"];
  const labels = JSON.parse(document.getElementById("attendance-rate-labels").textContent);
  function setup(row) {
    const input = row.querySelector("[data-rate-allocations]");
    if (!input || input.dataset.ready) return;
    const kind = input.name.replace(/_rate_allocations$/, "");
    if (!windows[kind] || windows[kind].length < 2) return;
    input.dataset.ready = "1";
    const saved = JSON.parse(input.value || "[]");
    let configured = saved.length === windows[kind].length && windows[kind].every((w,i) => saved[i].start === w.start && saved[i].end === w.end);
    const panel = document.createElement("fieldset"); panel.className = "rate-allocation wide";
    const legend = document.createElement("legend"); legend.textContent = labels.title; panel.append(legend);
    windows[kind].forEach(window => {
      const line = document.createElement("div"); line.className = "rate-allocation-row";
      line.dataset.start = window.start; line.dataset.end = window.end;
      const title = document.createElement("strong"); title.textContent = window.start + " — " + window.end + " · " + window.amount; line.append(title);
      const part = saved.find(r => r.start === window.start && r.end === window.end) || {};
      fields.forEach(field => {
        const original = row.querySelector('[name="' + kind + "_" + (field === "sunday_holiday_days" ? "holiday_days" : field) + '"]');
        if (!original || original.disabled) return;
        const label = document.createElement("label"), span = document.createElement("span"), number = document.createElement("input");
        span.textContent = original.closest("label")?.querySelector("span")?.textContent || labels[field]; number.type = "number"; number.min = "0";
        number.step = field === "large_ecall_count" ? "1" : "0.5"; number.value = part[field] || 0; number.dataset.rateField = field;
         if (field === "sunday_holiday_days" && row.querySelector("[data-special-work-picker]")) number.readOnly = true;
        label.append(span, number); line.append(label);
      });
      panel.append(line);
    });
    const sync = () => {
      const dated = JSON.parse(row.querySelector("[data-special-work-entries]")?.value || "[]");
       const parts = [...panel.querySelectorAll(".rate-allocation-row")].map(line => {
        const part = {start: line.dataset.start, end: line.dataset.end};
        line.querySelectorAll("[data-rate-field]").forEach(n => {
           if (n.readOnly && n.dataset.rateField === "sunday_holiday_days") n.value = dated.filter(d => d.date >= part.start && d.date <= part.end).reduce((total, d) => total + Number(d.days || 0), 0);
           part[n.dataset.rateField] = n.value || "0";
         });
        return part;
      });
      input.value = JSON.stringify(parts);
      fields.forEach(field => {
        const original = row.querySelector('[name="' + kind + "_" + (field === "sunday_holiday_days" ? "holiday_days" : field) + '"]');
        if (original && !original.disabled) { original.value = parts.reduce((sum, p) => sum + Number(p[field] || 0), 0); original.readOnly = true; }
      });
    };
    panel.addEventListener("input", () => { configured = true; sync(); }); row.append(panel);
    row.addEventListener("special-dates-changed", () => {
      if (!configured) configured = fields.filter(f => f !== "sunday_holiday_days").every(field => {
        const original = row.querySelector('[name="' + kind + "_" + field + '"]');
        return !original || original.disabled || Number(original.value || 0) === 0;
      });
      if (configured) sync();
    });
    if (configured) sync();
    // Existing aggregate-only entries remain visible until the operator supplies dates.
    // Do not silently replace saved totals with zero when the panel is first opened.
  }
  const root = document.getElementById("attendance-review-form");
  if (!root) return;
  const refresh = () => root.querySelectorAll("[data-segment-row]").forEach(setup);
  refresh(); root.addEventListener("segment-added", refresh);
})();
