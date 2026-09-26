import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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

// A controllable stand-in for the lazy-loaded Settings page. vi.mock is
// hoisted above imports, so the deferred promise it awaits must be created
// via vi.hoisted rather than a module-scope variable declared below it.
const { settingsGate } = vi.hoisted(() => {
    let release;
    const gate = new Promise((resolve) => {
        release = resolve;
    });
    return { settingsGate: { gate, release } };
});

vi.mock('../pages/Settings.jsx', async () => {
    // Blocks the dynamic import's promise from resolving until the test
    // calls settingsGate.release(), so we can observe the app mid-suspense.
    await settingsGate.gate;
    return {
        default: () => <div data-testid="settings-content">Settings Content</div>,
    };
});

import App from '../App.jsx';
import { ThemeProvider } from '../context/ThemeContext.jsx';

describe('ProtectedRoute shell', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('renders a protected route with the Layout shell present (settled state)', async () => {
        localStorage.setItem('token', 'test-token');
        window.history.pushState({}, '', '/devices');

        render(
            <ThemeProvider>
                <App />
            </ThemeProvider>
        );

        // The sidebar nav is Layout's landmark. If ProtectedRoute's
        // composition (Layout wrapping a Suspense wrapping children) were
        // broken, this would never appear.
        await waitFor(() => {
            expect(screen.getByRole('navigation')).toBeInTheDocument();
        });
    });

    it('keeps the Layout shell mounted while the route chunk is still loading', async () => {
        // This is the actual regression case from fix round 1: the shell
        // must not disappear behind the full-page fallback on first visit
        // to a route while its lazy chunk is in flight.
        localStorage.setItem('token', 'test-token');
        window.history.pushState({}, '', '/settings');

        render(
            <ThemeProvider>
                <App />
            </ThemeProvider>
        );

        // Settings' mocked import is still pending (settingsGate has not
        // been released yet), so the inner content-area Suspense fallback
        // should be showing right now — and, critically, the shell around
        // it should already be mounted, not replaced by it.
        expect(screen.getByRole('navigation')).toBeInTheDocument();
        expect(screen.getByRole('status', { name: /loading content/i })).toBeInTheDocument();
        expect(screen.queryByTestId('settings-content')).not.toBeInTheDocument();

        // Now let the chunk "finish loading".
        settingsGate.release();

        await waitFor(() => {
            expect(screen.getByTestId('settings-content')).toBeInTheDocument();
        });

        // The shell must still be there after the content resolves — it was
        // never unmounted in the process.
        expect(screen.getByRole('navigation')).toBeInTheDocument();
    });
});
