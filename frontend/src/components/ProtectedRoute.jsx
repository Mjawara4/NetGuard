import React, { Suspense } from 'react';
import { Navigate } from 'react-router-dom';
import Layout from './Layout';

// Content-area fallback for the boundary below. Sized for the pane inside
// Layout rather than the full viewport, so the shell (sidebar, header) stays
// mounted and only this pane shows a loading state while a route chunk
// loads. Kept deliberately simple: a heavier fallback here would itself have
// to ship in the entry chunk.
const ContentFallback = () => (
    <div className="flex items-center justify-center h-full min-h-[50vh]" role="status" aria-label="Loading content">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-ink-300 dark:border-ink-700 border-t-signal-600 dark:border-t-signal-300" />
    </div>
);

const ProtectedRoute = ({ children }) => {
    const token = localStorage.getItem('token');
    if (!token) {
        return <Navigate to="/login" replace />;
    }
    return (
        <Layout>
            <Suspense fallback={<ContentFallback />}>
                {children}
            </Suspense>
        </Layout>
    );
};

export default ProtectedRoute;
