(() => {
  const dialog = document.querySelector("#past-attendance");
  if (!dialog) return;
  const opener = document.querySelector("[data-corr-open]");
  const source = dialog.querySelector("[data-corr-month]");
  const body = dialog.querySelector("[data-corr-body]");
  const history = document.querySelector("[data-corr-history]");
  const words = JSON.parse(dialog.querySelector("script").textContent);
  const sourceLink = dialog.querySelector("[data-corr-source-link]");
  const money = (value, currency) => currency + " " + Number(value).toLocaleString(document.documentElement.lang || "zh-HK", {
    minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: "exceptZero"
  });
  let generation = 0;
  let timer;
  let saving = false;
  async function load() {
    const token = ++generation;
    body.textContent = "";
    sourceLink.replaceChildren();
    if (!source.reportValidity()) return;
    try {
      const response = await fetch(dialog.dataset.url.replace("SOURCE", source.value));
      if (!response.ok) throw Error(words.failed);
      const html = await response.text();
      if (token !== generation) return;
      body.innerHTML = html;
      sourceLink.append(body.querySelector("[data-corr-source]"));
      schedule();
    } catch (e) { if (token === generation) body.textContent = words.failed; }
  }
  opener.addEventListener("click", () => {
    source.value = source.max;
    dialog.showModal();
    load();
  });
  source.addEventListener("change", load);
  function schedule() {
    const form = body.querySelector("form");
    if (!form) return;
    const token = ++generation;
    clearTimeout(timer);
    const rows = [...form.querySelectorAll("[data-corr-row]")];
    for (const row of rows) {
      const workDate = row.querySelector("[name=work_date]").value;
      const show = source.value === source.max && Number(workDate.slice(8)) >= 21;
      row.querySelector("[data-tail-choice]").hidden = !show;
      row.querySelector("[name=tail]").required = show;
      row.querySelector("[name=quantity]").max = row.querySelector("[name=kind]").value === "ot" ? 24 : 1;
      row.querySelector("output").textContent = "—";
    }
    const total = form.querySelector("[data-corr-total]");
    const units = form.querySelector("[data-corr-units]");
    total.dataset.state = "pending";
    total.textContent = words.pending;
    units.textContent = "";
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    if (!form.checkValidity() || (!rows.length && form.elements.revision.value === "0")) return;
    timer = setTimeout(async () => {
      try {
        const data = new FormData(form);
        data.delete("evidence");
        data.set("action", "preview");
        const response = await fetch(form.action, {method:"POST", body:data});
        const result = await response.json();
        if (token !== generation) return;
        if (!response.ok) throw Error(result.error || words.failed);
        const changes = new Map();
        result.lines.forEach((line,i) => {
          const amount = rows[i].querySelector("output");
          amount.textContent = money(line.amount, result.currency);
          const explanation = line.included ? words.included : (line.kind === "day" && Number(line.rate) === 0 ? words.fixed : "");
          if (explanation) {
            const note = document.createElement("small");
            note.textContent = explanation;
            amount.append(note);
          }
          const key = (line.date.slice(8) <= "20" ? words.period1 : words.period2) + " " + words[line.kind];
          changes.set(key,(changes.get(key) || 0) + Number(line.quantity) * (line.direction === "add" ? 1 : -1));
        });
        total.dataset.state = "ready";
        total.textContent = money(result.total, result.currency);
        units.textContent = [...changes].map(([k,v]) => k + " " + (v > 0 ? "+" : "") + v).join("　");
        submit.disabled = false;
      } catch (e) { if (token === generation) total.textContent = e.message || words.failed; }
    }, 100);
  }
  dialog.addEventListener("change", e => {
    if (e.target.name !== "evidence") return;
    const names = Array.from(e.target.files, file => {
      const label = document.createElement("span");
      label.textContent = file.name;
      return label;
    });
    body.querySelector("[data-corr-files]").replaceChildren(...names);
  });
  dialog.addEventListener("input", e => { if (e.target.closest("[data-corr-row]")) schedule(); });
  dialog.addEventListener("cancel",e => { if (saving) e.preventDefault(); });
  dialog.addEventListener("click", e => {
    if (saving) return;
    if (e.target.closest("[data-corr-close]")) dialog.close();
    if (e.target.closest("[data-corr-add]")) {
      const row = body.querySelector("template").content.cloneNode(true);
      body.querySelector("[data-corr-rows]").append(row);
      body.querySelector("[data-corr-row]:last-child input").focus();
      schedule();
    }
    if (e.target.closest("[data-corr-remove]")) {
      e.target.closest("[data-corr-row]").remove();
      schedule();
    }
  });
  dialog.addEventListener("submit",async e => {
    e.preventDefault();
    const form = e.target;
    if (saving || form.querySelector("[type=submit]").disabled) return;
    saving = true;
    const data = new FormData(form);
    const controls = [...dialog.querySelectorAll("button,select,input")];
    controls.forEach(c => c.disabled = true);
    try {
      const response = await fetch(form.action,{method:"POST",body:data});
      if (response.status === 413) throw Error(words.size);
      if (!response.headers.get("Content-Type")?.includes("application/json")) throw Error(words.failed);
      const result = await response.json();
      if (!response.ok) throw Error(result.error || words.failed);
      history.innerHTML = result.history;
      dialog.close();
      opener.focus();
    } catch(e) {
      form.querySelector("[data-corr-total]").textContent = e.message || words.failed;
    } finally {
      controls.forEach(c => c.disabled = false);
      saving = false;
    }
  });
})();
