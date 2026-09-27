import { describe, it, expect } from 'vitest';
import config from '../../tailwind.config.js';

const colors = config.theme.extend.colors;

// WCAG relative luminance, then contrast ratio. Written out rather than
// pulled from a dependency so the gate has no install cost.
function luminance(hex) {
    const c = hex.replace('#', '');
    const channels = [0, 2, 4].map((i) => {
        const v = parseInt(c.slice(i, i + 2), 16) / 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(a, b) {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
}

describe('colour tokens', () => {
    it('defines the full ink scale', () => {
        for (const step of [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]) {
            expect(colors.ink[step]).toMatch(/^#[0-9A-Fa-f]{6}$/);
        }
    });

    it('defines the signal accent and the three semantics', () => {
        expect(colors.signal[600]).toBe('#7C3E9C');
        expect(colors.up).toBe('#2F7D62');
        expect(colors.down).toBe('#9A3A22');
        expect(colors.warn).toBe('#8A6114');
    });

    it('has no leftover default gray or blue aliases', () => {
        expect(colors.gray).toBeUndefined();
        expect(colors.blue).toBeUndefined();
    });
});

describe('contrast', () => {
    // Review Focus #2: caption grey on the page ground is the pair that
    // fails most often, so it is pinned here rather than caught in review.
    it('caption text on the light ground meets 4.5:1', () => {
        expect(contrast(colors.ink[500], colors.ink[50])).toBeGreaterThanOrEqual(4.5);
    });

    it('body text on the light ground meets 4.5:1', () => {
        expect(contrast(colors.ink[900], colors.ink[50])).toBeGreaterThanOrEqual(4.5);
    });

    it('body text on the dark ground meets 4.5:1', () => {
        expect(contrast(colors.ink[100], colors.ink[950])).toBeGreaterThanOrEqual(4.5);
    });

    it('white on the accent meets 4.5:1, so primary buttons are readable', () => {
        expect(contrast('#FFFFFF', colors.signal[600])).toBeGreaterThanOrEqual(4.5);
    });

    it('each status colour is distinguishable from the ground', () => {
        for (const status of [colors.up, colors.down, colors.warn]) {
            expect(contrast(status, colors.ink[50])).toBeGreaterThanOrEqual(4.5);
        }
    });

    // Task 3 amendment. signal-400 has no dark-mode text use: it clears
    // 4.5:1 on the page ground (ink-900) but not on a card's ground
    // (ink-800), so a link inside a card would pass or fail depending on
    // which surface it happened to sit on. signal-300 is the dark-mode
    // accent-text token instead, chosen as the least-light shade that
    // clears both dark grounds, so there is one rule for dark-mode accent
    // text rather than a "which background am I on" judgment call.
    it('signal-300 is the dark-mode accent-text token: it clears 4.5:1 on both dark grounds', () => {
        expect(contrast(colors.signal[300], colors.ink[800])).toBeGreaterThanOrEqual(4.5);
        expect(contrast(colors.signal[300], colors.ink[900])).toBeGreaterThanOrEqual(4.5);
    });

    it('signal-300 does not meet 4.5:1 on a light ground, so it must stay a dark-mode-only token', () => {
        expect(contrast(colors.signal[300], colors.ink[50])).toBeLessThan(4.5);
    });

    it('up and down differ in lightness, not hue alone', () => {
        // Colour-blind safety: the spec requires a lightness difference.
        const delta = Math.abs(luminance(colors.up) - luminance(colors.down));
        expect(delta).toBeGreaterThan(0.04);
    });
});

describe('display font', () => {
    // Review Focus #3: a blocked or slow webfont must degrade, not break.
    it('falls back to a system face', () => {
        expect(config.theme.extend.fontFamily.display).toContain('system-ui');
    });
});

describe('semantic tint compositing', () => {
    // Task 2 amendment. The kit renders semantic "wash" chips as a flat
    // token composited over the page ground at low alpha — e.g. Badge.jsx's
    // `bg-down/10 ... dark:bg-down/20` — not a literal Tailwind shade. A
    // contrast check on the raw token alone (as above) says nothing about
    // what actually paints once that alpha is applied, so it is computed
    // here instead of eyeballed.
    //
    // Alphas are read from where the kit actually uses them, not assumed:
    // grepping 'up/', 'down/', 'warn/' across Badge.jsx and StatCard.jsx
    // shows every semantic wash uses the same pair, no exceptions —
    // 10% in light mode, 20% in dark mode.
    const LIGHT_ALPHA = 0.10;
    const DARK_ALPHA = 0.20;

    // Straight per-channel linear interpolation on the 8-bit sRGB values.
    // This is what `background-color` with alpha actually composites to in
    // a browser over an opaque parent — do not lift this into linear-light
    // space, that would answer a different question than the one on screen.
    function composite(fgHex, bgHex, alpha) {
        const f = fgHex.replace('#', '');
        const b = bgHex.replace('#', '');
        const channels = [0, 2, 4].map((i) => {
            const fv = parseInt(f.slice(i, i + 2), 16);
            const bv = parseInt(b.slice(i, i + 2), 16);
            return Math.round(fv * alpha + bv * (1 - alpha));
        });
        return '#' + channels.map((v) => v.toString(16).padStart(2, '0')).join('');
    }

    const semantics = { up: colors.up, down: colors.down, warn: colors.warn };

    for (const [name, hex] of Object.entries(semantics)) {
        it(`${name}'s light-mode wash is distinguishable from the page ground`, () => {
            const tint = composite(hex, colors.ink[50], LIGHT_ALPHA);
            expect(contrast(tint, colors.ink[50])).toBeGreaterThan(1.1);
        });

        it(`${name}'s dark-mode wash is distinguishable from the page ground`, () => {
            const tint = composite(hex, colors.ink[900], DARK_ALPHA);
            expect(contrast(tint, colors.ink[900])).toBeGreaterThan(1.1);
        });

        // The kit's original design used the semantic itself as the wash's
        // text/icon colour (`text-down dark:text-down`, etc). Computed, that
        // pattern's contrast falls monotonically as alpha rises — the
        // composite converges toward the text colour itself as alpha
        // approaches 1, so alpha=0 (no wash at all) is the *best* case, not
        // the worst. Even at alpha=0, a semantic's direct contrast against
        // ink-900 tops out at 3.36 (up), 3.02 (warn), 2.39 (down) — all
        // below 4.5, at any alpha, in dark mode. No alpha change and no
        // amount of darkening the token fixes this: darkening only helps
        // the light-ground comparison and makes the dark-ground one worse.
        // Badge.jsx and StatCard.jsx were changed to use neutral ink as the
        // wash's text/icon colour instead (ink-900 on the light wash,
        // ink-50 on the dark wash) — the semantic hue now lives only in the
        // background. This asserts that shipped pairing actually clears
        // 4.5:1, in both modes, for all three semantics.
        it(`${name}'s wash is readable with neutral ink text in light mode`, () => {
            const tint = composite(hex, colors.ink[50], LIGHT_ALPHA);
            expect(contrast(colors.ink[900], tint)).toBeGreaterThanOrEqual(4.5);
        });

        it(`${name}'s wash is readable with neutral ink text in dark mode`, () => {
            const tint = composite(hex, colors.ink[900], DARK_ALPHA);
            expect(contrast(colors.ink[50], tint)).toBeGreaterThanOrEqual(4.5);
        });
    }
});
