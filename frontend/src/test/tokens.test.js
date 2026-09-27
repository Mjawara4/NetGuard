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
