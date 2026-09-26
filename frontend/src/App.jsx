import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

import ProtectedRoute from './components/ProtectedRoute';
import ChunkErrorBoundary from './components/ChunkErrorBoundary';

const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const SettingsPage = lazy(() => import('./pages/Settings'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Sites = lazy(() => import('./pages/Sites'));
const Devices = lazy(() => import('./pages/Devices'));
const NetworkMap = lazy(() => import('./pages/NetworkMap'));
const Reports = lazy(() => import('./pages/Reports'));
const Hotspot = lazy(() => import('./pages/Hotspot'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));

// Shown only while a route chunk is in flight. Deliberately minimal: a heavy
// skeleton here would itself have to ship in the entry chunk.
const RouteFallback = () => (
    <div className="flex items-center justify-center min-h-screen">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
    </div>
);

function App() {
    return (
        <Router>
            <ChunkErrorBoundary>
                <Suspense fallback={<RouteFallback />}>
                    <Routes>
                        <Route path="/login" element={<Login />} />
                        <Route path="/signup" element={<Signup />} />
                        <Route
                            path="/settings"
                            element={
                                <ProtectedRoute>
                                    <SettingsPage />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/"
                            element={
                                <ProtectedRoute>
                                    <Dashboard />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/sites"
                            element={
                                <ProtectedRoute>
                                    <Sites />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/devices"
                            element={
                                <ProtectedRoute>
                                    <Devices />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/network-map"
                            element={
                                <ProtectedRoute>
                                    <NetworkMap />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/reports"
                            element={
                                <ProtectedRoute>
                                    <Reports />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/hotspot"
                            element={
                                <ProtectedRoute>
                                    <Hotspot />
                                </ProtectedRoute>
                            }
                        />
                        <Route
                            path="/admin"
                            element={
                                <ProtectedRoute>
                                    <AdminDashboard />
                                </ProtectedRoute>
                            }
                        />
                    </Routes>
                </Suspense>
            </ChunkErrorBoundary>
        </Router>
    );
}

export default App;
