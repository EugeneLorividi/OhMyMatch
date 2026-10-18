// Show the wait indicator and block double submits on slow forms (OCR).
document.addEventListener("submit", (event) => {
  const form = event.target;
  const wait = form.querySelector("[data-wait]");
  if (!wait) return;
  wait.hidden = false;
  for (const button of form.querySelectorAll("button[type=submit]")) {
    button.disabled = true;
  }
});
