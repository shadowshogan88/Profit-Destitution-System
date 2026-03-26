
(function () {
  const html = document.documentElement;
  const defaultTheme = "light";

  try {
    const savedConfig = JSON.parse(sessionStorage.getItem("__THEME_CONFIG__")) || {};
    html.setAttribute("data-bs-theme", savedConfig.theme || defaultTheme);
  } catch {
    html.setAttribute("data-bs-theme", defaultTheme);
  }
})();

// --- THEME CONFIG ---
const defaults = { theme: "light" };
let storedConfig = {};
try {
  storedConfig = JSON.parse(sessionStorage.getItem("__THEME_CONFIG__")) || {};
} catch {
  storedConfig = {};
}
const config = { ...defaults, ...storedConfig };
document.documentElement.setAttribute("data-bs-theme", config.theme);

// --- THEME CUSTOMIZER CLASS ---
class ThemeCustomizer {
  constructor() {
    this.html = document.documentElement;
    this.config = { ...config };
  }

  saveConfig() {
    sessionStorage.setItem("__THEME_CONFIG__", JSON.stringify(this.config));
    sessionStorage.setItem("__THEME_LABEL__", this.config.theme === "dark" ? "Dark" : "Light");
  }

  applyTheme(theme) {
    this.config.theme = theme;
    this.html.setAttribute("data-bs-theme", theme);
    this.updateUI();
    this.saveConfig();
  }

  resetTheme() {
    this.applyTheme(defaults.theme);
  }

  updateUI() {
    // Set radio inputs
    document.querySelectorAll("input[name=data-bs-theme]").forEach(radio => {
      radio.checked = radio.value === this.config.theme;
    });

    // Update dropdown label
    const dropdownToggle = document.querySelector(".theme-dropdown .dropdown-toggle");
    const savedLabel = sessionStorage.getItem("__THEME_LABEL__");
    if (dropdownToggle && savedLabel) dropdownToggle.textContent = savedLabel;
  }

  initListeners() {
    // Radio buttons
    document.querySelectorAll("input[name=data-bs-theme]").forEach(radio => {
      radio.addEventListener("change", () => this.applyTheme(radio.value));
    });

    // Toggle buttons
    document.querySelectorAll(".light-dark-mode").forEach(btn => {
      btn.addEventListener("click", () => {
        this.applyTheme(this.config.theme === "light" ? "dark" : "light");
      });
    });

    // Reset button
    const resetBtn = document.querySelector("#reset-layout");
    if (resetBtn) resetBtn.addEventListener("click", () => this.resetTheme());
  }

  init() {
    this.updateUI();
    this.initListeners();
  }
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  new ThemeCustomizer().init();
});
