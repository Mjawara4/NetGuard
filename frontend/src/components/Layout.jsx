import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Server, Map, FileText, Wifi, LogOut, Globe, Menu, X, Settings, ShieldCheck } from 'lucide-react';

const SidebarItem = ({ to, icon: Icon, label, onClick }) => {
    const location = useLocation();
    const isActive = location.pathname === to;

    return (
        <Link
            to={to}
            onClick={onClick}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${isActive
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 translate-x-1'
                : 'text-gray-500 hover:bg-gray-100 hover:text-blue-600'
                }`}
        >
            <Icon size={20} className={isActive ? 'text-white' : 'text-gray-400'} />
            <span className={`font-semibold tracking-tight ${isActive ? 'text-white' : ''}`}>{label}</span>
        </Link>
    );
};

export default function Layout({ children }) {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const navigate = useNavigate();

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/login');
    };

    const toggleMobileMenu = () => setIsMobileMenuOpen(!isMobileMenuOpen);
    const closeMobileMenu = () => setIsMobileMenuOpen(false);

    return (
        <div className="flex h-screen bg-gray-50 overflow-hidden">
            {/* Mobile Header */}
            <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-white border-b shadow-sm z-40 flex items-center justify-between px-6">
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                    NetGuard AI
                </h1>
                <button
                    onClick={toggleMobileMenu}
                    className="p-2 text-gray-500 hover:text-blue-600 transition-colors"
                >
                    {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
                </button>
            </div>

            {/* Mobile Sidebar Overlay */}
            {isMobileMenuOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity"
                    onClick={closeMobileMenu}
                />
            )}

            {/* Sidebar */}
            <div className={`
                fixed inset-y-0 left-0 w-64 bg-white border-r shadow-sm flex flex-col z-50 transition-transform duration-300 transform
                lg:translate-x-0 lg:static lg:inset-0
                ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <div className="p-6 border-b hidden lg:block">
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                        NetGuard AI
                    </h1>
                    <p className="text-xs text-gray-400 mt-1">Advanced Network OS</p>
                </div>

                {/* Mobile Title (visible in sidebar when open) */}
                <div className="p-6 border-b lg:hidden">
                    <h1 className="text-xl font-bold text-blue-600">Navigation</h1>
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    <SidebarItem to="/" icon={LayoutDashboard} label="Dashboard" onClick={closeMobileMenu} />
                    <SidebarItem to="/sites" icon={Globe} label="Sites" onClick={closeMobileMenu} />
                    <SidebarItem to="/devices" icon={Server} label="Devices" onClick={closeMobileMenu} />
                    <SidebarItem to="/network-map" icon={Map} label="Network Map" onClick={closeMobileMenu} />
                    <SidebarItem to="/reports" icon={FileText} label="Reports" onClick={closeMobileMenu} />
                    <SidebarItem to="/hotspot" icon={Wifi} label="Hotspot Manager" onClick={closeMobileMenu} />
                    <SidebarItem to="/settings" icon={Settings} label="Settings" onClick={closeMobileMenu} />

                    {/* Admin Link */}
                    {JSON.parse(localStorage.getItem('user') || '{}').role === 'super_admin' && (
                        <SidebarItem to="/admin" icon={ShieldCheck} label="Admin" onClick={closeMobileMenu} />
                    )}
                </nav>

                <div className="p-4 border-t">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-3 w-full text-left text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    >
                        <LogOut size={20} />
                        <span className="font-medium">Logout</span>
                    </button>
                    <div className="mt-4 text-xs text-center text-gray-400">
                        v1.0.0
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto pt-16 lg:pt-0">
                {children}
            </div>
        </div>
    );
}
