import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

vi.mock('../api', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn(() => Promise.resolve({ data: {} })) },
}));

import Login from '../pages/Login.jsx';

describe('Login', () => {
  // The labels currently have no htmlFor and the inputs no id, so a screen
  // reader announces nothing. This is the fix.
  it('associates every label with its control', () => {
    render(<MemoryRouter><Login /></MemoryRouter>);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('uses no default-palette or shouting classes', () => {
    const { container } = render(<MemoryRouter><Login /></MemoryRouter>);
    const html = container.innerHTML;
    expect(html).not.toMatch(/(bg|text|border|from|to|ring|divide)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/);
    expect(html).not.toMatch(/font-black|uppercase|tracking-widest|text-\[10px\]/);
  });

  it('has no gradient wordmark', () => {
    const { container } = render(<MemoryRouter><Login /></MemoryRouter>);
    expect(container.innerHTML).not.toMatch(/bg-gradient-to|bg-clip-text/);
  });
});
