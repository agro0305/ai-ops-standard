(() => {
  const root = document.documentElement;
  const themeButton = document.querySelector("#theme-button");

  function storedTheme() {
    try {
      const value = window.localStorage.getItem("aiops-theme");
      return value === "light" || value === "dark" ? value : null;
    } catch {
      return null;
    }
  }

  function saveTheme(theme) {
    try {
      window.localStorage.setItem("aiops-theme", theme);
    } catch {
      // Theme switching must still work when browser storage is unavailable.
    }
  }

  function setTheme(theme) {
    root.dataset.theme = theme;
    saveTheme(theme);
    if (!themeButton) return;
    const dark = theme === "dark";
    themeButton.textContent = dark ? "☀" : "☾";
    themeButton.setAttribute("aria-label", dark ? "Uključi svetlu temu" : "Uključi tamnu temu");
    themeButton.setAttribute("title", dark ? "Uključi svetlu temu" : "Uključi tamnu temu");
    themeButton.setAttribute("aria-pressed", dark ? "false" : "true");
  }

  const prefersLight = window.matchMedia?.("(prefers-color-scheme: light)").matches === true;
  setTheme(storedTheme() || (prefersLight ? "light" : "dark"));

  themeButton?.addEventListener("click", () => {
    setTheme(root.dataset.theme === "dark" ? "light" : "dark");
  });

  for (const button of document.querySelectorAll("[data-tab-target]")) {
    button.addEventListener("click", () => {
      const group = button.dataset.tabGroup;
      for (const peer of document.querySelectorAll(`[data-tab-group="${group}"]`)) {
        const active = peer === button;
        peer.classList.toggle("active", active);
        peer.setAttribute("aria-selected", active ? "true" : "false");
      }
      for (const panel of document.querySelectorAll(`[data-tab-panel="${group}"]`)) {
        const active = panel.id === button.dataset.tabTarget;
        panel.classList.toggle("active", active);
        panel.hidden = !active;
      }
    });
  }
})();
