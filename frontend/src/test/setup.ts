import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement matchMedia -- needed by the theme-resolution
// logic (frontend/src/app/theme.ts) that several tests exercise.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }) as unknown as MediaQueryList;
}
