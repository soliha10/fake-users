(() => {
  const TOAST_DURATION_MS = 1800;
  const WAKE_MESSAGE_DELAY_MS = 3000;
  const BATCH_LINK_IDS = { ArrowLeft: "prev-batch", ArrowRight: "next-batch" };

  const form = document.getElementById("controls");
  const toast = document.getElementById("toast");
  const wakeMessage = document.getElementById("wake-message");
  let toastTimer;

  function showToast(text) {
    toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove("is-visible");
      toast.textContent = "";
    }, TOAST_DURATION_MS);
  }

  function startLoading(control) {
    control.classList.add("is-loading");
    control.setAttribute("aria-busy", "true");
    if (control.tagName === "BUTTON") control.disabled = true;
    setTimeout(() => { wakeMessage.hidden = false; }, WAKE_MESSAGE_DELAY_MS);
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Copied");
    } catch {
      showToast("Could not copy");
    }
  }

  function handleCopyClick(event) {
    const copyButton = event.target.closest("[data-copy]");
    if (copyButton) copyToClipboard(copyButton.dataset.copy);
    if (event.target.closest("#copy-link")) copyToClipboard(window.location.href);
  }

  function setUpDisclosure(button) {
    const user = button.closest(".user");
    button.addEventListener("click", () => {
      const isOpen = user.classList.toggle("is-open");
      button.setAttribute("aria-expanded", String(isOpen));
      button.setAttribute("aria-label", `${isOpen ? "Hide" : "Show"} details for ${button.dataset.person}`);
    });
  }

  function setUpBatchLink(link) {
    link.addEventListener("click", (event) => {
      const opensElsewhere = event.metaKey || event.ctrlKey || event.shiftKey;
      if (!opensElsewhere) startLoading(link);
    });
  }

  function setUpForm() {
    const seedInput = document.getElementById("seed");
    document.getElementById("locale").addEventListener("change", () => form.requestSubmit());
    document.getElementById("random-seed").addEventListener("click", () => {
      [seedInput.value] = crypto.getRandomValues(new Uint32Array(1));
      form.requestSubmit();
    });
    form.addEventListener("submit", () => startLoading(form.querySelector('[type="submit"]')));
  }

  function moveBatchWithArrowKeys(event) {
    const hasModifier = event.altKey || event.ctrlKey || event.metaKey || event.shiftKey;
    if (hasModifier || event.target.closest("input, select, textarea")) return;
    const link = document.getElementById(BATCH_LINK_IDS[event.key]);
    if (!link) return;
    startLoading(link);
    window.location.href = link.href;
  }

  function reloadPageRestoredFromCache(event) {
    if (event.persisted) window.location.reload();
  }

  if (navigator.clipboard) document.documentElement.classList.add("has-clipboard");
  window.addEventListener("pageshow", reloadPageRestoredFromCache);
  document.addEventListener("click", handleCopyClick);
  document.addEventListener("keydown", moveBatchWithArrowKeys);
  document.querySelectorAll(".disclosure").forEach(setUpDisclosure);
  document.querySelectorAll("#prev-batch, #next-batch").forEach(setUpBatchLink);
  if (form) setUpForm();
})();
