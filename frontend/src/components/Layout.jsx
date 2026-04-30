import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard, Server, Map, FileText, Wifi, LogOut, Globe, Menu, X, Settings, ShieldCheck,
    Sun, Moon, ChevronLeft, ChevronRight, Bell
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import api from '../api';
import AIChatParams from './AIChatParams';

const SidebarItem = ({ to, icon: Icon, label, onClick, collapsed, badge }) => {
    const location = useLocation();
    const isActive = location.pathname === to;

    return (
        <Link
            to={to}
            onClick={onClick}
            aria-current={isActive ? 'page' : undefined}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${isActive
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 dark:shadow-blue-900/30 translate-x-1'
                : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-blue-600 dark:hover:text-blue-400'
                }`}
            title={collapsed ? label : undefined}
        >
            <div className="relative">
                <Icon size={20} className={isActive ? 'text-white' : 'text-gray-400 dark:text-gray-500'} />
                {badge > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white text-[9px] font-black rounded-full flex items-center justify-center">
                        {badge > 9 ? '9+' : badge}
                    </span>
                )}
            </div>
            {!collapsed && (
                <span className={`font-semibold tracking-tight ${isActive ? 'text-white' : ''}`}>{label}</span>
            )}
        </Link>
    );
};

export default function Layout({ children }) {
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem('sidebarCollapsed') === 'true';
        }
        return false;
    });
    const [alertCounts, setAlertCounts] = useState({ devices: 0, alerts: 0 });
    const navigate = useNavigate();
    const { theme, toggleTheme } = useTheme();

    useEffect(() => {
        fetchAlertCounts();
        const interval = setInterval(fetchAlertCounts, 30000);
        return () => clearInterval(interval);
    }, []);

    const fetchAlertCounts = async () => {
        try {
            const [devicesRes, alertsRes] = await Promise.all([
                api.get('/inventory/devices').catch(() => ({ data: [] })),
                api.get('/monitoring/alerts').catch(() => ({ data: [] }))
            ]);
            const offlineDevices = devicesRes.data.filter(d => !d.is_active).length;
            const openAlerts = alertsRes.data.filter(a => a.status === 'open').length;
            setAlertCounts({ devices: offlineDevices, alerts: openAlerts });
        } catch (e) {
            // Silently fail
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/login');
    };

    const toggleMobileMenu = () => setIsMobileMenuOpen(!isMobileMenuOpen);
    const closeMobileMenu = () => setIsMobileMenuOpen(false);

    const toggleCollapse = () => {
        const next = !isCollapsed;
        setIsCollapsed(next);
        localStorage.setItem('sidebarCollapsed', String(next));
    };

    const sidebarWidth = isCollapsed ? 'w-20' : 'w-64';
    const user = JSON.parse(localStorage.getItem('user') || '{}');

    return (
        <div className="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
            {/* Mobile Header */}
            <div className="lg:hidden fixed top-0 left-0 right-0 min-h-16 bg-white dark:bg-gray-800 border-b dark:border-gray-700 shadow-sm z-40 flex items-center justify-between px-6 pt-safe-top">
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent my-4">
                    NetGuard AI
                </h1>
                <button
                    onClick={toggleMobileMenu}
                    className="p-2 text-gray-500 dark:text-gray-400 hover:text-blue-600 transition-colors"
                    aria-label="Toggle navigation menu"
                    aria-expanded={isMobileMenuOpen}
                >
                    {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
                </button>
            </div>

            {/* Mobile Sidebar Overlay */}
            {isMobileMenuOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity"
                    onClick={closeMobileMenu}
                    aria-hidden="true"
                />
            )}

            {/* Sidebar */}
            <div className={`
                fixed inset-y-0 left-0 ${sidebarWidth} bg-white dark:bg-gray-800 border-r dark:border-gray-700 shadow-sm flex flex-col z-50 transition-all duration-300 transform
                lg:translate-x-0 lg:static lg:inset-0
                ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <div className="p-6 border-b dark:border-gray-700 hidden lg:flex items-center justify-between">
                    {!isCollapsed && (
                        <div>
                            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                                NetGuard AI
                            </h1>
                            <p className="text-xs text-gray-400 mt-1">Advanced Network OS</p>
                        </div>
                    )}
                    <button
                        onClick={toggleCollapse}
                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                        title={isCollapsed ? 'Expand' : 'Collapse'}
                    >
                        {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                    </button>
                </div>

                {/* Mobile Title (visible in sidebar when open) */}
                <div className="p-6 border-b dark:border-gray-700 lg:hidden">
                    <h1 className="text-xl font-bold text-blue-600">Navigation</h1>
                </div>

                <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                    <SidebarItem to="/" icon={LayoutDashboard} label="Dashboard" onClick={closeMobileMenu} collapsed={isCollapsed} />
                    <SidebarItem to="/sites" icon={Globe} label="Sites" onClick={closeMobileMenu} collapsed={isCollapsed} />
                    <SidebarItem to="/devices" icon={Server} label="Devices" onClick={closeMobileMenu} collapsed={isCollapsed} badge={alertCounts.devices} />
                    <SidebarItem to="/network-map" icon={Map} label="Network Map" onClick={closeMobileMenu} collapsed={isCollapsed} />
                    <SidebarItem to="/reports" icon={FileText} label="Reports" onClick={closeMobileMenu} collapsed={isCollapsed} />
                    <SidebarItem to="/hotspot" icon={Wifi} label="Hotspot Manager" onClick={closeMobileMenu} collapsed={isCollapsed} />
                    <SidebarItem to="/settings" icon={Settings} label="Settings" onClick={closeMobileMenu} collapsed={isCollapsed} />

                    {user.role === 'super_admin' && (
                        <SidebarItem to="/admin" icon={ShieldCheck} label="Admin" onClick={closeMobileMenu} collapsed={isCollapsed} />
                    )}
                </nav>

                <div className="p-4 border-t dark:border-gray-700 space-y-2">
                    <button
                        onClick={toggleTheme}
                        className="flex items-center gap-3 px-4 py-3 w-full text-left text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                    >
                        {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
                        {!isCollapsed && <span className="font-medium">{theme === 'light' ? 'Dark Mode' : 'Light Mode'}</span>}
                    </button>
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-4 py-3 w-full text-left text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    >
                        <LogOut size={20} />
                        {!isCollapsed && <span className="font-medium">Logout</span>}
                    </button>
                    {!isCollapsed && (
                        <div className="mt-4 text-xs text-center text-gray-400">
                            v1.0.0
                        </div>
                    )}
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto pt-[calc(4rem+env(safe-area-inset-top))] lg:pt-0">
                {children}
            </div>

            {/* AI Assistant Float */}
            <AIChatParams />
        </div>
    );
}
