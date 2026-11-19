(() => {
  document.querySelectorAll("#attendance-review-form, .final-payment-form, [data-retain-form]").forEach(form => {
    form.addEventListener("submit", async event => {
      if (event.defaultPrevented || !form.reportValidity()) return;
      event.preventDefault();
      const submitter = event.submitter, data = new FormData(form);
      if (submitter && submitter.name) data.append(submitter.name, submitter.value);
      const alert = form.querySelector("[data-submit-message]") || document.createElement("p");
      alert.dataset.submitMessage = "1"; alert.className = "inline-alert"; alert.setAttribute("role", "status"); form.prepend(alert);
      if (submitter) submitter.disabled = true;
      try {
        const response = await fetch(form.action, {method:"POST", body:data, headers:{"X-HKR-Profile-Editor":"1"}});
        if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
          alert.textContent = form.dataset.retryText || "未能保存，輸入已保留，請重試。"; return;
        }
        const result = await response.json();
        if (result.replace_document_id) {
          alert.textContent = form.dataset.existingLabel + " " + result.filename + " ";
          const replace = document.createElement("button");
          replace.className = "secondary-btn danger-text";
          replace.type = "submit";
          replace.name = "replace_document_id";
          replace.value = result.replace_document_id;
          replace.dataset.explicitReplace = "1";
          replace.textContent = form.dataset.replaceLabel;
          alert.append(replace);
          alert.tabIndex = -1;
          alert.focus();
          alert.scrollIntoView({ behavior: "smooth", block: "center" });
        } else if (result.errors) alert.textContent = result.errors.join(" · ");
        else if (result.redirect) { location.assign(result.redirect); return; }
      } catch (error) { alert.textContent = form.dataset.retryText || "連線中斷，輸入已保留，請重試。"; }
      finally { if (submitter) submitter.disabled = false; }
    });
  });
  // Restore position only for the same URL when returning to a list.
  const key = "hkr-scroll:" + location.pathname + location.search;
  if (performance.getEntriesByType("navigation")[0]?.type === "back_forward") scrollTo(0, Number(sessionStorage.getItem(key) || 0));
  addEventListener("pagehide", () => sessionStorage.setItem(key, String(scrollY)));
})();
