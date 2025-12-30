import React from 'react';
import { Navigate } from 'react-router-dom';
import Layout from './Layout';

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

export default ProtectedRoute;
