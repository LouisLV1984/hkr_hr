/* Progressive enhancement for employee editors. Drafts stay in this page's memory. */
(() => {
  "use strict";
  const root = document.querySelector("[data-profile-workspace]");
  if (!root) return;
  const copy = JSON.parse(root.textContent);
  const forms = [...document.querySelectorAll("main form[method=post], main form[method=POST]")]
    .filter(form => !form.matches(".mini-form, .duplicate-actions, [data-profile-guard-skip]"));
  const initial = new Map();
  let navigating = false;
  let saving = false;
  function navigateTo(destination) {
    const samePage = destination.pathname === location.pathname && destination.search === location.search;
    navigating = true;
    if (samePage) {
      // A same-page redirect with only #employee-leave changed would leave the
      // saved dialog and old history visible. Refresh without replaying POST.
      history.replaceState(null, "", destination.href);
      window.location.reload();
    } else window.location.assign(destination.href);
  }
  const controls = form => [...form.elements].filter(el => el.name && !el.disabled
    && !el.readOnly && !["submit", "button", "reset"].includes(el.type)
    && el.name !== "_csrf_token");
  const scalarValue = el => {
    const raw = el.value.replace(/,/g, "").trim();
    // Formatting 15000 as 15,000.00 on blur is not an HR edit.
    return el.hasAttribute("data-money-input") && raw && Number.isFinite(Number(raw))
      ? String(Number(raw)) : el.value;
  };
  const value = el => el.type === "file"
    ? [...el.files].map(file => [file.name, file.size, file.lastModified])
    : ["checkbox", "radio"].includes(el.type) ? el.checked
    : el.multiple ? [...el.selectedOptions].map(option => option.value) : scalarValue(el);
  const snapshot = form => controls(form).map(el => [el, JSON.stringify(value(el))]);
  const changed = form => (initial.get(form) || []).some(([el, old]) => JSON.stringify(value(el)) !== old);
  const dirtyForms = except => forms.filter(form => form !== except && changed(form));
  const discard = list => list.forEach(form => {
    (initial.get(form) || []).forEach(([el, old]) => {
      const saved = JSON.parse(old);
      if (el.type === "file") el.value = "";
      else if (["checkbox", "radio"].includes(el.type)) el.checked = saved;
      else if (el.multiple) [...el.options].forEach(option => { option.selected = saved.includes(option.value); });
      else el.value = saved;
      el.dispatchEvent(new Event("change", {bubbles: true}));
    });
    form.querySelector("[data-save-error]")?.remove();
    form.querySelectorAll("[aria-invalid]").forEach(el => el.removeAttribute("aria-invalid"));
  });
  function allowDiscard(list) {
    if (saving) { window.alert(copy.saving); return false; }
    if (!list.length) return true;
    if (!window.confirm(copy.discard)) return false;
    discard(list);
    return true;
  }
  // Capture before existing tab, backdrop and Cancel listeners can hide an editor.
  document.addEventListener("click", event => {
    const closer = event.target.closest("[data-dialog-close]");
    const backdrop = event.target.matches("dialog.app-dialog") ? event.target : null;
    const tab = event.target.closest("[data-tab], [data-open-tab]");
    const link = event.target.closest("a[href]");
    let affected = [];
    if (closer || backdrop) {
      const dialog = backdrop || closer.closest("dialog");
      affected = forms.filter(form => dialog?.contains(form) && changed(form));
    } else if (tab && !tab.classList.contains("active")) affected = dirtyForms();
    else if (link && !link.target && !link.hasAttribute("download") && !event.ctrlKey && !event.metaKey) {
      const url = new URL(link.href, location.href);
      const samePage = url.pathname === location.pathname && url.search === location.search;
      if (!samePage && !/\/(download|bundle)$/.test(url.pathname)) affected = dirtyForms();
    }
    if ((affected.length || (saving && (closer || backdrop || tab || link))) && !allowDiscard(affected)) {
      event.preventDefault(); event.stopImmediatePropagation();
    }
  }, true);
  document.querySelectorAll("dialog.app-dialog").forEach(dialog => dialog.addEventListener("cancel", event => {
    if (!allowDiscard(forms.filter(form => dialog.contains(form) && changed(form)))) event.preventDefault();
  }));
  window.addEventListener("beforeunload", event => {
    if (!navigating && (saving || dirtyForms().length)) { event.preventDefault(); event.returnValue = ""; }
  });
  // A quick action must not commit and only then ask about another dirty form.
  document.addEventListener("submit", event => {
    if (forms.includes(event.target) || event.target.id === "quick-reference-form" || !dirtyForms().length) return;
    if (!allowDiscard(dirtyForms())) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, true);
  document.querySelectorAll("main .mini-form").forEach(form => {
    if (/\/(void|withdraw|status)$/.test(new URL(form.action).pathname)) {
      form.querySelector("button")?.setAttribute("title", copy.void);
    }
  });

  const insertionPoint = form => form.querySelector(":scope > .record-editor-body, :scope > .form-grid") || form;
  function note(form, attribute, className, text) {
    let box = form.querySelector("[" + attribute + "]");
    if (!box) {
      box = document.createElement("p"); box.setAttribute(attribute, "");
      box.className = className + " wide";
      box.setAttribute("role", attribute === "data-save-error" ? "alert" : "status");
      box.tabIndex = -1; insertionPoint(form).prepend(box);
    }
    box.textContent = text;
    return box;
  }
  function impact(form) {
    const path = new URL(form.action).pathname;
    const tracked = /salary|salaries|assignment|employment|probation|terminat|rehire|personal|review/.test(path);
    if (!tracked) return;
    const applied = form.elements.apply_contract_terms;
    const fields = (initial.get(form) || []).filter(([el, old]) => JSON.stringify(value(el)) !== old
      && ["start_date", "end_date", "effective_from", "effective_to", "confirmation_date",
        "probation_end_date", "workweek_days", "monthly_pay_method", "contract_annual_leave_days",
        "contract_effective_date"].includes(el.name)
      && (!applied || applied.checked));
    if (!fields.length) { form.querySelector("[data-impact-note]")?.remove(); return; }
    const dates = fields.flatMap(([el, old]) => [JSON.parse(old), el.value])
      .filter(item => typeof item === "string" && /^\d{4}-\d{2}-\d{2}$/.test(item)).sort();
    const effective = form.elements.effective_from?.value || form.elements.start_date?.value
      || form.elements.contract_effective_date?.value;
    if (effective && !dates.length) dates.push(effective);
    const months = [...new Set(dates.map(item => item.slice(0, 7)))];
    const period = months.length ? months[0] + (months.length > 1 ? " ～ " + months[months.length - 1] : "") : copy.effectivePeriod;
    const topic = fields.some(([el]) => ["start_date", "end_date", "contract_annual_leave_days"].includes(el.name))
      ? copy.leaveImpact : fields.some(([el]) => /confirmation|probation/.test(el.name))
        ? copy.probationImpact : copy.payImpact;
    note(form, "data-impact-note", "inline-note impact-note", copy.impactPrefix + period + " · " + topic + " " + copy.historyImpact);
  }
  function explainAction(form) {
    if (form.querySelector("[data-action-hint]")) return;
    const path = new URL(form.action).pathname;
    let message = /\/(correct|update)$/.test(path) ? copy.correct
      : /\/(replace)$/.test(path) ? copy.replace
      : /\/(evidence)$/.test(path) ? copy.evidence
      : /\/(void|withdraw|status)$/.test(path) ? copy.void
      : /\/(salaries|assignments|certificates|identities|visas|qualifications)$/.test(path) ? copy.add : "";
    if (/\/(certificates|identities|visas|qualifications)$/.test(path)) message += " " + copy.renew;
    if (message) note(form, "data-action-hint", "form-note action-hint", message);
  }
  function showError(form, message) {
    const box = note(form, "data-save-error", "flash flash-error", message);
    const edited = (initial.get(form) || []).filter(([el, old]) => JSON.stringify(value(el)) !== old);
    const matches = edited.map(([el]) => el).filter(el => {
      const label = el.closest("label")?.querySelector("span")?.textContent.replace("*", "").trim();
      return (label && message.includes(label)) || (el.type === "date" && /日期|到期|date|expiry/i.test(message))
        || (/identity.*number/.test(el.name) && /身份|identity/i.test(message));
    });
    matches.forEach(el => el.setAttribute("aria-invalid", "true"));
    (matches.find(el => el.offsetParent !== null) || box).focus();
    box.scrollIntoView({block: "nearest"});
  }
  forms.forEach(form => {
    initial.set(form, snapshot(form));
    explainAction(form);
    form.addEventListener("input", event => { event.target.removeAttribute("aria-invalid"); impact(form); });
    form.addEventListener("change", () => impact(form));
    form.addEventListener("submit", async event => {
      if (event.defaultPrevented) return;
      event.preventDefault();
      if (saving || !form.reportValidity()) return;
      if (dirtyForms(form).length && !window.confirm(copy.otherChanges)) return;
      const buttons = [...form.querySelectorAll("button[type=submit], input[type=submit]")];
      const disabled = buttons.map(button => button.disabled);
      const payload = new FormData(form);
      if (event.submitter?.name) payload.append(event.submitter.name, event.submitter.value);
      saving = true; buttons.forEach(button => { button.disabled = true; });
      form.setAttribute("aria-busy", "true");
      form.querySelector("[data-save-error]")?.remove();
      try {
        const response = await fetch(form.action, {method: "POST", body: payload, credentials: "same-origin",
          headers: {"X-HKR-Profile-Editor": "1"}});
        if (response.headers.get("content-type")?.includes("application/json")) {
          const result = await response.json();
          if (!response.ok || result.errors?.length) {
            showError(form, result.errors?.join("\n") || copy.failed); return;
          }
          if (result.redirect) {
            const destination = new URL(result.redirect, location.href);
            if (destination.origin !== location.origin) { showError(form, copy.failed); return; }
            if (destination.pathname === "/login") { showError(form, copy.sessionExpired); return; }
            navigateTo(destination); return;
          }
          showError(form, copy.failed); return;
        }
        const html = await response.text();
        const result = new DOMParser().parseFromString(html, "text/html");
        if (new URL(response.url).pathname === "/login") { showError(form, copy.sessionExpired); return; }
        const errors = [...result.querySelectorAll(".flash-error, .flash-danger")].map(el => el.textContent.trim());
        if (!response.ok && response.status < 500 && !errors.length) {
          const detail = result.querySelector('[data-error-detail]')?.textContent.trim();
          if (detail) errors.push(detail);
        }
        if (!response.ok || errors.length) {
          showError(form, errors.join("\n") || (response.status >= 500 ? copy.uncertain : copy.failed));
          return;
        }
        if (!response.redirected) {
          // Successful upload can require the existing identical-file confirmation.
          // Only navigate this server-rendered stage; never resubmit a POST automatically.
          if (result.querySelector('input[name="duplicate_token"]')) {
            document.querySelector("main").innerHTML = result.querySelector("main").innerHTML;
            initial.clear(); forms.length = 0;
            document.querySelectorAll('main form[method="post"]').forEach(next => {
              const csrf = document.createElement("input"); csrf.type = "hidden"; csrf.name = "_csrf_token";
              csrf.value = document.querySelector('meta[name="csrf-token"]').content; next.append(csrf);
            });
            document.querySelector("main h2")?.scrollIntoView({block: "center"});
            return;
          }
          showError(form, copy.failed); return;
        }
        navigateTo(new URL(response.url));
      } catch (_) {
        // A lost response does not prove that the server rolled back.
        showError(form, copy.uncertain);
      } finally {
        saving = false; form.removeAttribute("aria-busy");
        buttons.forEach((button, index) => { button.disabled = disabled[index]; });
      }
    });
  });
  const library = document.querySelector("[data-document-library]");
  if (library) {
    const filters = [...library.querySelectorAll("[data-document-filter]")];
    filters.forEach(button => button.addEventListener("click", () => {
      filters.forEach(other => other.setAttribute("aria-pressed", String(other === button)));
      let visible = 0;
      library.querySelectorAll("tr[data-document-category]").forEach(row => {
        row.hidden = !!button.dataset.documentFilter && row.dataset.documentCategory !== button.dataset.documentFilter;
        if (!row.hidden) visible++;
      });
      const empty = library.querySelector("[data-library-empty]");
      if (empty) empty.hidden = visible > 0;
    }));
  }
})();
