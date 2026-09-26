import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React, { Suspense, lazy } from 'react';

import ChunkErrorBoundary, { RELOAD_FLAG } from '../components/ChunkErrorBoundary.jsx';

// Throws synchronously during render — stands in for a genuine, non-chunk
// render error (a bug in a component, not a missing network asset).
function Boom({ message }) {
    throw new Error(message);
}

describe('ChunkErrorBoundary', () => {
    let reloadSpy;

    beforeEach(() => {
        reloadSpy = vi.fn();
        // jsdom's window.location.reload is unimplemented and logs noise if
        // called directly; stub it so the boundary's calls are observable
        // without actually trying to reload the test environment.
        Object.defineProperty(window, 'location', {
            configurable: true,
            value: { ...window.location, reload: reloadSpy },
        });
        sessionStorage.clear();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('shows a visible, non-blank fallback panel for a chunk-load error when a reload was already attempted', async () => {
        // Seed the flag as if a previous mount (before this reload) already
        // tried the one-shot auto-reload. This is the path the real app
        // takes on a genuinely broken deploy, where reloading again would
        // just loop.
        sessionStorage.setItem(RELOAD_FLAG, '1');

        const LazyBoom = lazy(() =>
            Promise.reject(new Error('Failed to fetch dynamically imported module'))
        );

        const { container } = render(
            <ChunkErrorBoundary>
                <Suspense fallback={<div>loading…</div>}>
                    <LazyBoom />
                </Suspense>
            </ChunkErrorBoundary>
        );

        await waitFor(() => {
            expect(screen.getByText(/new version is available/i)).toBeInTheDocument();
        });

        // The core regression this guards against: the document must not
        // be left blank the way an uncaught chunk-load rejection would
        // leave it (root innerHTML length 0).
        expect(container.innerHTML.length).toBeGreaterThan(0);
        expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument();
        // Already attempted once — must not reload again.
        expect(reloadSpy).not.toHaveBeenCalled();
    });

    it('performs a one-shot reload the first time a chunk-load error is caught in a session', async () => {
        const LazyBoom = lazy(() =>
            Promise.reject(new Error('error loading dynamically imported module'))
        );

        render(
            <ChunkErrorBoundary>
                <Suspense fallback={<div>loading…</div>}>
                    <LazyBoom />
                </Suspense>
            </ChunkErrorBoundary>
        );

        await waitFor(() => {
            expect(reloadSpy).toHaveBeenCalledTimes(1);
        });
        expect(sessionStorage.getItem(RELOAD_FLAG)).toBe('1');
    });

    it('catches a non-chunk render error and shows the fallback instead of blanking the app', () => {
        const { container } = render(
            <ChunkErrorBoundary>
                <Boom message="Cannot read properties of undefined (reading 'foo')" />
            </ChunkErrorBoundary>
        );

        expect(screen.getByText(/new version is available/i)).toBeInTheDocument();
        expect(container.innerHTML.length).toBeGreaterThan(0);
        // Never auto-reload for a non-chunk error — only the fallback panel.
        expect(reloadSpy).not.toHaveBeenCalled();
    });

    it('renders children normally, and clears any stale reload flag, when there is no error', () => {
        sessionStorage.setItem(RELOAD_FLAG, '1');

        render(
            <ChunkErrorBoundary>
                <div data-testid="fine">all good</div>
            </ChunkErrorBoundary>
        );

        expect(screen.getByTestId('fine')).toBeInTheDocument();
        expect(sessionStorage.getItem(RELOAD_FLAG)).toBeNull();
    });
});
