import '@testing-library/jest-dom/vitest';

// jsdom does not implement matchMedia. ThemeContext itself never calls it
// (it only reads localStorage on mount) — this shim is a defensive guard
// for any code that does, so jsdom doesn't throw on access.
if (!window.matchMedia) {
    window.matchMedia = (query) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
    });
}
