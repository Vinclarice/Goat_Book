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

// jsdom doesn't implement ResizeObserver -- Radix's Switch (and other
// size-aware primitives) use it internally.
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
