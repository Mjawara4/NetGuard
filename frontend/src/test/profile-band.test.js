import { describe, it, expect } from 'vitest';
import { bandFor } from '../pages/Hotspot/profileBand.js';

describe('profile colour band', () => {
  it('gives the known profiles stable, distinct colours', () => {
    const a = bandFor('default');
    const b = bandFor('day-pass');
    const c = bandFor('week');
    expect(new Set([a, b, c]).size).toBe(3);
    expect(bandFor('default')).toBe(a); // stable across calls
  });

  // Review Focus #4: a fourth profile, or a renamed one, must not vanish.
  it('gives an unknown profile a visible neutral band', () => {
    const band = bandFor('some-new-profile');
    expect(band).toBeTruthy();
    expect(band).toMatch(/ink-/);
  });

  it('survives a missing or empty profile name', () => {
    expect(bandFor(undefined)).toBeTruthy();
    expect(bandFor('')).toBeTruthy();
    expect(bandFor(null)).toBeTruthy();
  });
});
