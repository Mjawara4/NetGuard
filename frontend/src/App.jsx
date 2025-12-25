import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Devices from './pages/Devices';
import Sites from './pages/Sites';
import NetworkMap from './pages/NetworkMap';
import Reports from './pages/Reports';
import Layout from './components/Layout';
import Hotspot from './pages/Hotspot';
import Signup from './pages/Signup';
import SettingsPage from './pages/Settings';
import AdminDashboard from './pages/AdminDashboard';

const ProtectedRoute = ({ children }) => {
    const token = localStorage.getItem('token');
    if (!token) {
        return <Navigate to="/login" replace />;
    }
    return (
        <Layout>
            {children}
        </Layout>
    );
};

function App() {
    return (
        <Router>
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
        </Router>
    );
}

export default App;
