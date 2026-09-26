import React from 'react';

// sessionStorage key used to make the auto-reload below one-shot per tab.
// Exported so tests can seed/inspect it without guessing the literal string.
export const RELOAD_FLAG = 'ng-chunk-reload-attempted';

// Chunk-load failures surface as a rejected dynamic import() with one of two
// browser-specific phrasings — there is no shared error "code" to check.
// Matched case-insensitively since capitalization has drifted across
// browser versions.
export function isChunkLoadError(error) {
    const message = String((error && error.message) || '');
    return (
        /failed to fetch dynamically imported module/i.test(message) ||
        /error loading dynamically imported module/i.test(message)
    );
}

function readReloadFlag() {
    try {
        return sessionStorage.getItem(RELOAD_FLAG) === '1';
    } catch {
        // sessionStorage can throw in some locked-down/private contexts.
        // Treat as "no reload attempted yet" — worst case we reload once
        // more than strictly necessary, never in a loop, since the flag
        // write below is wrapped the same way.
        return false;
    }
}

function writeReloadFlag() {
    try {
        sessionStorage.setItem(RELOAD_FLAG, '1');
    } catch {
        // Nothing to persist; the reload still happens below.
    }
}

function clearReloadFlag() {
    try {
        sessionStorage.removeItem(RELOAD_FLAG);
    } catch {
        // ignore
    }
}

// Catches render-phase errors — including a rejected React.lazy() import,
// which React re-throws into the nearest boundary once the promise settles.
// Must be a class component: getDerivedStateFromError/componentDidCatch have
// no function-component equivalent.
//
// This ships in the entry chunk (it wraps the top-level Suspense in
// App.jsx), so it is intentionally dependency-free and small.
class ChunkErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, isChunkError: false };
        // Read once at construction: reflects whatever a *previous* mount of
        // this boundary (i.e. before this page load) left behind.
        this.alreadyAttemptedReload = readReloadFlag();
        this.handleManualReload = this.handleManualReload.bind(this);
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, isChunkError: isChunkLoadError(error) };
    }

    componentDidCatch(error) {
        // Side effects belong here, not in render() (which React may call
        // more than once for the same commit).
        if (this.state.isChunkError && !this.alreadyAttemptedReload) {
            writeReloadFlag();
            window.location.reload();
        }
    }

    componentDidMount() {
        // this.state.hasError is only true here if an error was caught
        // before this, the boundary's first-ever commit (see
        // getDerivedStateFromError, which runs before render). So this only
        // clears the flag after a genuinely clean mount, letting a later,
        // unrelated chunk failure self-heal with its own one-shot reload.
        if (!this.state.hasError) {
            clearReloadFlag();
        }
    }

    handleManualReload() {
        window.location.reload();
    }

    render() {
        if (this.state.hasError) {
            if (this.state.isChunkError && !this.alreadyAttemptedReload) {
                // A reload is already in flight (triggered from
                // componentDidCatch). Show a neutral placeholder rather than
                // nothing while navigation completes.
                return (
                    <div className="flex items-center justify-center min-h-screen bg-white text-gray-600">
                        <p>Loading the latest version…</p>
                    </div>
                );
            }
            return (
                <div className="flex flex-col items-center justify-center gap-4 min-h-screen bg-white px-6 text-center text-gray-900">
                    <h1 className="text-xl font-semibold">A new version is available</h1>
                    <p className="max-w-sm text-gray-600">
                        This app was updated since you opened it. Please reload
                        the page to continue.
                    </p>
                    <button
                        type="button"
                        onClick={this.handleManualReload}
                        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
                    >
                        Reload
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

export default ChunkErrorBoundary;
