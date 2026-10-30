(() => {
  const form = document.getElementById("controls");
  const seed = document.getElementById("seed");
  const toast = document.getElementById("toast");
  const wakeMessage = document.getElementById("wake-message");
  const WAKE_DELAY_MS = 3000;
  let toastTimer;

  function showToast(text) {
    toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove("is-visible");
      toast.textContent = "";
    }, 1800);
  }

  function startLoading(control) {
    control.classList.add("is-loading");
    control.setAttribute("aria-busy", "true");
    if (control.tagName === "BUTTON") control.disabled = true;
    if (wakeMessage) {
      setTimeout(() => { wakeMessage.hidden = false; }, WAKE_DELAY_MS);
    }
  }

  // Restored pages from the back/forward cache must not stay in a loading state.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) window.location.reload();
  });

  if (navigator.clipboard) {
    document.documentElement.classList.add("has-clipboard");
  }

  document.addEventListener("click", async (event) => {
    const copyButton = event.target.closest("[data-copy]");
    const copyLink = event.target.closest("#copy-link");
    if (!copyButton && !copyLink) return;
    try {
      await navigator.clipboard.writeText(copyLink ? window.location.href : copyButton.dataset.copy);
      showToast("Copied");
    } catch {
      showToast("Could not copy");
    }
  });

  document.querySelectorAll(".disclosure").forEach((button) => {
    const user = button.closest(".user");
    const name = button.getAttribute("aria-label").replace("Show details for ", "");
    button.addEventListener("click", () => {
      const open = user.classList.toggle("is-open");
      button.setAttribute("aria-expanded", String(open));
      button.setAttribute("aria-label", `${open ? "Hide" : "Show"} details for ${name}`);
    });
  });

  document.querySelectorAll("#prev-batch, #next-batch").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey) return;
      startLoading(link);
    });
  });

  if (form) {
    document.getElementById("locale").addEventListener("change", () => form.requestSubmit());
    document.getElementById("random-seed").addEventListener("click", () => {
      const [value] = crypto.getRandomValues(new Uint32Array(1));
      seed.value = value;
      form.requestSubmit();
    });
    form.addEventListener("submit", () => startLoading(form.querySelector('[type="submit"]')));
  }

  document.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.target.closest("input, select, textarea")) return;
    const target = { ArrowLeft: "prev-batch", ArrowRight: "next-batch" }[event.key];
    const link = target && document.getElementById(target);
    if (link) {
      startLoading(link);
      window.location.href = link.href;
    }
  });
})();
