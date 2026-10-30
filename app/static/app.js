(() => {
  const TOAST_DURATION_MS = 1800;
  const WAKE_MESSAGE_DELAY_MS = 3000;
  const BATCH_LINK_IDS = { ArrowLeft: "prev-batch", ArrowRight: "next-batch" };

  const form = document.getElementById("controls");
  const toast = document.getElementById("toast");
  const wakeMessage = document.getElementById("wake-message");
  let toastTimer;
  let wakeTimer;
  let pendingRequest;

  function showToast(text) {
    toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove("is-visible");
      toast.textContent = "";
    }, TOAST_DURATION_MS);
  }

  function setLoading(control, isLoading) {
    control.classList.toggle("is-loading", isLoading);
    control.setAttribute("aria-busy", String(isLoading));
    if (control.tagName === "BUTTON") control.disabled = isLoading;
  }

  function startLoading(control) {
    setLoading(control, true);
    clearTimeout(wakeTimer);
    wakeTimer = setTimeout(() => { wakeMessage.hidden = false; }, WAKE_MESSAGE_DELAY_MS);
  }

  function stopLoading() {
    clearTimeout(wakeTimer);
    wakeMessage.hidden = true;
    setLoading(form.querySelector('[type="submit"]'), false);
  }

  function syncFormWith(page) {
    document.getElementById("locale").value = page.getElementById("locale").value;
    document.getElementById("seed").value = page.getElementById("seed").value;
  }

  function showPage(page) {
    const focusedId = document.activeElement.id;
    const results = document.getElementById("results");
    results.replaceWith(page.getElementById("results"));
    syncFormWith(page);
    document.getElementById(focusedId)?.focus();
    const newResults = document.getElementById("results");
    if (newResults.getBoundingClientRect().top < 0) newResults.scrollIntoView();
  }

  async function loadPage(url, { addToHistory }) {
    pendingRequest?.abort();
    pendingRequest = new AbortController();
    try {
      const response = await fetch(url, { signal: pendingRequest.signal });
      if (!response.ok) {
        window.location.assign(url);
        return;
      }
      showPage(new DOMParser().parseFromString(await response.text(), "text/html"));
      if (addToHistory) window.history.pushState(null, "", url);
      stopLoading();
    } catch (error) {
      if (error.name !== "AbortError") window.location.assign(url);
    }
  }

  function goToBatch(link) {
    startLoading(link);
    loadPage(link.href, { addToHistory: true });
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      showToast("Copied");
    } catch {
      showToast("Could not copy");
    }
  }

  function toggleDetails(button) {
    const isOpen = button.closest(".user").classList.toggle("is-open");
    button.setAttribute("aria-expanded", String(isOpen));
    button.setAttribute("aria-label", `${isOpen ? "Hide" : "Show"} details for ${button.dataset.person}`);
  }

  function handleClick(event) {
    const copyButton = event.target.closest("[data-copy]");
    const disclosure = event.target.closest(".disclosure");
    const batchLink = event.target.closest("#prev-batch, #next-batch");
    const opensElsewhere = event.metaKey || event.ctrlKey || event.shiftKey;
    if (copyButton) copyToClipboard(copyButton.dataset.copy);
    if (event.target.closest("#copy-link")) copyToClipboard(window.location.href);
    if (disclosure) toggleDetails(disclosure);
    if (batchLink && !opensElsewhere) {
      event.preventDefault();
      goToBatch(batchLink);
    }
  }

  function submitForm(event) {
    event.preventDefault();
    startLoading(form.querySelector('[type="submit"]'));
    const query = new URLSearchParams(new FormData(form));
    loadPage(`${form.action}?${query}`, { addToHistory: true });
  }

  function setUpForm() {
    const seedInput = document.getElementById("seed");
    document.getElementById("locale").addEventListener("change", () => form.requestSubmit());
    document.getElementById("random-seed").addEventListener("click", () => {
      [seedInput.value] = crypto.getRandomValues(new Uint32Array(1));
      form.requestSubmit();
    });
    form.addEventListener("submit", submitForm);
    window.addEventListener("popstate", () => loadPage(window.location.href, { addToHistory: false }));
  }

  function moveBatchWithArrowKeys(event) {
    const hasModifier = event.altKey || event.ctrlKey || event.metaKey || event.shiftKey;
    if (hasModifier || event.target.closest("input, select, textarea")) return;
    const link = document.getElementById(BATCH_LINK_IDS[event.key]);
    if (link) goToBatch(link);
  }

  function reloadPageRestoredFromCache(event) {
    if (event.persisted) window.location.reload();
  }

  if (navigator.clipboard) document.documentElement.classList.add("has-clipboard");
  window.addEventListener("pageshow", reloadPageRestoredFromCache);
  document.addEventListener("click", handleClick);
  document.addEventListener("keydown", moveBatchWithArrowKeys);
  if (form) setUpForm();
})();
