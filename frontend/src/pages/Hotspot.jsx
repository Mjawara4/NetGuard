import React, { useState, useEffect } from 'react';
import api from '../api';
import { LayoutDashboard, Users, CreditCard, Activity, RefreshCw, Plus, Trash, Printer, X, Scissors, Shield, Trash2, Wifi, Clock, ArrowDownCircle, ArrowUpCircle, Settings, Download, Search, FileText, Globe, AlertCircle } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend } from 'recharts';
import ResponsiveTable from '../components/ResponsiveTable';
import ResponsiveModal from '../components/ResponsiveModal';

export default function Hotspot() {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [devices, setDevices] = useState([]);
    const [selectedDevice, setSelectedDevice] = useState(null);
    const [users, setUsers] = useState([]);
    const [activeSessions, setActiveSessions] = useState([]);
    const [profiles, setProfiles] = useState([]);
    const [dashboardData, setDashboardData] = useState(null);
    const [healthStatus, setHealthStatus] = useState('unknown');
    const [loading, setLoading] = useState(false);
    const [showProfileModal, setShowProfileModal] = useState(false);
    const [profileForm, setProfileForm] = useState({ name: '', rateLimit: '1M/1M', sharedUsers: 1 });
    const [userSearch, setUserSearch] = useState('');

    // Generation State
    const [batchForm, setBatchForm] = useState({ qty: 10, prefix: 'user', profile: 'default', time_limit: '1h', data_limit: '', length: 4, random_mode: false, format: 'alphanumeric' });
    const [generatedBatch, setGeneratedBatch] = useState([]);
    const [showPrintView, setShowPrintView] = useState(false);

    // Template State
    const [template, setTemplate] = useState({
        header_text: "Wi-Fi Voucher",
        footer_text: "Thank you for visiting!",
        logo_url: "",
        color_primary: "#2563EB"
    });

    useEffect(() => {
        fetchDevices();
    }, []);

    useEffect(() => {
        if (selectedDevice) {
            fetchData();
        }
    }, [selectedDevice, activeTab]);

    const fetchDevices = async () => {
        try {
            const res = await api.get('/inventory/devices');
            console.log("Fetched devices:", res.data);
            const routers = res.data.filter(d => d.device_type?.toLowerCase() === 'router');
            setDevices(routers);
            if (routers.length > 0 && !selectedDevice) setSelectedDevice(routers[0].id);
        } catch (e) {
            console.error(e);
        }
    };

    const fetchProfiles = async (deviceId) => {
        setLoading(true);
        try {
            const res = await api.get(`/hotspot/${deviceId}/profiles`);
            setProfiles(res.data);
        } catch (e) {
            console.error("Failed to fetch profiles:", e);
        } finally {
            setLoading(false);
        }
    };

    const fetchTemplate = async (deviceId) => {
        try {
            const res = await api.get(`/hotspot/${deviceId}/voucher-template`);
            if (res.data) setTemplate(res.data);
        } catch (e) {
            console.error("Failed to fetch template:", e);
        }
    };

    const saveTemplate = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post(`/hotspot/${selectedDevice}/voucher-template`, template);
            if (res.data) alert('Template saved!');
        } catch (e) {
            alert("Failed to save template.");
        } finally {
            setLoading(false);
        }
    };

    const fetchData = async () => {
        if (!selectedDevice) return;
        setLoading(true);
        try {
            if (activeTab === 'dashboard') {
                const res = await api.get(`/hotspot/${selectedDevice}/summary`);
                setDashboardData(res.data);
                setHealthStatus('online');
            } else if (activeTab === 'users') {
                const res = await api.get(`/hotspot/${selectedDevice}/users`);
                setUsers(res.data);
                setHealthStatus('online');
            } else if (activeTab === 'active') {
                const res = await api.get(`/hotspot/${selectedDevice}/active`);
                setActiveSessions(res.data);
                setHealthStatus('online');
            } else if (activeTab === 'profiles') {
                await fetchProfiles(selectedDevice);
                setHealthStatus('online');
            } else if (activeTab === 'templates') {
                await fetchTemplate(selectedDevice);
            }
        } catch (e) {
            console.error(e);
            if (activeTab !== 'templates') setHealthStatus('offline');
        } finally {
            setLoading(false);
        }
    };

    const handleKick = async (id) => {
        if (!window.confirm("Disconnect this user?")) return;
        try {
            await api.delete(`/hotspot/${selectedDevice}/active/${id}`);
            fetchData();
        } catch (e) {
            alert("Failed to kick user.");
        }
    };

    const handleProfileAdd = async (e) => {
        e.preventDefault();
        if (!selectedDevice) return;
        try {
            await api.post(`/hotspot/${selectedDevice}/profiles`, {
                name: profileForm.name,
                'rate-limit': profileForm.rateLimit,
                'shared-users': profileForm.sharedUsers
            });
            setShowProfileModal(false);
            setProfileForm({ name: '', rateLimit: '1M/1M', sharedUsers: 1 }); // Reset form
            fetchProfiles(selectedDevice);
        } catch (err) {
            alert("Failed to add profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleProfileDelete = async (name) => {
        if (!selectedDevice) return;
        if (!confirm(`Are you sure you want to delete profile "${name}"?`)) return;
        try {
            await api.delete(`/hotspot/${selectedDevice}/profiles/${name}`);
            fetchProfiles(selectedDevice);
        } catch (err) {
            alert("Failed to delete profile: " + (err.response?.data?.detail || err.message));
        }
    };

    const handleGenerate = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post(`/hotspot/${selectedDevice}/users/batch`, batchForm);
            setGeneratedBatch(res.data);
            setShowPrintView(true);
        } catch (e) {
            alert('Generation failed: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleCleanupExpired = async () => {
        if (!window.confirm("Delete all users who have reached their time or data limits?")) return;
        setLoading(true);
        try {
            const res = await api.delete(`/hotspot/${selectedDevice}/users/bulk?expired=true`);
            alert(`Cleaned up ${res.data.count} expired users.`);
            fetchData();
        } catch (e) {
            alert("Cleanup failed.");
        } finally {
            setLoading(false);
        }
    };

    const handleBulkDeleteByComment = async (comment) => {
        if (!window.confirm(`Delete all users in batch "${comment}"?`)) return;
        setLoading(true);
        try {
            const res = await api.delete(`/hotspot/${selectedDevice}/users/bulk?comment=${comment}`);
            alert(`Deleted ${res.data.count} users.`);
            fetchData();
        } catch (e) {
            alert("Bulk delete failed.");
        } finally {
            setLoading(false);
        }
    };

    const handleExportCSV = async () => {
        try {
            const res = await api.get(`/hotspot/${selectedDevice}/users/export`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `hotspot_users_${selectedDevice}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (e) {
            alert("Export failed.");
        }
    };

    const handleDelete = async (name) => {
        if (!window.confirm(`Are you sure you want to delete user "${name}"?`)) return;
        setLoading(true);
        try {
            await api.delete(`/hotspot/${selectedDevice}/users/${name}`);
            fetchData();
        } catch (e) {
            alert("Delete failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 pt-4 sm:pt-8 px-4 sm:px-6 lg:px-10 pb-12">
            <style>{`
                @media print {
                    @page { margin: 5mm; size: auto; }
                    body * { visibility: hidden; }
                    #printable-area, #printable-area * { visibility: visible; }
                    #printable-area { 
                        position: absolute; 
                        left: 0; 
                        top: 0; 
                        width: 100%; 
                        display: block !important;
                    }
                    .no-print { display: none !important; }
                    
                    /* Grid simulation using inline-block for better print support */
                    .voucher-card { 
                        display: inline-block !important;
                        width: 19% !important; /* Slightly wider */
                        margin: 0.5% !important; /* Tighter margins */
                        vertical-align: top;
                        
                        page-break-inside: avoid !important; 
                        break-inside: avoid !important;
                        page-break-after: auto;
                        
                        border: 1px dashed #ccc; 
                        box-sizing: border-box;
                    }
                    
                    /* Dynamic Print Styles */
                    .print-header { color: ${template.color_primary} !important; }
                    .print-border { border-color: ${template.color_primary} !important; }
                    .print-bg { background-color: ${template.color_primary}10 !important; } /* 10% opacity */
                }
            `}</style>

            <div className="max-w-7xl mx-auto">
                {/* Page Header */}
                <div className="mb-8 sm:mb-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6 no-print">
                    <div>
                        <h1 className="text-3xl sm:text-4xl font-black text-gray-900 tracking-tight leading-none">
                            Hotspot <span className="text-blue-600">Controller</span>
                        </h1>
                        <p className="text-gray-500 mt-2 font-medium text-sm sm:text-base">Enterprise voucher management and hotspot profile orchestration.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex flex-col items-end gap-1 px-3">
                            <div className="flex items-center gap-1.5">
                                <div className={`w-2 h-2 rounded-full ${healthStatus === 'online' ? 'bg-emerald-500 animate-pulse' : healthStatus === 'offline' ? 'bg-red-500' : 'bg-gray-300'}`}></div>
                                <span className={`text-[10px] font-black uppercase tracking-widest ${healthStatus === 'online' ? 'text-emerald-600' : healthStatus === 'offline' ? 'text-red-600' : 'text-gray-400'}`}>
                                    {healthStatus === 'online' ? 'Sync Active' : healthStatus === 'offline' ? 'Sync Failed' : 'Checking...'}
                                </span>
                            </div>
                        </div>
                        <select
                            className="bg-white border border-gray-100 rounded-2xl px-4 sm:px-5 py-3 shadow-sm focus:ring-2 focus:ring-blue-500 outline-none transition-all font-bold text-gray-700 flex-1 lg:min-w-[240px] text-sm sm:text-base"
                            value={selectedDevice || ''}
                            onChange={e => setSelectedDevice(e.target.value)}
                        >
                            <option value="" disabled>Select Core Router</option>
                            {devices.map(d => <option key={d.id} value={d.id}>{d.name} ({d.ip_address})</option>)}
                        </select>
                        <button
                            onClick={fetchData}
                            className="bg-white p-3 border border-gray-100 rounded-2xl shadow-sm hover:bg-gray-50 text-gray-600 transition-all active:scale-95 flex-shrink-0"
                            title="Refresh Data"
                        >
                            <RefreshCw size={22} className={loading ? 'animate-spin text-blue-600' : ''} />
                        </button>
                    </div>
                </div>

                {/* Navigation Bar */}
                <div className="mb-8 sm:mb-10 no-print">
                    <div className="flex bg-white p-1.5 rounded-3xl shadow-sm border border-gray-100 gap-1.5 overflow-x-auto no-scrollbar scroll-smooth">
                        <TabButton id="dashboard" label="Dashboard" icon={LayoutDashboard} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="active" label="Active" icon={Activity} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="users" label="Users" icon={Users} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="profiles" label="Profiles" icon={Shield} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="generate" label="Generator" icon={Printer} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="templates" label="Templates" icon={Settings} activeTab={activeTab} setActiveTab={setActiveTab} />
                    </div>
                </div>

                <div className="space-y-8">
                    {/* Dashboard Tab */}
                    {activeTab === 'dashboard' && !showPrintView && dashboardData && (
                        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            {/* Dashboard Headline Stats */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                <MetricCard title="Active Sessions" value={dashboardData.active_count} icon={Users} color="blue" />
                                <MetricCard title="Total Vouchers" value={dashboardData.total_vouchers} icon={CreditCard} color="indigo" />
                                <MetricCard title="Data (Current Sessions)" value={`${dashboardData.total_data_mb}MB`} icon={Activity} color="emerald" />
                                <MetricCard title="System Health" value={healthStatus === 'online' ? 'Healthy' : 'Sync Error'} icon={Shield} color={healthStatus === 'online' ? 'emerald' : 'red'} />
                            </div>

                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                                {/* Profile Distribution Chart */}
                                <div className="bg-white p-6 sm:p-8 rounded-[32px] shadow-sm border border-gray-100">
                                    <h3 className="text-lg font-black text-gray-900 mb-6 uppercase tracking-tight flex items-center gap-2">
                                        <Activity size={20} className="text-blue-500" />
                                        Voucher Distribution
                                    </h3>
                                    <div className="h-[300px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={dashboardData.profile_distribution}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={60}
                                                    outerRadius={100}
                                                    paddingAngle={5}
                                                    dataKey="value"
                                                >
                                                    {dashboardData.profile_distribution.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444'][index % 5]} />
                                                    ))}
                                                </Pie>
                                                <RechartsTooltip />
                                                <Legend />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>

                                {/* Quick Actions / Status */}
                                <div className="bg-white p-6 sm:p-8 rounded-[32px] shadow-sm border border-gray-100 flex flex-col justify-between">
                                    <div>
                                        <h3 className="text-lg font-black text-gray-900 mb-4 uppercase tracking-tight">Sync Status</h3>
                                        <div className="space-y-4">
                                            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-2 rounded-lg ${healthStatus === 'online' ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'}`}>
                                                        <Globe size={18} />
                                                    </div>
                                                    <span className="text-sm font-bold text-gray-700">Router Integration</span>
                                                </div>
                                                <span className={`text-xs font-black uppercase ${healthStatus === 'online' ? 'text-emerald-600' : 'text-red-600'}`}>{healthStatus}</span>
                                            </div>
                                            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-2xl">
                                                <div className="flex items-center gap-3">
                                                    <div className="p-2 rounded-lg bg-blue-100 text-blue-600">
                                                        <Activity size={18} />
                                                    </div>
                                                    <span className="text-sm font-bold text-gray-700">API Latency</span>
                                                </div>
                                                <span className="text-xs font-black uppercase text-blue-600">Optimal</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="mt-6 flex gap-3">
                                        <button onClick={() => setActiveTab('generate')} className="flex-1 bg-blue-600 text-white py-3 rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-lg shadow-blue-100">Quick Generate</button>
                                        <button onClick={() => setActiveTab('active')} className="flex-1 bg-white border border-gray-100 text-gray-600 py-3 rounded-2xl font-black text-[10px] uppercase tracking-widest">View Sessions</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    {/* Print View Overlay/Content */}
                    {showPrintView && (
                        <div className="bg-white rounded-3xl shadow-xl border border-blue-100 overflow-hidden animate-in fade-in zoom-in duration-300 mb-8 no-print">
                            <div className="bg-blue-600 p-6 flex flex-col sm:flex-row justify-between items-center text-white gap-4">
                                <div className="flex items-center gap-4">
                                    <div className="bg-white/20 p-2 rounded-lg">
                                        <Printer size={20} />
                                    </div>
                                    <div>
                                        <h3 className="font-black uppercase tracking-tight text-sm sm:text-base">Print Preview</h3>
                                        <p className="text-blue-100 text-[10px] sm:text-xs font-medium">Ready to export {generatedBatch.length} vouchers</p>
                                    </div>
                                </div>
                                <div className="flex gap-3 w-full sm:w-auto">
                                    <button onClick={() => setShowPrintView(false)} className="flex-1 sm:flex-none px-5 py-2 hover:bg-white/10 rounded-xl font-bold text-[10px] sm:text-xs uppercase transition-colors border border-white/20">Close</button>
                                    <button onClick={() => window.print()} className="flex-1 sm:flex-none bg-white text-blue-600 px-6 py-2 rounded-xl font-black text-[10px] sm:text-xs uppercase shadow-lg transition-all active:scale-95">Print Now</button>
                                </div>
                            </div>
                            <div className="p-4 sm:p-8 bg-gray-50 grid grid-cols-2 xs:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4 overflow-y-auto max-h-[400px]">
                                {generatedBatch.map((u, i) => (
                                    <div key={i} className="bg-white p-3 sm:p-4 rounded-xl border border-gray-200 shadow-sm text-center">
                                        <div className="text-[8px] sm:text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">Voucher</div>
                                        <div className="font-mono text-base sm:text-lg font-black text-blue-600 bg-blue-50 py-1 sm:py-2 rounded-lg border border-blue-100 mb-1 sm:mb-2" style={{ color: template.color_primary, backgroundColor: template.color_primary + '10', borderColor: template.color_primary + '30' }}>{u.username}</div>
                                        <div className="flex flex-col items-center gap-1">
                                            <img
                                                src={`https://api.qrserver.com/v1/create-qr-code/?size=60x60&data=${encodeURIComponent(`http://10.5.5.1/login?username=${u.username}&password=${u.password}`)}`}
                                                alt="QR Login"
                                                className="w-12 h-12 grayscale opacity-50 mb-1"
                                            />
                                            <div className="text-[7px] sm:text-[8px] text-gray-400 uppercase font-bold">LIM: {batchForm.time_limit || 'UNLIM'}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Hidden Print Area (Physical Print) */}
                    {/* Hidden Print Area (Physical Print) */}
                    {/* Hidden Print Area (Physical Print) */}
                    <div className="hidden print:grid print:grid-cols-5 print:gap-3 print:p-4" id="printable-area">
                        {generatedBatch.map((u, i) => (
                            <div key={i} className="voucher-card p-2 rounded-lg border border-gray-200 text-center bg-white flex flex-col justify-center min-h-[70px] overflow-hidden break-inside-avoid shadow-sm relative">
                                {/* Cut Guides */}
                                <div className="absolute top-0 left-0 w-1.5 h-1.5 border-t border-l border-gray-300"></div>
                                <div className="absolute top-0 right-0 w-1.5 h-1.5 border-t border-r border-gray-300"></div>
                                <div className="absolute bottom-0 left-0 w-1.5 h-1.5 border-b border-l border-gray-300"></div>
                                <div className="absolute bottom-0 right-0 w-1.5 h-1.5 border-b border-r border-gray-300"></div>

                                <div className="text-[9px] font-black uppercase tracking-widest leading-none mb-1.5 print-header" style={{ color: template.color_primary }}>{template.header_text}</div>
                                <div className="flex items-center gap-2 mb-1.5">
                                    <div className="bg-blue-50 border border-blue-100 rounded-md py-1 flex-1 flex justify-center items-center print-bg print-border overflow-hidden" style={{ backgroundColor: template.color_primary + '10', borderColor: template.color_primary + '30' }}>
                                        <div className="font-mono text-base font-black leading-none tracking-tight print-header whitespace-nowrap overflow-hidden text-ellipsis px-1" style={{ color: template.color_primary }}>{u.username}</div>
                                    </div>
                                    <img
                                        src={`https://api.qrserver.com/v1/create-qr-code/?size=40x40&data=${encodeURIComponent(`http://10.5.5.1/login?username=${u.username}&password=${u.password}`)}`}
                                        className="w-8 h-8 rounded border border-gray-100 p-0.5"
                                        alt="QR"
                                    />
                                </div>
                                <div className="text-[7px] font-bold text-gray-400 uppercase leading-none mb-0.5" style={{ color: template.color_primary }}>
                                    {template.footer_text}
                                </div>
                                <div className="text-[7px] font-bold text-gray-400 uppercase leading-none">
                                    LIM: {batchForm.time_limit || 'UNLIM'}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Active Sessions */}
                    {activeTab === 'active' && !showPrintView && (
                        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="p-6 sm:p-8 border-b border-gray-50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                                <h2 className="text-xl font-black text-gray-900">Online Users</h2>
                                <span className="inline-flex max-w-fit bg-blue-50 text-blue-600 px-4 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest">
                                    {activeSessions.length} Connected
                                </span>
                            </div>
                            <div className="overflow-hidden">
                                <ResponsiveTable
                                    data={activeSessions}
                                    columns={[
                                        {
                                            header: 'Identity',
                                            accessor: 'user',
                                            render: (u) => <div className="font-bold text-gray-900 text-sm">{u.user}</div>
                                        },
                                        {
                                            header: 'Network Info',
                                            accessor: 'address',
                                            render: (u) => (
                                                <div>
                                                    <div className="text-xs text-gray-900 font-mono font-bold leading-none mb-1">{u.address}</div>
                                                    <div className="text-[10px] text-gray-400 font-mono tracking-tighter uppercase">{u.mac_address || 'Unknown MAC'}</div>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Time Online',
                                            accessor: 'uptime',
                                            render: (u) => <div className="text-xs text-gray-500 font-medium whitespace-nowrap">{u.uptime}</div>
                                        },
                                        {
                                            header: 'Interrupt',
                                            accessor: 'actions',
                                            render: (u) => (
                                                <div className="text-right">
                                                    <button onClick={() => handleKick(u.id)} className="text-red-500 hover:text-red-700 font-black text-[10px] uppercase tracking-widest hover:underline px-3 py-1.5 bg-red-50 rounded-lg whitespace-nowrap">
                                                        Kick
                                                    </button>
                                                </div>
                                            )
                                        }
                                    ]}
                                    renderCard={(u) => (
                                        <div className="flex flex-col gap-3">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Wifi size={16} className="text-emerald-500" />
                                                    <span className="font-bold text-gray-900 text-sm">{u.user}</span>
                                                </div>
                                                <span className="text-[10px] font-mono text-gray-400">{u.address}</span>
                                            </div>
                                            <div className="flex justify-between items-center text-xs text-gray-500">
                                                <div className="flex items-center gap-1.5">
                                                    <Clock size={12} />
                                                    <span>{u.uptime}</span>
                                                </div>
                                            </div>
                                            <div className="flex justify-end border-t pt-3 mt-1">
                                                <button onClick={() => handleKick(u.id)} className="w-full text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 py-2 rounded-lg">Interrupt Session</button>
                                            </div>
                                        </div>
                                    )}
                                    emptyMessage="No active hotspot sessions detected."
                                />
                            </div>
                        </div>
                    )}

                    {/* Users Database */}
                    {activeTab === 'users' && (
                        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="p-6 sm:p-8 border-b border-gray-50 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                                <div className="flex items-center gap-4">
                                    <div className="p-3 bg-blue-50 rounded-2xl">
                                        <Users className="text-blue-600" size={24} />
                                    </div>
                                    <div>
                                        <h2 className="text-xl font-black text-gray-900 leading-none">Voucher Database</h2>
                                        <p className="text-gray-400 text-[10px] mt-1 font-bold uppercase tracking-widest">{users.length} Total Records</p>
                                    </div>
                                </div>

                                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                                    <div className="relative group flex-1 sm:w-64">
                                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 transition-colors group-focus-within:text-blue-500" size={18} />
                                        <input
                                            type="text"
                                            placeholder="Search vouchers..."
                                            value={userSearch}
                                            onChange={(e) => setUserSearch(e.target.value)}
                                            className="w-full bg-gray-50 border border-transparent focus:border-blue-500/30 focus:bg-white rounded-2xl py-2.5 pl-12 pr-4 text-sm font-bold text-gray-700 outline-none transition-all shadow-inner"
                                        />
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={handleExportCSV}
                                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-white border border-gray-100 px-4 py-2.5 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-600 hover:bg-gray-50 transition-all active:scale-95"
                                        >
                                            <Download size={16} />
                                            Export
                                        </button>
                                        <button
                                            onClick={handleCleanupExpired}
                                            className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-red-50 border border-red-100 px-4 py-2.5 rounded-2xl text-[10px] font-black uppercase tracking-widest text-red-600 hover:bg-red-100 transition-all active:scale-95"
                                        >
                                            <Trash2 size={16} />
                                            Cleanup Expired
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div className="overflow-hidden">
                                <ResponsiveTable
                                    data={users.filter(u => u.name.toLowerCase().includes(userSearch.toLowerCase()) || (u.comment || '').toLowerCase().includes(userSearch.toLowerCase()))}
                                    columns={[
                                        {
                                            header: 'Identity',
                                            accessor: 'name',
                                            render: (u) => (
                                                <div>
                                                    <div className="font-bold text-gray-900 text-sm flex items-center gap-2">
                                                        {u.name}
                                                        {u.comment && <span className="text-[8px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded uppercase tracking-tighter">Batch: {u.comment}</span>}
                                                    </div>
                                                    <div className="text-[10px] text-gray-400 font-mono tracking-tighter">PWD: {u.password}</div>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Profile & Limits',
                                            accessor: 'profile',
                                            render: (u) => (
                                                <div className="flex flex-col gap-1">
                                                    <span className="max-w-fit px-3 py-1 bg-emerald-50 text-emerald-600 rounded-lg text-[10px] font-black uppercase whitespace-nowrap">{u.profile}</span>
                                                    {(u.limit_uptime || u.limit_bytes_total) && (
                                                        <div className="text-[8px] text-gray-400 font-bold uppercase tracking-widest whitespace-nowrap">
                                                            {u.limit_uptime && <span>Time: {u.limit_uptime}</span>}
                                                            {u.limit_bytes_total > 0 && <span> • Data: {(u.limit_bytes_total / 1024 / 1024).toFixed(0)}MB</span>}
                                                        </div>
                                                    )}
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Current Usage',
                                            accessor: 'bytes_in',
                                            render: (u) => (
                                                <div>
                                                    <div className="text-xs font-bold text-gray-700 whitespace-nowrap">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB In</div>
                                                    <div className="text-[10px] text-gray-400 font-medium whitespace-nowrap">{u.uptime || '0s'} Uptime</div>
                                                </div>
                                            )
                                        },
                                        {
                                            header: 'Actions',
                                            accessor: 'actions',
                                            render: (u) => (
                                                <div className="text-right flex items-center justify-end gap-2">
                                                    {u.comment && (
                                                        <button
                                                            onClick={() => handleBulkDeleteByComment(u.comment)}
                                                            className="text-orange-500 hover:text-orange-700 font-black text-[10px] uppercase tracking-widest hover:underline px-2 py-1 bg-orange-50 rounded-lg whitespace-nowrap"
                                                            title={`Delete all users in batch ${u.comment}`}
                                                        >
                                                            Del Batch
                                                        </button>
                                                    )}
                                                    <button onClick={() => handleDelete(u.name)} className="text-red-500 hover:text-red-700 font-black text-[10px] uppercase tracking-widest hover:underline px-3 py-1.5 bg-red-50 rounded-lg whitespace-nowrap">
                                                        Revoke
                                                    </button>
                                                </div>
                                            )
                                        }
                                    ]}
                                    renderCard={(u) => (
                                        <div className="flex flex-col gap-3">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Users size={16} className="text-blue-500" />
                                                    <span className="font-bold text-gray-900 text-sm">{u.name}</span>
                                                </div>
                                                <span className="px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded-md text-[10px] font-black uppercase text-center">{u.profile}</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                                                <div className="bg-gray-50 p-2 rounded-lg">
                                                    <div className="text-[8px] uppercase font-bold text-gray-400">Password</div>
                                                    <div className="font-mono font-bold text-gray-700">{u.password}</div>
                                                </div>
                                                <div className="bg-gray-50 p-2 rounded-lg">
                                                    <div className="text-[8px] uppercase font-bold text-gray-400">Usage</div>
                                                    <div className="font-mono font-bold text-gray-700">{(u.bytes_in / 1024 / 1024).toFixed(1)} MB</div>
                                                </div>
                                            </div>
                                            {(u.comment || u.limit_uptime || u.limit_bytes_total) && (
                                                <div className="bg-blue-50/50 p-2 rounded-lg text-[8px] font-bold text-gray-500 uppercase tracking-widest flex flex-wrap gap-2">
                                                    {u.comment && <div className="bg-white px-1.5 py-0.5 rounded shadow-sm border border-blue-100">Batch: {u.comment}</div>}
                                                    {u.limit_uptime && <div className="bg-white px-1.5 py-0.5 rounded shadow-sm border border-blue-100">Limit: {u.limit_uptime}</div>}
                                                </div>
                                            )}
                                            <div className="flex gap-2 border-t pt-3 mt-1">
                                                {u.comment && (
                                                    <button onClick={() => handleBulkDeleteByComment(u.comment)} className="flex-1 text-center text-orange-500 font-bold text-[10px] uppercase bg-orange-50 py-2 rounded-lg">Delete Batch</button>
                                                )}
                                                <button onClick={() => handleDelete(u.name)} className="flex-1 text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 py-2 rounded-lg">Revoke Token</button>
                                            </div>
                                        </div>
                                    )}
                                    emptyMessage="Voucher database is empty."
                                />
                            </div>
                        </div>
                    )}

                    {/* Hotspot Profiles Tab */}
                    {activeTab === 'profiles' && (
                        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center bg-white p-6 sm:p-8 rounded-3xl shadow-sm border border-gray-100 gap-6">
                                <div>
                                    <h2 className="text-xl sm:text-2xl font-black text-gray-900 tracking-tight">Hotspot User Profiles</h2>
                                    <p className="text-gray-500 font-medium text-xs sm:text-sm">Define speed limits and simultaneous device allowances.</p>
                                </div>
                                <button
                                    onClick={() => setShowProfileModal(true)}
                                    className="bg-blue-600 text-white px-6 sm:px-8 py-3 sm:py-3.5 rounded-2xl font-black text-[10px] sm:text-xs uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95 flex items-center justify-center gap-2"
                                >
                                    <Plus size={18} /> Create Profile
                                </button>
                            </div>

                            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden">
                                <div className="overflow-hidden">
                                    <ResponsiveTable
                                        data={profiles}
                                        columns={[
                                            {
                                                header: 'Profile Name',
                                                accessor: 'name',
                                                render: (p) => <div className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors uppercase tracking-tight text-sm">{p.name}</div>
                                            },
                                            {
                                                header: 'Bandwidth',
                                                accessor: 'rate-limit',
                                                render: (p) => (
                                                    <div className="inline-flex items-center gap-2 bg-indigo-50 text-indigo-700 px-3 py-1 rounded-xl text-[10px] font-black tracking-widest font-mono">
                                                        {p['rate-limit'] || 'UNLIMITED'}
                                                    </div>
                                                )
                                            },
                                            {
                                                header: 'Devices',
                                                accessor: 'shared-users',
                                                render: (p) => <div className="text-gray-900 font-black text-sm text-center">{p['shared-users'] || '1'}</div>
                                            },
                                            {
                                                header: 'Active Users',
                                                accessor: 'active_users',
                                                render: (p) => (
                                                    <div className="flex items-center justify-center gap-1.5">
                                                        <div className={`w-1.5 h-1.5 rounded-full ${p.active_users > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-gray-300'}`}></div>
                                                        <span className={`text-[10px] font-black uppercase tracking-tight ${p.active_users > 0 ? 'text-emerald-600' : 'text-gray-400'}`}>
                                                            {p.active_users || 0} Online
                                                        </span>
                                                    </div>
                                                )
                                            },
                                            {
                                                header: 'Delete',
                                                accessor: 'actions',
                                                render: (p) => (
                                                    <div className="text-right">
                                                        <button
                                                            onClick={() => handleProfileDelete(p.name)}
                                                            className="text-red-500 hover:text-red-700 p-2 bg-red-50 rounded-xl transition-all active:scale-90"
                                                            title="Remove Profile"
                                                        >
                                                            <Trash2 size={18} />
                                                        </button>
                                                    </div>
                                                )
                                            }
                                        ]}
                                        renderCard={(p) => (
                                            <div className="flex flex-col gap-3">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <Shield size={16} className="text-purple-500" />
                                                        <span className="font-bold text-gray-900 uppercase text-sm">{p.name}</span>
                                                    </div>
                                                    <div className="text-xs font-black bg-indigo-50 text-indigo-700 px-2 py-1 rounded-lg font-mono">
                                                        {p['rate-limit'] || 'UNLIM'}
                                                    </div>
                                                </div>
                                                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                                                    <div className="bg-gray-50 p-2 rounded-lg text-center">
                                                        <div className="uppercase font-bold text-[8px] text-gray-400">Shared Devices</div>
                                                        <div className="font-black text-gray-900">{p['shared-users'] || '1'}</div>
                                                    </div>
                                                    <div className="bg-emerald-50 p-2 rounded-lg text-center border border-emerald-100/50">
                                                        <div className="uppercase font-bold text-[8px] text-emerald-600">Active Users</div>
                                                        <div className="font-black text-emerald-700">{p.active_users || 0} Online</div>
                                                    </div>
                                                </div>
                                                <div className="flex justify-end border-t pt-3 mt-1">
                                                    <button onClick={() => handleProfileDelete(p.name)} className="w-full text-center text-red-500 font-bold text-[10px] uppercase bg-red-50 py-2 rounded-lg">Delete Profile</button>
                                                </div>
                                            </div>
                                        )}
                                        emptyMessage="No profiles found on this router."
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Batch Generator */}
                    {activeTab === 'generate' && (
                        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="bg-white rounded-[32px] sm:rounded-[40px] shadow-sm border border-gray-100 overflow-hidden flex flex-col md:flex-row min-h-[500px]">
                                <div className="md:w-1/3 bg-blue-600 p-8 sm:p-12 text-white flex flex-col justify-between">
                                    <div>
                                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-white/10 rounded-2xl flex items-center justify-center mb-6 sm:mb-8">
                                            <Printer size={28} />
                                        </div>
                                        <h3 className="text-2xl sm:text-3xl font-black tracking-tight leading-tight uppercase">Batch Engine</h3>
                                        <p className="text-blue-100 mt-4 font-medium text-xs sm:text-sm">Create unique access codes with a single click.</p>
                                    </div>
                                    <div className="pt-8 hidden sm:block">
                                        <p className="text-[10px] font-black uppercase tracking-widest text-blue-200">Processing high-speed vouchers</p>
                                    </div>
                                </div>
                                <div className="md:w-2/3 p-8 sm:p-12">
                                    <form onSubmit={handleGenerate} className="space-y-6 sm:space-y-8">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
                                            <div>
                                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Token Quantity</label>
                                                <input type="number" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-black text-xl" value={batchForm.qty} onChange={e => setBatchForm({ ...batchForm, qty: parseInt(e.target.value) })} min="1" max="500" required />
                                            </div>
                                            <div>
                                                <div className="flex justify-between items-center mb-3">
                                                    <label className="block text-[10px] font-black text-gray-400 uppercase tracking-widest">Generation Mode</label>
                                                </div>
                                                <div className="flex gap-2">
                                                    <select
                                                        className="w-5/12 bg-gray-50 border-none rounded-2xl px-3 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold text-xs"
                                                        value={batchForm.random_mode ? (batchForm.format === 'numeric' ? 'numeric' : 'auto') : 'prefix'}
                                                        onChange={e => {
                                                            const mode = e.target.value;
                                                            if (mode === 'prefix') {
                                                                setBatchForm({ ...batchForm, random_mode: false, prefix: '', format: 'alphanumeric' });
                                                            } else if (mode === 'auto') {
                                                                setBatchForm({ ...batchForm, random_mode: true, prefix: 'RAND_SEQ', format: 'alphanumeric' });
                                                            } else if (mode === 'numeric') {
                                                                setBatchForm({ ...batchForm, random_mode: true, prefix: 'RAND_NUM', format: 'numeric' });
                                                            }
                                                        }}
                                                    >
                                                        <option value="prefix">Prefix</option>
                                                        <option value="auto">Auto (A-Z, 0-9)</option>
                                                        <option value="numeric">Auto (0-9 Only)</option>
                                                    </select>
                                                    <input
                                                        type="text"
                                                        className="w-7/12 bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold disabled:opacity-50"
                                                        value={batchForm.prefix}
                                                        onChange={e => setBatchForm({ ...batchForm, prefix: e.target.value })}
                                                        disabled={batchForm.random_mode}
                                                        placeholder="Prefix..."
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Link Profile</label>
                                            <select className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" value={batchForm.profile} onChange={e => setBatchForm({ ...batchForm, profile: e.target.value })}>
                                                <option value="default">Default Profile</option>
                                                {profiles.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
                                            </select>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-8">
                                            <div>
                                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Validity</label>
                                                <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" placeholder="e.g. 1h, 1d" value={batchForm.time_limit} onChange={e => setBatchForm({ ...batchForm, time_limit: e.target.value })} />
                                            </div>
                                            <div>
                                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Quota</label>
                                                <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-3.5 sm:py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" placeholder="e.g. 1G" value={batchForm.data_limit} onChange={e => setBatchForm({ ...batchForm, data_limit: e.target.value })} />
                                            </div>
                                        </div>

                                        <div className="pt-4 sm:pt-6">
                                            <button type="submit" className="w-full py-4 sm:py-5 bg-blue-600 text-white rounded-3xl font-black text-xs sm:text-sm uppercase tracking-widest hover:bg-blue-700 shadow-2xl shadow-blue-100 transition-all active:scale-[0.98]" disabled={loading}>
                                                {loading ? 'Processing...' : 'Generate Hotspot Vouchers'}
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div >
                    )}

                    {/* Template Editor */}
                    {activeTab === 'templates' && (
                        <div className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
                            <div className="bg-white rounded-[32px] sm:rounded-[40px] shadow-sm border border-gray-100 overflow-hidden flex flex-col md:flex-row min-h-[500px]">
                                <div className="md:w-1/3 bg-gray-900 p-8 sm:p-12 text-white flex flex-col justify-between">
                                    <div>
                                        <div className="w-12 h-12 sm:w-16 sm:h-16 bg-white/10 rounded-2xl flex items-center justify-center mb-6 sm:mb-8">
                                            <Printer size={28} />
                                        </div>
                                        <h3 className="text-2xl sm:text-3xl font-black tracking-tight leading-tight uppercase">Print Styles</h3>
                                        <p className="text-gray-400 mt-4 font-medium text-xs sm:text-sm">Customize how your vouchers look when printed.</p>
                                    </div>
                                </div>
                                <div className="md:w-2/3 p-8 sm:p-12">
                                    <form onSubmit={saveTemplate} className="space-y-6">
                                        <div>
                                            <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Header Text</label>
                                            <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" value={template.header_text} onChange={e => setTemplate({ ...template, header_text: e.target.value })} />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Footer Text</label>
                                            <input type="text" className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold" value={template.footer_text} onChange={e => setTemplate({ ...template, footer_text: e.target.value })} />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Primary Color</label>
                                            <div className="flex gap-4 items-center">
                                                <input type="color" className="h-12 w-24 rounded-xl cursor-pointer border-none p-1 bg-gray-50" value={template.color_primary} onChange={e => setTemplate({ ...template, color_primary: e.target.value })} />
                                                <span className="font-mono text-gray-500 text-sm font-bold">{template.color_primary}</span>
                                            </div>
                                        </div>

                                        <div className="pt-6">
                                            <button type="submit" className="w-full py-4 bg-blue-600 text-white rounded-3xl font-black text-xs sm:text-sm uppercase tracking-widest hover:bg-blue-700 shadow-xl transition-all active:scale-[0.98]" disabled={loading}>
                                                {loading ? 'Saving...' : 'Save Template'}
                                            </button>
                                        </div>
                                    </form>
                                    <div className="mt-8 pt-8 border-t border-gray-100">
                                        <h4 className="text-[10px] font-black text-gray-400 uppercase mb-4 tracking-widest">Preview</h4>
                                        <div className="w-48 mx-auto p-4 border border-dashed border-gray-300 rounded-lg text-center bg-gray-50">
                                            <div className="text-[10px] font-black uppercase tracking-widest leading-none mb-2" style={{ color: template.color_primary }}>{template.header_text}</div>
                                            <div className="bg-white border rounded-md py-3 mb-2 w-full flex justify-center items-center" style={{ borderColor: template.color_primary + '40', backgroundColor: template.color_primary + '10' }}>
                                                <div className="font-mono text-xl font-black leading-none tracking-tight" style={{ color: template.color_primary }}>abc1234</div>
                                            </div>
                                            <div className="text-[8px] font-bold text-gray-400 uppercase">{template.footer_text}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div >

            {/* Profile Creation Modal */}
            < ResponsiveModal
                isOpen={showProfileModal}
                onClose={() => setShowProfileModal(false)
                }
                title="New Hotspot Profile"
                size="lg"
            >
                <div className="pb-4">
                    <p className="text-blue-600 text-xs sm:text-sm mb-6 font-medium">Configure network limitations for this profile.</p>
                    <form onSubmit={handleProfileAdd} className="space-y-8">
                        <div>
                            <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Profile Name</label>
                            <input
                                type="text"
                                className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-black"
                                value={profileForm.name}
                                onChange={e => setProfileForm({ ...profileForm, name: e.target.value })}
                                placeholder="e.g. ULTRA_FAST_MONTHLY"
                                required
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-8">
                            <div>
                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Rate Limit (Up/Down)</label>
                                <input
                                    type="text"
                                    className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-bold font-mono"
                                    value={profileForm.rateLimit}
                                    onChange={e => setProfileForm({ ...profileForm, rateLimit: e.target.value })}
                                    placeholder="5M/5M"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black text-gray-400 uppercase mb-3 tracking-widest">Shared Device Count</label>
                                <input
                                    type="number"
                                    className="w-full bg-gray-50 border-none rounded-2xl px-5 py-4 focus:ring-2 focus:ring-blue-500 transition-all font-black"
                                    value={profileForm.sharedUsers}
                                    onChange={e => setProfileForm({ ...profileForm, sharedUsers: parseInt(e.target.value) })}
                                    min="1"
                                    required
                                />
                            </div>
                        </div>
                        <div className="pt-6 flex gap-4">
                            <button type="button" onClick={() => setShowProfileModal(false)} className="flex-1 px-6 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest text-gray-400 hover:bg-gray-50 transition-colors">Abort</button>
                            <button type="submit" className="flex-1 px-6 py-4 bg-blue-600 text-white rounded-2xl font-black text-[10px] uppercase tracking-widest hover:bg-blue-700 shadow-xl shadow-blue-100 transition-all active:scale-95">Create Profile</button>
                        </div>
                    </form>
                </div>
            </ResponsiveModal >
        </div >
    );
}

const MetricCard = ({ title, value, icon: Icon, color }) => {
    const colorClasses = {
        blue: "bg-blue-50 text-blue-600 border-blue-100",
        indigo: "bg-indigo-50 text-indigo-600 border-indigo-100",
        emerald: "bg-emerald-50 text-emerald-600 border-emerald-100",
        red: "bg-red-50 text-red-600 border-red-100"
    };

    return (
        <div className={`bg-white p-6 rounded-[32px] border ${colorClasses[color] || colorClasses.blue} shadow-sm flex items-center gap-5 transition-all hover:scale-[1.02]`}>
            <div className={`p-4 rounded-2xl ${colorClasses[color]?.split(' ')[0]} ${colorClasses[color]?.split(' ')[1]}`}>
                <Icon size={24} />
            </div>
            <div>
                <p className="text-[10px] font-black uppercase tracking-widest opacity-60">{title}</p>
                <h4 className="text-2xl font-black tracking-tight">{value}</h4>
            </div>
        </div>
    );
};

const TabButton = ({ id, label, icon: Icon, activeTab, setActiveTab }) => (
    <button
        onClick={() => setActiveTab(id)}
        className={`flex-1 min-w-[140px] px-8 py-4 rounded-2xl font-black text-[10px] uppercase tracking-widest flex items-center justify-center gap-3 transition-all duration-300 ${activeTab === id
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 scale-[1.02]'
            : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
            }`}
    >
        <Icon size={16} /> {label}
    </button>
);
