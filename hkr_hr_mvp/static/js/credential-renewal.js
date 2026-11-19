for (const button of document.querySelectorAll("[data-dialog-open$='-add-dialog']")) {
  const form = document.getElementById(button.dataset.dialogOpen)?.querySelector("form");
  if (!form) continue;
  button.addEventListener("click", () => {
    const past = form.querySelector('input[name="renews_id"]');
    if (!past && !button.dataset.renewId) return;
    const title = form.querySelector("h2");
    const begins = form.elements.valid_from || form.elements.issue_date;
    if (past) {
      past.remove();
      form.reset();
      title.textContent = title.dataset.originalTitle;
      begins.required = false;
    }
    if (!button.dataset.renewId) return;
    const source = document.createElement("input");
    source.type = "hidden";
    source.name = "renews_id";
    source.value = button.dataset.renewId;
    form.append(source);
    title.dataset.originalTitle = title.textContent;
    title.textContent = button.dataset.renewLabel + " · " +
      button.closest("article").querySelector(".credential-record-main strong").textContent;
    begins.required = true;
    form.elements[button.dataset.renewType].value = button.dataset.renewValue;
    if (button.dataset.renewName) form.elements.qualification_name.value = button.dataset.renewName;
  });
}
