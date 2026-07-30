/**
 * Mirrors the pre-paint script in lists.templatetags.frontend_tags
 * (theme_resolution_script). That copy has to stay a blocking, inline,
 * non-module <script> to run before first paint -- this one is what lets
 * the dev/ui gallery's toggle change the *same* state interactively.
 */
export type ThemeChoice = "system" | "light" | "dark";

const STORAGE_KEY = "clarice-theme";
const COOKIE_NAME = "clarice_theme";

export function resolveTheme(choice: ThemeChoice): "light" | "dark" {
  if (choice === "light" || choice === "dark") return choice;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(choice: ThemeChoice) {
  const resolved = resolveTheme(choice);
  document.documentElement.setAttribute("data-theme", resolved);
  document.cookie = `${COOKIE_NAME}=${resolved}; path=/; max-age=31536000; samesite=lax`;
  if (choice === "system") {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, choice);
  }
}

export function currentThemeChoice(): ThemeChoice {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === "light" || saved === "dark" ? saved : "system";
}
