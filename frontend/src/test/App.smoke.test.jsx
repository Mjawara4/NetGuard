import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import React from 'react';

// The api module creates an axios instance at import time and must never
// make real requests during tests.
vi.mock('../api', () => ({
    default: {
        get: vi.fn(() => Promise.resolve({ data: [] })),
        post: vi.fn(() => Promise.resolve({ data: {} })),
        put: vi.fn(() => Promise.resolve({ data: {} })),
        delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
}));

import App from '../App.jsx';
import { ThemeProvider } from '../context/ThemeContext.jsx';

describe('App', () => {
    beforeEach(() => {
        localStorage.clear();
        window.history.pushState({}, '', '/login');
    });

    it('renders the login route without crashing when unauthenticated', async () => {
        const { container } = render(
            <ThemeProvider>
                <App />
            </ThemeProvider>
        );
        // Login's <label> elements have no htmlFor and its inputs have no id or
        // aria-label (verified in src/pages/Login.jsx), so *ByLabelText cannot
        // resolve them. Query the password input by type instead, which is
        // independent of copy and of the missing label association.
        await waitFor(() => {
            expect(container.querySelector('input[type="password"]')).toBeInTheDocument();
        });
    });
});
